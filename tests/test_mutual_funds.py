"""Mutual-fund pillar tests — stubbed AMFI client (no network)."""
from __future__ import annotations

import json
from datetime import date, timedelta

import numpy as np
import pytest

from screener.core.config import config
from screener.core.mf_models import (
    FundCategory,
    FundScreenerRequest,
)
from screener.services.mutual_fund_service import (
    MutualFundService,
    classify,
    classify_name,
    classify_sebi,
    compute_returns,
    compute_risk,
    is_direct_name,
    match_metadata,
    normalize_history,
    plain_reason,
    risk_rating,
)

CATEGORY_FIXTURES = [
    ("large", "Equity Scheme - Large Cap Fund", 0.13, 0.12),
    ("mid", "Equity Scheme - Mid Cap Fund", 0.16, 0.16),
    ("small", "Equity Scheme - Small Cap Fund", 0.18, 0.22),
    ("flexi", "Equity Scheme - Flexi Cap Fund", 0.15, 0.14),
    ("elss", "Equity Scheme - ELSS", 0.15, 0.15),
    ("index", "Index Funds", 0.12, 0.11),
    ("liquid", "Liquid Funds", 0.065, 0.02),
    ("debt", "Debt Scheme - Corporate Bond Fund", 0.07, 0.05),
    ("hybrid", "Hybrid Scheme - Aggressive Hybrid Fund", 0.11, 0.10),
]

FUND_HOUSES = ["HDFC", "SBI", "ICICI Prudential", "Mirae Asset", "Axis", "Kotak", "UTI", "Nippon India", "DSP", "Tata"]

_CATEGORY_LABELS = {
    "large": "Large Cap Fund",
    "mid": "Mid Cap Fund",
    "small": "Small Cap Fund",
    "flexi": "Flexi Cap Fund",
    "elss": "ELSS Tax Saver Fund",
    "index": "Nifty 50 Index Fund",
    "liquid": "Liquid Fund",
    "debt": "Corporate Bond Fund",
    "hybrid": "Balanced Advantage Fund",
}

_FLAGSHIPS = {
    "flexi": "Parag Parikh Flexi Cap Fund",
    "liquid": "HDFC Liquid Fund",
    "index": "UTI Nifty 50 Index Fund",
    "hybrid": "HDFC Balanced Advantage Fund",
    "elss": "Mirae Asset ELSS Tax Saver Fund",
    "large": "SBI Bluechip Fund",
    "mid": "HDFC Mid-Cap Opportunities Fund",
    "small": "Nippon India Small Cap Fund",
    "debt": "HDFC Corporate Bond Fund",
}


@pytest.fixture(autouse=True)
def _isolate_disk_cache(tmp_path, monkeypatch):
    """Tests share the global MF disk cache; point it at a temp dir."""
    from screener.core.config import AppConfig

    mf_dir = tmp_path / "mf"
    monkeypatch.setattr(AppConfig, "mf_dir", property(lambda self: mf_dir))
    monkeypatch.setattr(AppConfig, "mf_master_file", property(lambda self: mf_dir / "master.json"))
    monkeypatch.setattr(AppConfig, "mf_universe_file", property(lambda self: mf_dir / "universe.json"))
    monkeypatch.setattr(AppConfig, "mf_scheme_dir", property(lambda self: mf_dir / "schemes"))
    monkeypatch.setattr(AppConfig, "mf_scheme_file", lambda self, code: mf_dir / "schemes" / f"{code}.json")
    yield


def _make_points(seed: int, years: int, cagr: float, vol: float) -> list[dict]:
    rng = np.random.default_rng(seed)
    start = date.today() - timedelta(days=int(years * 365.25))
    nav = 10.0
    points = []
    d = start
    n_days = int(years * 250)
    for _ in range(n_days):
        points.append({"date": d.isoformat(), "nav": round(nav, 4)})
        drift = (cagr - 0.5 * vol * vol) / 252.0
        nav *= float(np.exp(drift + vol / np.sqrt(252.0) * rng.standard_normal()))
        d += timedelta(days=1)
    return points


