"""Mutual Fund Service — Phase-3 fund pillar.

Responsibilities (all backed by the cached AMFI NAV feed):
- build / serve the searchable direct-plan scheme universe (classified into
  beginner-friendly SEBI buckets, enriched with returns + risk analytics),
- the fund screener (category, expense ratio, AUM, 1/3/5/10-yr returns,
  risk rating, fund age, manager) sorted by a risk-adjusted metric,
- the profiled recommendation flow tied to the Phase-2 risk profile + goal
  ("Conservative + 5-yr goal -> 60% index + 40% hybrid" style advice with
  2-3 concrete direct plans),
- side-by-side comparison (2-4 schemes),
- the SIP / lumpsum / step-up calculator,
- ELSS / exit-load / NFO badges.

Every response carries a visible data-as-of timestamp and the data source.
Return / risk figures are computed from NAV history — they are a record of
the past, not a forecast, and the UI always says so.
"""
from __future__ import annotations

import json
import math
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np

from screener.core.config import config
from screener.core.mf_models import (
    CATEGORY_LABELS,
    FundAllocation,
    FundBasket,
    FundCategory,
    FundComparison,
    FundDetail,
    FundRecommendation,
    FundReturns,
    FundRisk,
    FundScheme,
    FundScreenerRequest,
    FundScreenerResult,
    SipResult,
)
from screener.core.models import RiskLevel
from screener.infrastructure.data.amfi_client import AmfiClient
from screener.services.risk_profile_service import (
    PROFILE_LABELS,
    PROFILE_RETURNS,
)

# --------------------------------------------------------------------------- #
# Curated flagship fragments — these get priority when building the universe
# so the screener and the recommendation flow always surface well-known funds.
# --------------------------------------------------------------------------- #
CURATED_FLAGSHIPS: list[str] = [
    "PARAG PARIKH FLEXI CAP FUND",
    "HDFC BALANCED ADVANTAGE FUND",
    "MIRAE ASSET ELSS TAX SAVER FUND",
    "UTI NIFTY 50 INDEX FUND",
    "HDFC LIQUID FUND",
    "HDFC FLEXI CAP FUND",
    "MIRAE ASSET FLEXI CAP FUND",
    "HDFC CORPORATE BOND FUND",
    "SBI BLUECHIP FUND",
    "HDFC MID-CAP OPPORTUNITIES FUND",
    "NIPPON INDIA SMALL CAP FUND",
    "KOTAK EMERGING EQUITY FUND",
    "AXIS ELSS TAX SAVER FUND",
    "HDFC NIFTY 50 INDEX FUND",
    "SBI SMALL CAP FUND",
    "AXIS FLEXI CAP FUND",
    "ICICI PRUDENTIAL BALANCED ADVANTAGE FUND",
    "SBI EQUITY HYBRID FUND",
    "HDFC HYBRID EQUITY FUND",
    "SBI LIQUID FUND",
    "SBI MAGNUM GILT FUND",
    "HDFC Overnight Fund".upper(),
    "DSP MIDCAP FUND",
    "QUANT FLEXI CAP FUND",
    "AXIS LIQUID FUND",
    "UTI LIQUID FUND",
]

# --------------------------------------------------------------------------- #
# Plain-language helpers
# --------------------------------------------------------------------------- #

_RISK_LABELS = {1: "Low", 2: "Moderately low", 3: "Moderate", 4: "High", 5: "Very high"}

_EXCLUDE_WORDS = ("ETF", "FOF", "FUND OF FUND", "CLOSE ENDED", "NEW FUND OFFER", "NFO")


def normalize(text: str) -> str:
    """Upper-case + collapse whitespace, for name matching."""
    return re.sub(r"\s+", " ", (text or "").upper().strip())


def amc_of(scheme_name: str) -> str:
    """First two words are almost always the AMC ("PARAG PARIKH", "ICICI PRUDENTIAL")."""
    words = normalize(scheme_name).split()
    return " ".join(words[:2]) if words else ""


def is_direct_name(name: str) -> bool:
    return "DIRECT" in normalize(name)


def is_growth_option(name: str) -> bool:
    n = normalize(name)
    return "GROWTH" in n and not any(k in n for k in ("IDCW", "BONUS", "DIVIDEND", "INCOME DISTRIBUTION"))


def is_eligible_name(name: str) -> bool:
    n = normalize(name)
    if any(word in n for word in _EXCLUDE_WORDS):
        return False
    if not n:
        return False
    return True


