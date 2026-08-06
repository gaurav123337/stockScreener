"""Plan Service — goal-based starter basket generator.

Given a risk profile + monthly amount + horizon + goal, returns:
- the same asset split as the profile,
- a starter basket of 3-5 diversified stocks picked by the same signal
  engine that powers recommendations (sector-diversified, score-weighted),
- plain-language mutual-fund suggestions for the fund sleeve,
- expected vs conservative return ranges (clearly labeled assumptions),
- practical notes (quarterly rebalancing, diversification).

This is the Smallcase/NAPS-style "here's where to start" play: a beginner
gets a few understandable holdings with reasons, not a jargon dump.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from screener.core.config import AppConfig, config
from screener.core.models import (
    Action,
    InvestmentPlan,
    PlanBasketItem,
    Recommendation,
    RiskLevel,
)
from screener.services.analysis_service import AnalysisService
from screener.services.plain_language import build_thesis
from screener.services.risk_profile_service import (
    PROFILE_LABELS,
    PROFILE_RETURNS,
    PROFILE_SPLITS,
)

# Curated, liquid, sector-diverse blue-chip candidates. Deliberately a small
# set so the first plan builds fast — good enough for a beginner starter
# basket, and always scored live by the real engine (no hand-picked picks).
CANDIDATE_UNIVERSE: list[str] = [
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "ITC",
    "HINDUNILVR", "LT", "AXISBANK", "BHARTIARTL", "MARUTI", "ASIANPAINT",
    "SUNPHARMA", "TITAN", "WIPRO", "NTPC", "POWERGRID", "TATAMOTORS", "HCLTECH",
]

_FUND_BY_LEVEL: dict[RiskLevel, list[str]] = {
    RiskLevel.CONSERVATIVE: [
        "Liquid / overnight mutual fund (park money safely, easy to withdraw)",
        "Short-duration debt fund (modest returns, low swings)",
    ],
    RiskLevel.MODERATE: [
        "Aggressive hybrid fund (a balanced mix of shares and bonds)",
        "Large-cap equity fund (steady, blue-chip companies)",
    ],
    RiskLevel.AGGRESSIVE: [
        "Flexi-cap equity fund (fund manager picks the best ideas)",
        "Mid-cap equity fund (higher risk, higher growth potential)",
    ],
}

_TAX_FUND = "ELSS fund — tax saving under 80C, with a 3-year lock-in period"

# Conservative long-run view ranges (nominal, p.a.) — clearly assumptions,
# shown as "expected" vs "conservative" so the user sees the spread.
RETURN_RANGES: dict[RiskLevel, list[float]] = dict(PROFILE_RETURNS)
CONSERVATIVE_RETURN_RANGES: dict[RiskLevel, list[float]] = {
    RiskLevel.CONSERVATIVE: [0.04, 0.07],
    RiskLevel.MODERATE: [0.05, 0.09],
    RiskLevel.AGGRESSIVE: [0.06, 0.10],
}


class PlanService:
    """Build a beginner-friendly investment plan from a risk profile."""

    def __init__(self, analysis_service: AnalysisService | None = None):
        self._analysis = analysis_service or AnalysisService()

    # ------------------------------------------------------------------ #
    # Public entry point
    # ------------------------------------------------------------------ #

    def build_plan(
        self,
        risk_level: RiskLevel | str,
        monthly_amount: float,
        horizon_years: int,
        goal: str = "wealth",
        app_config: AppConfig | None = None,
    ) -> InvestmentPlan:
        level = RiskLevel(risk_level)
        effective = app_config or config
        amount = max(0.0, float(monthly_amount))
        horizon = max(0, int(horizon_years))

        picks = self._pick_basket(self._analysis, effective)
        weights = self._weights(picks)

        basket: list[PlanBasketItem] = []
        for rec, weight in zip(picks, weights, strict=False):
            thesis = build_thesis(rec)
            highlights = [
                f"{d.label}: {d.plain}" for d in thesis.drivers if d.positive is True
            ][:2]
            basket.append(
                PlanBasketItem(
                    symbol=rec.symbol,
                    name=rec.metrics.name,
                    sector=rec.metrics.sector,
                    role=thesis.portfolio_role or "",
                    weight=weight,
                    score=rec.score,
                    action=rec.action,
                    price=rec.price,
                    plain=thesis.thesis or "",
                    risk_badge=thesis.risk_badge,
                    driver_highlights=highlights,
                )
            )

        funds = list(_FUND_BY_LEVEL[level])
        if goal == "tax":
            funds = [_TAX_FUND] + [f for f in funds if f != _TAX_FUND]

        notes = [
            "Re-balance roughly once a quarter: sell a bit of what grew fast and add to what lagged, to keep your mix close to the plan.",
            "The basket is sector-diversified so one bad industry doesn't sink the plan.",
            f"You'd invest about ₹{amount:,.0f} a month. In {max(horizon, 1)} years at the expected rate this is a starting point — increase as your income grows.",
            "Mutual-fund part handles the rest of the diversification for you; the fund examples are starting points to research, not endorsements.",
        ]

        return InvestmentPlan(
            risk_level=level,
            risk_label=PROFILE_LABELS[level],
            goal=goal,
            monthly_amount=amount,
            horizon_years=horizon,
            asset_split=dict(PROFILE_SPLITS[level]),
            basket=basket,
            mutual_funds=funds,
            expected_return_range=list(RETURN_RANGES[level]),
            conservative_return_range=list(CONSERVATIVE_RETURN_RANGES[level]),
            notes=notes,
            generated_at=datetime.now(),
        )

    # ------------------------------------------------------------------ #
    # Basket selection
    # ------------------------------------------------------------------ #

    def _pick_basket(
        self,
        analysis: AnalysisService,
        app_config: AppConfig,
    ) -> list[Recommendation]:
        """Score the candidate universe, keep BUY signals, diversify by sector."""
        recs: list[Recommendation] = []
        for symbol in CANDIDATE_UNIVERSE:
            try:
                rec = analysis.analyze(symbol, app_config)
            except Exception:
                continue
            if rec.error is None and rec.action == Action.BUY:
                recs.append(rec)

        recs.sort(key=lambda r: r.score, reverse=True)

        picked: list[Recommendation] = []
        used_sectors: set[str] = set()
        for rec in recs:
            sector = (rec.metrics.sector or "").strip().lower()
            if sector and sector in used_sectors:
                continue
            picked.append(rec)
            if sector:
                used_sectors.add(sector)
            if len(picked) >= 5:
                break

        # If fewer than 3 clear BUY signals, top up with the next-best scores
        # so a beginner still gets a diversified starting list.
        if len(picked) < 3:
            for rec in recs:
                if rec in picked:
                    continue
                picked.append(rec)
                if len(picked) >= 3:
                    break
        return picked[:5]

    @staticmethod
    def _weights(picks: list[Recommendation]) -> list[float]:
        """Score-based weights that sum to 1.0."""
        if not picks:
            return []
        total = sum(max(r.score, 0.0) for r in picks) or 1.0
        raw = [max(r.score, 0.0) / total for r in picks]
        total = sum(raw)
        raw = [w / total for w in raw]
        raw[-1] = round(1.0 - sum(raw[:-1]), 4)
        return raw