class StubAmfiClient:
    """Deterministic stand-in for AmfiClient (no network, no disk)."""

    source = "stub"

    def __init__(self, schemes_per_category: int = 6):
        self._schemes: dict[int, dict] = {}
        code = 100000
        for i, (_key, sebi, cagr, vol) in enumerate(CATEGORY_FIXTURES):
            for j in range(schemes_per_category):
                house = FUND_HOUSES[(i + j) % len(FUND_HOUSES)]
                if j == 0 and _key in _FLAGSHIPS:
                    base = _FLAGSHIPS[_key]
                else:
                    base = f"{house} {_CATEGORY_LABELS[_key]}"
                name = f"{base} - Direct Plan - Growth"
                self._schemes[code] = {
                    "schemeCode": code,
                    "schemeName": name,
                    "sebi": sebi,
                    "cagr": cagr,
                    "vol": vol,
                }
                code += 1

    def fetch_master(self):
        return [
            {"schemeCode": c, "schemeName": s["schemeName"], "isinGrowth": f"INF{c}"}
            for c, s in self._schemes.items()
        ], {"fetched_at": "2026-08-05T00:00:00+00:00"}

    def fetch_scheme(self, code: int):
        s = self._schemes.get(int(code))
        if s is None:
            return {}, {"error": "missing"}
        points = _make_points(int(code), years=16, cagr=s["cagr"], vol=s["vol"])
        return {
            "meta": {
                "scheme_name": s["schemeName"],
                "fund_house": s["schemeName"].split()[0],
                "scheme_category": s["sebi"],
                "isin_growth": f"INF{code}",
            },
            "data": points,
        }, {"fetched_at": "2026-08-05T00:00:00+00:00"}

    def data_as_of(self):
        return "2026-08-05T00:00:00+00:00"


@pytest.fixture(scope="module")
def service():
    svc = MutualFundService(client=StubAmfiClient())
    return svc


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #

def test_classify_name_buckets():
    assert classify_name("SBI Bluechip Fund - Direct Plan - Growth") == FundCategory.LARGE
    assert classify_name("HDFC Mid-Cap Opportunities Fund - Direct Plan - Growth") == FundCategory.MID
    assert classify_name("Nippon India Small Cap Fund - Direct Plan - Growth") == FundCategory.SMALL
    assert classify_name("Parag Parikh Flexi Cap Fund - Direct Plan - Growth") == FundCategory.FLEXI
    assert classify_name("Mirae Asset ELSS Tax Saver Fund - Direct Plan - Growth") == FundCategory.ELSS
    assert classify_name("UTI Nifty 50 Index Fund - Direct Plan - Growth") == FundCategory.INDEX
    assert classify_name("HDFC Liquid Fund - Direct Plan - Growth") == FundCategory.LIQUID
    assert classify_name("HDFC Corporate Bond Fund - Direct Plan - Growth") == FundCategory.DEBT
    assert classify_name("HDFC Balanced Advantage Fund - Direct Plan - Growth") == FundCategory.HYBRID


def test_classify_sebi_authoritative():
    assert classify_sebi("Equity Scheme - Large Cap Fund") == FundCategory.LARGE
    assert classify_sebi("Hybrid Scheme - Aggressive Hybrid Fund") == FundCategory.HYBRID
    assert classify(None, "Equity Scheme - Flexi Cap Fund") == FundCategory.FLEXI
    assert classify(FundCategory.OTHER, "Equity Scheme - ELSS") == FundCategory.ELSS


def test_direct_detection():
    assert is_direct_name("HDFC Flexi Cap Fund - Direct Plan - Growth")
    assert not is_direct_name("HDFC Flexi Cap Fund - Regular Plan - Growth")


# --------------------------------------------------------------------------- #
# Analytics
# --------------------------------------------------------------------------- #

def test_normalize_history_sorts_and_cleans():
    raw = [{"date": "02-01-2020", "nav": "100"}, {"date": "01-01-2020", "nav": "95"}, {"date": "03-01-2020", "nav": "bad"}]
    out = normalize_history(raw)
    assert [p["date"] for p in out] == ["2020-01-01", "2020-01-02"]
    assert out[0]["nav"] == 95.0


def test_compute_returns_and_risk():
    points = _make_points(42, years=12, cagr=0.15, vol=0.15)
    ret = compute_returns(points)
    assert ret.three_year is not None
    assert 0.05 < ret.three_year < 0.30
    assert ret.one_year is not None
    risk = compute_risk(points, ret)
    assert risk.rating is not None and 1 <= risk.rating <= 5
    assert risk.volatility_annual is not None
    assert risk.sharpe is not None
    assert risk.sortino is not None


def test_risk_rating_scale():
    assert risk_rating(0.02) == (1, "Low")
    assert risk_rating(0.25) == (5, "Very high")


# --------------------------------------------------------------------------- #
# Universe + screener
# --------------------------------------------------------------------------- #

def test_universe_is_direct_growth_and_categorised(service):
    universe = service.universe()
    assert 20 <= len(universe) <= 60
    assert all(s.is_direct for s in universe)
    cats = {s.category for s in universe}
    assert FundCategory.LARGE in cats and FundCategory.ELSS in cats and FundCategory.LIQUID in cats


def test_screener_category_filter(service):
    result = service.screener(FundScreenerRequest(category=FundCategory.ELSS, limit=200))
    assert result.total > 0
    assert all(s.category == FundCategory.ELSS for s in result.items)