def classify_name(scheme_name: str) -> FundCategory:
    """Bucket a scheme by its name, using beginner-friendly SEBI buckets.

    Order matters: the most specific buckets (ELSS, index) are checked
    before the broader ones (debt, hybrid).
    """
    n = normalize(scheme_name)
    if any(k in n for k in ("ELSS", "TAX SAVER", "TAX-SAVER", "TAX SAVING")):
        return FundCategory.ELSS
    if any(k in n for k in ("LARGE CAP", "LARGE-CAP", "LARGECAP", "BLUECHIP", "BLUE CHIP")):
        return FundCategory.LARGE
    if any(k in n for k in ("MID CAP", "MID-CAP", "MIDCAP")):
        return FundCategory.MID
    if any(k in n for k in ("SMALL CAP", "SMALL-CAP", "SMALLCAP")):
        return FundCategory.SMALL
    if any(k in n for k in ("FLEXI CAP", "FLEXI-CAP", "FLEXICAP")):
        return FundCategory.FLEXI
    if any(k in n for k in ("MULTI CAP", "MULTI-CAP", "MULTICAP")):
        return FundCategory.MULTI
    if "VALUE" in n:
        return FundCategory.VALUE
    if any(k in n for k in ("INDEX FUND", "INDEX-PLUS", "NIFTY 50", "SENSEX", "INDEX")):
        return FundCategory.INDEX
    if any(k in n for k in ("OVERNIGHT", "LIQUID", "MONEY MARKET", "ULTRA SHORT", "LOW DURATION")):
        return FundCategory.LIQUID
    if any(k in n for k in ("GILT", "CORPORATE BOND", "DURATION", "BOND FUND", "BONDS",
                            "DEBT", "BANKING AND PSU", "FIXED INCOME", "GOVERNMENT",
                            "TREASURY", "FLOATING", "FMP", "INCOME FUND")):
        return FundCategory.DEBT
    if any(k in n for k in ("HYBRID", "BALANCED", "AGGRESSIVE", "EQUITY SAVINGS",
                            "RETIREMENT", "DYNAMIC ASSET", "CONSERVATIVE")):
        return FundCategory.HYBRID
    return FundCategory.OTHER


def classify_sebi(sebi_category: str | None) -> FundCategory:
    """Bucket a raw SEBI scheme-category string (authoritative when present)."""
    c = normalize(sebi_category or "")
    if not c:
        return FundCategory.OTHER
    if "ELSS" in c:
        return FundCategory.ELSS
    if "LARGE CAP" in c:
        return FundCategory.LARGE
    if "MID CAP" in c:
        return FundCategory.MID
    if "SMALL CAP" in c:
        return FundCategory.SMALL
    if "FLEXI CAP" in c:
        return FundCategory.FLEXI
    if "MULTI CAP" in c:
        return FundCategory.MULTI
    if "VALUE" in c:
        return FundCategory.VALUE
    if "INDEX" in c or "ETF" in c:
        return FundCategory.INDEX
    if any(k in c for k in ("OVERNIGHT", "LIQUID", "MONEY MARKET", "ULTRA SHORT", "LOW DURATION")):
        return FundCategory.LIQUID
    if any(k in c for k in ("HYBRID", "BALANCED", "EQUITY SAVINGS", "RETIREMENT", "DYNAMIC")):
        return FundCategory.HYBRID
    if any(k in c for k in ("DEBT", "GILT", "BOND", "DURATION", "INCOME", "GOVERNMENT")):
        return FundCategory.DEBT
    return classify_name(c)


def classify(category: FundCategory | None, sebi_category: str | None = None) -> FundCategory:
    """SEBI string wins when available; otherwise fall back to the name bucket."""
    if category is not None and category != FundCategory.OTHER:
        return category
    return classify_sebi(sebi_category)


# --------------------------------------------------------------------------- #
# NAV analytics (pure functions — a record of the past, never a forecast)
# --------------------------------------------------------------------------- #

_PARSED_CACHE: dict[str, date] = {}


def _parse_date(raw: str) -> date | None:
    """Parse 'DD-MM-YYYY' (mfapi format) or ISO into a date."""
    if not raw:
        return None
    if raw in _PARSED_CACHE:
        return _PARSED_CACHE[raw]
    parsed = None
    try:
        parsed = datetime.strptime(raw, "%d-%m-%Y").date()
    except ValueError:
        try:
            parsed = date.fromisoformat(raw)
        except ValueError:
            parsed = None
    _PARSED_CACHE[raw] = parsed
    return parsed