def test_screener_expense_and_risk_filters(service):
    # Flagship names carry curated metadata; stub names generally do not, so
    # test the filter semantics against schemes that do have the fields.
    universe = service.universe()
    with_meta = [s for s in universe if s.expense_ratio is not None]
    assert with_meta, "expected at least one flagship with curated metadata"
    min_exp = max(s.expense_ratio for s in with_meta) + 0.01
    result = service.screener(FundScreenerRequest(max_expense_ratio=min_exp, limit=200))
    assert all(s.expense_ratio is None or s.expense_ratio <= min_exp for s in result.items)
    low_risk = service.screener(FundScreenerRequest(max_risk_rating=2, limit=200))
    assert all(s.risk.rating is None or s.risk.rating <= 2 for s in low_risk.items)


def test_screener_sorts_by_sharpe(service):
    result = service.screener(FundScreenerRequest(sort_by="sharpe", sort_dir="desc", limit=200))
    sharps = [s.risk.sharpe for s in result.items if s.risk.sharpe is not None]
    assert sharps == sorted(sharps, reverse=True)


def test_screener_pagination(service):
    all_items = service.screener(FundScreenerRequest(limit=200)).items
    page = service.screener(FundScreenerRequest(limit=5, offset=0))
    assert len(page.items) == 5
    assert page.total == len(all_items)


def test_screener_status_when_warming():
    class EmptyClient(StubAmfiClient):
        def fetch_master(self):
            return [], {"fetched_at": None}

    svc = MutualFundService(client=EmptyClient(schemes_per_category=0))
    result = svc.screener(FundScreenerRequest())
    assert result.stale is True
    assert "warming" in (result.note or "")


# --------------------------------------------------------------------------- #
# Recommendation flow
# --------------------------------------------------------------------------- #

def test_recommend_produces_2_3_direct_schemes(service):
    basket = service.recommend("conservative", goal="wealth", monthly_amount=10000, horizon_years=5)
    assert 2 <= len(basket.schemes) <= 3
    assert all(scheme.scheme_name for scheme in basket.schemes)
    assert all("DIRECT" in scheme.scheme_name.upper() for scheme in basket.schemes)
    total_weight = sum(s.weight for s in basket.schemes)
    assert abs(total_weight - 1.0) < 0.02


def test_recommend_split_has_weight_one_and_labels(service):
    for level in ("conservative", "moderate", "aggressive"):
        basket = service.recommend(level, goal="wealth", monthly_amount=5000, horizon_years=10)
        total = sum(a.weight for a in basket.split)
        assert abs(total - 1.0) < 1e-6, level
        assert basket.risk_label
        assert basket.expected_return_range
        assert all(a.advice for a in basket.split)


def test_recommend_conservative_tilts_liquid_index(service):
    basket = service.recommend("conservative", goal="wealth", monthly_amount=5000, horizon_years=10)
    weights = {a.category: a.weight for a in basket.split}
    assert weights[FundCategory.LIQUID] >= 0.2
    assert weights[FundCategory.INDEX] >= 0.3


def test_recommend_tax_goal_adds_elss(service):
    basket = service.recommend("moderate", goal="tax", monthly_amount=10000, horizon_years=5)
    cats = {a.category for a in basket.split}
    assert FundCategory.ELSS in cats
    notes = " ".join(basket.notes).lower()
    assert "lock" in notes
    assert any(scheme.is_elss for scheme in basket.schemes)


def test_recommend_long_horizon_tilts_more_equity(service):
    short = service.recommend("conservative", goal="wealth", monthly_amount=5000, horizon_years=2)
    long = service.recommend("conservative", goal="wealth", monthly_amount=5000, horizon_years=10)
    index_short = next(a.weight for a in short.split if a.category == FundCategory.INDEX)
    index_long = next(a.weight for a in long.split if a.category == FundCategory.INDEX)
    assert index_long > index_short


def test_recommend_plain_reasons(service):
    basket = service.recommend("aggressive", goal="wealth", monthly_amount=10000, horizon_years=7)
    for scheme in basket.schemes:
        assert scheme.plain
        assert any(b for b in scheme.badges) or scheme.expense_ratio is not None or scheme.returns.three_year is not None


# --------------------------------------------------------------------------- #
# Compare / detail
# --------------------------------------------------------------------------- #

def test_compare_returns_2_4_schemes(service):
    universe = service.universe()
    codes = [s.scheme_code for s in universe[:3]]
    comparison = service.compare(codes)
    assert 2 <= len(comparison.schemes) <= 3


def test_detail_returns_history(service):
    code = service.universe()[0].scheme_code
    detail = service.detail(code)
    assert detail.scheme.scheme_code == code
    assert len(detail.history) > 0
    assert "date" in detail.history[0] and "nav" in detail.history[0]


def test_detail_missing_scheme_raises(service):
    with pytest.raises(LookupError):
        service.detail(999999)


# --------------------------------------------------------------------------- #
# SIP calculator
# --------------------------------------------------------------------------- #

def _calc(service, **kwargs):
    return MutualFundService.sip_calculator(service, **kwargs)


def test_sip_calculator_correctness(service):
    result = _calc(service, mode="sip", monthly_amount=10000, years=10, assumed_return_pct=12)
    assert result.mode == "sip"
    assert result.invested == 1_200_000
    assert 2_000_000 < result.future_value < 3_000_000
    assert len(result.table) == 10
    assert result.table[-1]["invested"] == result.invested


def test_lumpsum_calculator(service):
    result = _calc(service, mode="lumpsum", lumpsum_amount=1_000_000, years=10, assumed_return_pct=12)
    assert result.future_value > 3_000_000
    assert result.invested == 1_000_000


def test_stepup_grows_investment(service):
    plain = _calc(service, mode="sip", monthly_amount=10000, years=10, assumed_return_pct=12)
    step = _calc(service, mode="sip_stepup", monthly_amount=10000, years=10, assumed_return_pct=12, step_up_pct=10)
    assert step.invested > plain.invested
    assert step.future_value > plain.future_value


# --------------------------------------------------------------------------- #
# Metadata + plain reason
# --------------------------------------------------------------------------- #

def test_metadata_matches_direct_flagships():
    meta = match_metadata("Parag Parikh Flexi Cap Fund - Direct Plan - Growth")
    assert meta.get("expense_ratio") is not None
    assert meta.get("aum_cr") is not None
    assert not match_metadata("Some Unknown Fund - Direct Plan - Growth")


def test_plain_reason_is_readable():
    from screener.core.mf_models import FundReturns, FundRisk, FundScheme

    fund = FundScheme(
        scheme_code=1,
        scheme_name="Test Fund - Direct Plan - Growth",
        category=FundCategory.INDEX,
        expense_ratio=0.25,
        returns=FundReturns(three_year=0.14),
        risk=FundRisk(rating_label="Moderate"),
    )
    reason = plain_reason(fund, "Index funds track the market cheaply")
    assert "0.25%" in reason
    assert "14%" in reason
    assert "Moderate" in reason


def test_status_reports_source_and_freshness(service):
    from datetime import datetime, timezone

    status = service.status()
    assert status["source"] == "stub"
    assert status["data_as_of"] == datetime(2026, 8, 5, tzinfo=timezone.utc)
    assert status["universe_size"] > 0
    assert status["categories"]


def test_fetch_master_accepts_bare_list_payload(tmp_path, monkeypatch):
    """Regression: mfapi.in serves the master as a bare JSON array."""
    from screener.core.config import AppConfig
    from screener.infrastructure.data.amfi_client import AmfiClient

    mf_dir = tmp_path / "mf"
    mf_dir.mkdir(exist_ok=True)
    master = mf_dir / "master.json"
    master.write_text(
        json.dumps(
            {
                "fetched_at": "2026-08-07T00:00:00+00:00",
                "payload": [
                    {"schemeCode": 1, "schemeName": "Test Fund - Direct Plan - Growth"},
                    {"schemeCode": 2, "schemeName": "Other Fund - Regular Plan - Growth"},
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(AppConfig, "mf_dir", property(lambda self: mf_dir))
    monkeypatch.setattr(AppConfig, "mf_master_file", property(lambda self: mf_dir / "master.json"))

    client = AmfiClient(base_url="http://invalid.local", cache_dir=mf_dir)

    class FailSession:
        def get(self, *args, **kwargs):
            raise OSError("offline")

    client.session = FailSession()
    items, meta = client.fetch_master()
    assert len(items) == 2
    assert items[0]["schemeCode"] == 1
    assert meta["stale"] is True


def test_fetch_master_accepts_dict_items_shape(tmp_path, monkeypatch):
    """Legacy dict shape ({items: [...]}) still works."""
    from screener.core.config import AppConfig
    from screener.infrastructure.data.amfi_client import AmfiClient

    mf_dir = tmp_path / "mf"
    mf_dir.mkdir(exist_ok=True)
    master = mf_dir / "master.json"
    master.write_text(
        json.dumps(
            {
                "fetched_at": "2026-08-07T00:00:00+00:00",
                "payload": {"items": [{"schemeCode": 9, "schemeName": "Dict Fund - Direct Plan"}]},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(AppConfig, "mf_dir", property(lambda self: mf_dir))
    monkeypatch.setattr(AppConfig, "mf_master_file", property(lambda self: mf_dir / "master.json"))

    client = AmfiClient(base_url="http://invalid.local", cache_dir=mf_dir)

    class FailSession:
        def get(self, *args, **kwargs):
            raise OSError("offline")

    client.session = FailSession()
    items, _meta = client.fetch_master()
    assert len(items) == 1
    assert items[0]["schemeCode"] == 9