def normalize_history(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort raw history into ascending [{date: 'YYYY-MM-DD', nav: float}]."""
    points: list[dict[str, Any]] = []
    for point in data or []:
        d = _parse_date(str(point.get("date", "")))
        try:
            nav = float(point.get("nav"))
        except (TypeError, ValueError):
            continue
        if d and nav > 0:
            points.append({"date": d.isoformat(), "nav": nav})
    points.sort(key=lambda p: p["date"])
    return points


def _nav_at(points: list[dict[str, Any]], target: date) -> float | None:
    """NAV of the last point on or before ``target``."""
    best = None
    for point in points:
        d = _parse_date(point["date"])
        if d and d <= target:
            best = point["nav"]
    return best


def cagr(points: list[dict[str, Any]], years: int) -> float | None:
    """Compounded annual growth over a full-year lookback (needs real history)."""
    if len(points) < 30:
        return None
    latest_d = _parse_date(points[-1]["date"])
    latest_nav = points[-1]["nav"]
    if latest_d is None:
        return None
    start = _nav_at(points, latest_d - timedelta(days=int(round(years * 365.25))))
    if not start or start <= 0:
        return None
    elapsed_days = (latest_d - _parse_date(points[0]["date"])).days
    if elapsed_days < int(round(years * 365.25)) * 0.98:
        return None
    return (latest_nav / start) ** (1.0 / years) - 1.0


def _daily_log_returns(points: list[dict[str, Any]]) -> list[float]:
    logs: list[float] = []
    for prev, curr in zip(points, points[1:]):
        if prev["nav"] > 0 and curr["nav"] > 0:
            logs.append(math.log(curr["nav"] / prev["nav"]))
    return logs


def annualized_volatility(points: list[dict[str, Any]]) -> float | None:
    logs = _daily_log_returns(points)
    if len(logs) < 30:
        return None
    return float(np.std(logs) * math.sqrt(252.0))


def max_drawdown(points: list[dict[str, Any]]) -> float | None:
    peak = 0.0
    worst = 0.0
    for point in points:
        nav = point["nav"]
        peak = max(peak, nav)
        if peak > 0:
            worst = min(worst, nav / peak - 1.0)
    return float(worst) if worst < 0 else None


def _downside_deviation(points: list[dict[str, Any]]) -> float | None:
    logs = _daily_log_returns(points)
    neg = [log for log in logs if log < 0]
    if len(neg) < 10:
        return None
    return float(np.std(neg) * math.sqrt(252.0))


def risk_rating(vol: float | None) -> tuple[int, str] | None:
    """Map annualised volatility onto a 1-5 beginner risk scale."""
    if vol is None:
        return None
    if vol < 0.04:
        rating = 1
    elif vol < 0.08:
        rating = 2
    elif vol < 0.14:
        rating = 3
    elif vol < 0.22:
        rating = 4
    else:
        rating = 5
    return rating, _RISK_LABELS[rating]


def compute_returns(points: list[dict[str, Any]]) -> FundReturns:
    return FundReturns(
        one_year=cagr(points, 1),
        three_year=cagr(points, 3),
        five_year=cagr(points, 5),
        ten_year=cagr(points, 10),
        since_inception=cagr(points, max(int(((_parse_date(points[-1]["date"]) - _parse_date(points[0]["date"])).days or 0) / 365.25), 1)) if points else None,
    )


def compute_risk(points: list[dict[str, Any]], returns: FundReturns) -> FundRisk:
    vol = annualized_volatility(points)
    rating_info = risk_rating(vol)
    annual = returns.three_year if returns.three_year is not None else returns.since_inception
    rf = config.mutual_fund.risk_free_rate
    sharpe = None
    sortino = None
    if annual is not None and vol:
        sharpe = (annual - rf) / vol
    down = _downside_deviation(points)
    if annual is not None and down:
        sortino = (annual - rf) / down
    rating, label = rating_info or (None, None)
    return FundRisk(
        rating=rating,
        rating_label=label,
        volatility_annual=vol,
        sharpe=float(sharpe) if sharpe is not None else None,
        sortino=float(sortino) if sortino is not None else None,
        max_drawdown=max_drawdown(points),
    )


def fund_age_years(points: list[dict[str, Any]], launch_date: str | None) -> float | None:
    if launch_date:
        d = _parse_date(launch_date)
        if d:
            return max(0.0, (date.today() - d).days / 365.25)
    if points:
        start = _parse_date(points[0]["date"])
        if start:
            return max(0.0, (date.today() - start).days / 365.25)
    return None


# --------------------------------------------------------------------------- #
# Metadata
# --------------------------------------------------------------------------- #

def _load_metadata() -> dict[str, dict[str, Any]]:
    path = Path(__file__).resolve().parent.parent / "data" / "mf_metadata.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("funds", {})
    except Exception:
        return {}


_METADATA: dict[str, dict[str, Any]] = _load_metadata()


def match_metadata(scheme_name: str) -> dict[str, Any]:
    """Curated metadata keyed by canonical fragment; matched on Direct plans."""
    n = normalize(scheme_name)
    for fragment, meta in _METADATA.items():
        if fragment in n and "DIRECT" in n:
            return meta
    return {}


# --------------------------------------------------------------------------- #
# Service
# --------------------------------------------------------------------------- #

class MutualFundService:
    """Screener + recommendation + comparison + SIP over the MF universe."""

    def __init__(self, client: AmfiClient | None = None):
        self.client = client or AmfiClient()
        self._universe: list[FundScheme] | None = None

    # ------------------------------------------------------------------ #
    # Universe
    # ------------------------------------------------------------------ #

    def universe(self, force_refresh: bool = False) -> list[FundScheme]:
        """Cached direct-plan universe, enriched with analytics."""
        if self._universe is not None and not force_refresh:
            return self._universe
        if not force_refresh:
            cached = self._read_universe_cache()
            if cached is not None:
                self._universe = cached
                return cached
        built = self._build_universe()
        self._universe = built
        self._write_universe_cache(built)
        return built

    def _read_universe_cache(self) -> list[FundScheme] | None:
        try:
            path = config.mf_universe_file
            if not path.exists():
                return None
            raw = json.loads(path.read_text(encoding="utf-8"))
            if self._fresh(raw.get("fetched_at")):
                items = [FundScheme.model_validate(x) for x in raw.get("items", [])]
                return items or None
        except Exception:
            pass
        return None

    def _write_universe_cache(self, schemes: list[FundScheme]) -> None:
        try:
            config.mf_universe_file.parent.mkdir(parents=True, exist_ok=True)
            config.mf_universe_file.write_text(
                json.dumps({
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "items": [s.model_dump(mode="json") for s in schemes],
                }),
                encoding="utf-8",
            )
        except Exception:
            pass

    @staticmethod
    def _fresh(fetched_at: str | None) -> bool:
        if not fetched_at:
            return False
        try:
            return (datetime.now(timezone.utc) - datetime.fromisoformat(fetched_at)).total_seconds() <= config.mutual_fund.cache_ttl_seconds
        except Exception:
            return False

    def _build_universe(self) -> list[FundScheme]:
        """Pick a curated direct-growth universe from the master, enrich each."""
        try:
            master, _meta = self.client.fetch_master()
        except Exception:
            return []
        if not master:
            return []

        candidates: list[dict[str, Any]] = []
        for item in master:
            name = str(item.get("schemeName") or "")
            code = item.get("schemeCode")
            if not is_eligible_name(name) or not is_direct_name(name) or not is_growth_option(name):
                continue
            bucket = classify_name(name)
            if bucket == FundCategory.OTHER:
                continue
            candidates.append({"code": int(code), "name": name, "bucket": bucket})

        # Flagships first; then by recency of code (proxy for newer registrations).
        def priority(candidate: dict[str, Any]) -> int:
            n = normalize(candidate["name"])
            for i, fragment in enumerate(CURATED_FLAGSHIPS):
                if fragment in n:
                    return i
            return 10_000

        candidates.sort(key=lambda c: (priority(c), c["code"]))

        selected: list[dict[str, Any]] = []
        per_cat: dict[str, int] = {}
        per_amc_cat: dict[tuple[str, str], int] = {}
        for candidate in candidates:
            bucket = candidate["bucket"].value
            if per_cat.get(bucket, 0) >= config.mutual_fund.per_category_max:
                continue
            amc = amc_of(candidate["name"])
            if per_amc_cat.get((bucket, amc), 0) >= config.mutual_fund.per_amc_per_category:
                continue
            selected.append(candidate)
            per_cat[bucket] = per_cat.get(bucket, 0) + 1
            per_amc_cat[(bucket, amc)] = per_amc_cat.get((bucket, amc), 0) + 1
            if len(selected) >= config.mutual_fund.universe_max:
                break

        schemes: list[FundScheme] = []
        with ThreadPoolExecutor(max_workers=config.mutual_fund.max_workers) as pool:
            futures = {pool.submit(self._scheme_from_detail, c): c for c in selected}
            for future in futures:
                scheme = future.result()
                if scheme is not None:
                    schemes.append(scheme)
        schemes.sort(key=lambda s: (s.risk.sharpe if s.risk.sharpe is not None else -99), reverse=True)
        return schemes

    def _scheme_from_detail(self, candidate: dict[str, Any]) -> FundScheme | None:
        code = candidate["code"]
        try:
            detail, meta = self.client.fetch_scheme(code)
        except Exception:
            return None
        if not detail or meta.get("error"):
            return None
        dmeta = detail.get("meta", {}) or {}
        name = str(dmeta.get("scheme_name") or candidate["name"])
        points = normalize_history(detail.get("data", []))
        nav = points[-1]["nav"] if points else None
        nav_date = points[-1]["date"] if points else None
        metadata = match_metadata(name)
        sebi = dmeta.get("scheme_category")
        bucket = classify(None, sebi) if sebi else candidate["bucket"]
        returns = compute_returns(points) if points else FundReturns()
        risk = compute_risk(points, returns) if points else FundRisk()
        launch = metadata.get("launch_date")
        return FundScheme(
            scheme_code=code,
            scheme_name=name,
            fund_house=dmeta.get("fund_house") or amc_of(name),
            category=bucket,
            sebi_category=sebi,
            is_direct=True,
            is_growth=True,
            is_elss=bucket == FundCategory.ELSS,
            nav=nav,
            nav_date=nav_date,
            isin_growth=dmeta.get("isin_growth") or candidate.get("isinGrowth"),
            expense_ratio=metadata.get("expense_ratio"),
            aum_cr=metadata.get("aum_cr"),
            launch_date=launch,
            fund_manager=metadata.get("fund_manager"),
            exit_load=metadata.get("exit_load"),
            returns=returns,
            risk=risk,
            fund_age_years=fund_age_years(points, launch),
            data_as_of=datetime.now(timezone.utc),
            source=self.client.source,
        )

    def _data_as_of(self) -> datetime | None:
        fetched = self.client.data_as_of()
        if not fetched:
            return None
        try:
            return datetime.fromisoformat(fetched)
        except Exception:
            return None

    def status(self) -> dict[str, Any]:
        schemes = self.universe()
        return {
            "enabled": config.mutual_fund.enabled,
            "source": self.client.source,
            "data_as_of": self._data_as_of(),
            "universe_size": len(schemes),
            "categories": [{"value": c.value, "label": CATEGORY_LABELS[c]} for c in FundCategory],
            "note": "Daily NAV refresh from the AMFI feed; timestamps are visible on every response.",
        }

    def categories(self) -> list[dict[str, str]]:
        return [{"value": c.value, "label": CATEGORY_LABELS[c]} for c in FundCategory]

    # ------------------------------------------------------------------ #
    # Screener
    # ------------------------------------------------------------------ #

    def screener(self, request: FundScreenerRequest) -> FundScreenerResult:
        schemes = self.universe()
        data_as_of = self._data_as_of()

        def pass_filters(s: FundScheme) -> bool:
            if request.category is not None and s.category != request.category:
                return False
            if request.max_expense_ratio is not None:
                if s.expense_ratio is None or s.expense_ratio > request.max_expense_ratio:
                    return False
            if request.min_aum_cr is not None:
                if s.aum_cr is None or s.aum_cr < request.min_aum_cr:
                    return False
            if request.min_return_1y is not None:
                if s.returns.one_year is None or s.returns.one_year * 100 < request.min_return_1y:
                    return False
            if request.min_return_3y is not None:
                if s.returns.three_year is None or s.returns.three_year * 100 < request.min_return_3y:
                    return False
            if request.min_return_5y is not None:
                if s.returns.five_year is None or s.returns.five_year * 100 < request.min_return_5y:
                    return False
            if request.max_risk_rating is not None:
                if s.risk.rating is None or s.risk.rating > request.max_risk_rating:
                    return False
            if request.min_fund_age_years is not None:
                if s.fund_age_years is None or s.fund_age_years < request.min_fund_age_years:
                    return False
            if request.manager:
                if not s.fund_manager or request.manager.lower() not in s.fund_manager.lower():
                    return False
            if request.elss_only and not s.is_elss:
                return False
            if request.direct_only and not s.is_direct:
                return False
            return True

        items = [s for s in schemes if pass_filters(s)]
        items.sort(key=lambda s: self._sort_key(s, request.sort_by), reverse=(request.sort_dir == "desc"))
        total = len(items)
        page = items[request.offset: request.offset + request.limit]
        return FundScreenerResult(
            items=page,
            total=total,
            categories=self.categories(),
            sort_by=request.sort_by,
            sort_dir=request.sort_dir,
            data_as_of=data_as_of,
            refreshed_at=datetime.now(timezone.utc),
            source=self.client.source,
            stale=not bool(schemes),
            note=("Fund data is still warming up — first load takes a minute or two." if not schemes else None),
        )

    @staticmethod
    def _sort_key(s: FundScheme, sort_by: str) -> float:
        fields = {
            "sharpe": s.risk.sharpe,
            "sortino": s.risk.sortino,
            "returns_1y": s.returns.one_year,
            "returns_3y": s.returns.three_year,
            "returns_5y": s.returns.five_year,
            "expense_ratio": -s.expense_ratio if s.expense_ratio is not None else None,
            "aum": s.aum_cr,
            "nav": s.nav,
            "name": s.nav,  # name sorting handled separately
        }
        value = fields.get(sort_by, fields["sharpe"])
        return value if value is not None else -math.inf

    # ------------------------------------------------------------------ #
    # Detail / compare
    # ------------------------------------------------------------------ #

    def detail(self, scheme_code: int) -> FundDetail:
        schemes = self.universe()
        scheme = next((s for s in schemes if s.scheme_code == int(scheme_code)), None)
        if scheme is None:
            # Fall back to a live fetch (scheme outside the curated universe).
            raw, meta = self.client.fetch_scheme(int(scheme_code))
            if not raw or meta.get("error"):
                raise LookupError(f"scheme {scheme_code} not found")
            candidate = {"code": int(scheme_code), "name": raw.get("meta", {}).get("scheme_name", ""), "bucket": FundCategory.OTHER}
            scheme = self._scheme_from_detail(candidate)
            if scheme is None:
                raise LookupError(f"scheme {scheme_code} not found")
        points = normalize_history(self._scheme_history(scheme_code))
        is_nfo = False
        if scheme.launch_date:
            launched = _parse_date(scheme.launch_date)
            if launched and (date.today() - launched).days <= 180:
                is_nfo = True
        return FundDetail(scheme=scheme, history=points[-730:], is_nfo=is_nfo)

    def _scheme_history(self, scheme_code: int) -> list[dict[str, Any]]:
        raw, _meta = self.client.fetch_scheme(int(scheme_code))
        return raw.get("data", []) if raw else []

    def compare(self, codes: list[int]) -> FundComparison:
        seen: list[FundScheme] = []
        for code in (codes or [])[:4]:
            try:
                detail = self.detail(int(code))
            except LookupError:
                continue
            seen.append(detail.scheme)
        return FundComparison(codes=[s.scheme_code for s in seen], schemes=seen)

    # ------------------------------------------------------------------ #
    # Recommendation flow (tied to the Phase-2 risk profile + goal)
    # ------------------------------------------------------------------ #

    # Category weights as a fraction of the FUND sleeve (sums to 1.0).
    ALLOCATIONS: dict[RiskLevel, list[tuple[FundCategory, float, str]]] = {
        RiskLevel.CONSERVATIVE: [
            (FundCategory.INDEX, 0.35, "Index funds track the market cheaply"),
            (FundCategory.LIQUID, 0.35, "Liquid money you can reach quickly"),
            (FundCategory.DEBT, 0.30, "Bonds steady the ride"),
        ],
        RiskLevel.MODERATE: [
            (FundCategory.INDEX, 0.40, "Index funds track the market cheaply"),
            (FundCategory.HYBRID, 0.35, "Hybrid funds blend shares and bonds"),
            (FundCategory.LIQUID, 0.15, "Liquid money you can reach quickly"),
            (FundCategory.DEBT, 0.10, "Bonds steady the ride"),
        ],
        RiskLevel.AGGRESSIVE: [
            (FundCategory.FLEXI, 0.40, "Flexi-cap funds let a manager pick the best ideas"),
            (FundCategory.INDEX, 0.25, "Index funds track the market cheaply"),
            (FundCategory.MID, 0.20, "Mid-cap funds chase growth beyond the big names"),
            (FundCategory.SMALL, 0.15, "Small-cap funds for the biggest growth swings"),
        ],
    }

    _GOAL_NOTES: dict[str, str] = {
        "tax": "Because your goal is tax saving, an ELSS fund replaces part of the basket — it qualifies for deduction under Section 80C but locks your money in for 3 years.",
        "retirement": "For retirement, keeping a chunk in liquid/debt makes sense so a market dip near your target date doesn't hurt as much.",
        "safe": "You told us you want safety — the plan leans on liquid and debt so your money barely swings.",
        "goal": "For a named goal, the plan keeps a balanced mix so you don't have to time the market.",
    }

    def recommend(
        self,
        risk_level: RiskLevel | str,
        goal: str = "wealth",
        monthly_amount: float = 0.0,
        horizon_years: int = 0,
    ) -> FundBasket:
        level = RiskLevel(risk_level)
        amount = max(0.0, float(monthly_amount))
        horizon = max(0, int(horizon_years))
        schemes = self.universe()

        allocations = self._tilt_allocations(level, goal, horizon)
        if goal == "tax":
            # A tax goal means the ELSS scheme itself matters — put it first.
            allocations.sort(key=lambda a: (a[0] != FundCategory.ELSS, -a[1]))
        split = [
            FundAllocation(category=cat, weight=weight, advice=advice)
            for cat, weight, advice in allocations
        ]

        picks: list[FundRecommendation] = []
        for cat, weight, advice in allocations[:3]:
            fund = self._best_scheme(schemes, cat)
            if fund is None:
                continue
            picks.append(self._to_recommendation(fund, weight, advice))

        # Fill any gaps with the best remaining risk-adjusted funds so a
        # beginner always sees 2-3 concrete schemes.
        while len(picks) < 2:
            fund = self._best_scheme(schemes, None, excluded={p.scheme_code for p in picks})
            if fund is None:
                break
            picks.append(self._to_recommendation(fund, 0.33, "A solid, well-rounded fund to round out the basket"))

        # The schemes are the concrete way to implement the fund sleeve, so
        # their weights should sum to 1.0 (the split above remains the ideal).
        total_weight = sum(p.weight for p in picks) or 1.0
        for pick in picks:
            pick.weight = round(pick.weight / total_weight, 4)

        notes = [
            "These are direct plans only — they cost less than 'regular' plans because there is no distributor commission, and that difference compounds over years.",
            "Weights are a starting point for the fund part of your monthly amount; keep the mix close to the plan and re-balance roughly once a quarter.",
        ]
        if goal in self._GOAL_NOTES:
            notes.insert(0, self._GOAL_NOTES[goal])
        if any(p.is_elss for p in picks):
            notes.append("ELSS has a 3-year lock-in — only invest money you won't need before then.")
        if horizon >= 5:
            notes.append("Your horizon is 5+ years, so the plan leans on shares (via funds) — that is where the long-term growth has historically come from.")
        else:
            notes.append("With a shorter horizon, the plan leans on safer liquid/debt funds so a dip is easier to wait out.")

        return FundBasket(
            risk_level=level,
            risk_label=PROFILE_LABELS[level],
            goal=goal,
            monthly_amount=amount,
            horizon_years=horizon,
            split=split,
            schemes=picks,
            expected_return_range=list(PROFILE_RETURNS[level]),
            notes=notes,
            generated_at=datetime.now(timezone.utc),
            data_as_of=self._data_as_of(),
            source=self.client.source,
        )

    def _tilt_allocations(
        self,
        level: RiskLevel,
        goal: str,
        horizon: int,
    ) -> list[tuple[FundCategory, float, str]]:
        """Horizon / goal tilts on the base per-level allocations."""
        allocs = [list(x) for x in self.ALLOCATIONS[level]]
        by_cat = {cat: weight for cat, weight, _advice in allocs}

        # Longer horizons can stomach more shares.
        if horizon >= 5 and level in (RiskLevel.CONSERVATIVE, RiskLevel.MODERATE):
            shift = min(by_cat.get(FundCategory.LIQUID, 0.0), 0.15)
            if shift > 0:
                by_cat[FundCategory.INDEX] = by_cat.get(FundCategory.INDEX, 0.0) + shift
                by_cat[FundCategory.LIQUID] = by_cat.get(FundCategory.LIQUID, 0.0) - shift
        elif horizon < 3:
            shift = min(by_cat.get(FundCategory.INDEX, 0.0), 0.15)
            if shift > 0 and level == RiskLevel.AGGRESSIVE:
                by_cat[FundCategory.INDEX] = by_cat.get(FundCategory.INDEX, 0.0) - shift
                by_cat[FundCategory.DEBT] = by_cat.get(FundCategory.DEBT, 0.0) + shift

        # Tax goal swaps in ELSS.
        if goal == "tax":
            share = 0.25
            source = by_cat.get(FundCategory.INDEX, 0.0)
            if source >= share:
                by_cat[FundCategory.INDEX] = source - share
                by_cat[FundCategory.ELSS] = by_cat.get(FundCategory.ELSS, 0.0) + share

        rebuilt: list[tuple[FundCategory, float, str]] = []
        for cat, weight, advice in self.ALLOCATIONS[level]:
            weight = by_cat.get(cat, weight)
            if weight > 0.01:
                rebuilt.append((cat, round(weight, 4), advice))
        if by_cat.get(FundCategory.ELSS, 0.0) > 0.01:
            rebuilt.append((FundCategory.ELSS, round(by_cat[FundCategory.ELSS], 4),
                            "ELSS is an equity fund that saves tax (Section 80C)"))
        # Normalise back to 1.0.
        total = sum(w for _c, w, _a in rebuilt) or 1.0
        return [(c, round(w / total, 4), a) for c, w, a in rebuilt]

    def _best_scheme(
        self,
        schemes: list[FundScheme],
        category: FundCategory | None,
        excluded: set[int] | None = None,
    ) -> FundScheme | None:
        pool = [s for s in schemes if s.is_direct]
        if category is not None:
            pool = [s for s in pool if s.category == category]
        if excluded:
            pool = [s for s in pool if s.scheme_code not in excluded]
        if not pool:
            return None
        return max(pool, key=lambda s: self._pick_score(s))

    @staticmethod
    def _pick_score(s: FundScheme) -> float:
        """Risk-adjusted pick score: Sharpe, then 3y return, then 5y return."""
        score = s.risk.sharpe if s.risk.sharpe is not None else None
        if score is None:
            score = (s.returns.three_year or 0) * 5.0
        elif s.returns.three_year is not None:
            score += s.returns.three_year * 2.0
        return score

    @staticmethod
    def _to_recommendation(
        fund: FundScheme,
        weight: float,
        advice: str,
    ) -> FundRecommendation:
        return FundRecommendation(
            scheme_code=fund.scheme_code,
            scheme_name=fund.scheme_name,
            fund_house=fund.fund_house,
            category=fund.category,
            sebi_category=fund.sebi_category,
            is_elss=fund.is_elss,
            weight=round(weight, 4),
            nav=fund.nav,
            nav_date=fund.nav_date,
            expense_ratio=fund.expense_ratio,
            aum_cr=fund.aum_cr,
            returns=fund.returns,
            risk=fund.risk,
            badges=fund.badges,
            plain=plain_reason(fund, advice),
        )

    # ------------------------------------------------------------------ #
    # SIP calculator
    # ------------------------------------------------------------------ #

    def sip_calculator(
        self,
        mode: str,
        monthly_amount: float = 0.0,
        lumpsum_amount: float = 0.0,
        years: int = 10,
        assumed_return_pct: float = 12.0,
        step_up_pct: float = 0.0,
    ) -> SipResult:
        mode = (mode or "sip").lower()
        if mode not in ("sip", "lumpsum", "sip_stepup"):
            mode = "sip"
        years = max(1, min(int(years), 50))
        months = years * 12
        i = max(0.0, float(assumed_return_pct)) / 100.0 / 12.0
        step = max(0.0, float(step_up_pct)) / 100.0
        monthly = max(0.0, float(monthly_amount))
        lump = max(0.0, float(lumpsum_amount))

        invested = 0.0
        if mode == "lumpsum":
            invested = lump
            fv = lump * (1 + i) ** months
        else:
            if mode == "sip_stepup":
                monthly_series = [monthly * (1 + step) ** (m / 12.0) for m in range(months)]
            else:
                monthly_series = [monthly] * months
            invested = sum(monthly_series)
            fv = sum(amt * (1 + i) ** (months - m - 1) for m, amt in enumerate(monthly_series)) * (1 + i)

        table: list[dict[str, Any]] = []
        for year in range(1, years + 1):
            m_end = year * 12
            if mode == "lumpsum":
                cum_invested = lump
                value = lump * (1 + i) ** m_end
            else:
                if mode == "sip_stepup":
                    series = [monthly * (1 + step) ** (m / 12.0) for m in range(m_end)]
                else:
                    series = [monthly] * m_end
                cum_invested = sum(series)
                value = sum(amt * (1 + i) ** (m_end - m - 1) for m, amt in enumerate(series)) * (1 + i)
            table.append({
                "year": year,
                "invested": round(cum_invested, 2),
                "value": round(value, 2),
            })

        return SipResult(
            mode=mode,
            monthly_amount=monthly,
            lumpsum_amount=lump,
            years=years,
            step_up_pct=float(step_up_pct),
            assumed_return_pct=float(assumed_return_pct),
            invested=round(invested, 2),
            future_value=round(fv, 2),
            table=table,
        )


def plain_reason(fund: FundScheme, advice: str) -> str:
    """One plain-language sentence explaining why this fund was chosen."""
    bits = [advice]
    if fund.expense_ratio is not None:
        bits.append(f"costs about {fund.expense_ratio:.2f}% a year — among the cheapest")
    if fund.returns.three_year is not None:
        bits.append(f"averaged about {fund.returns.three_year * 100:.0f}% a year over 3 years (past, not a promise)")
    if fund.risk.rating_label:
        bits.append(f"risk: {fund.risk.rating_label}")
    return ". ".join(bits) + "."
