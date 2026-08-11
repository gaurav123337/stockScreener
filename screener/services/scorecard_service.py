"""Scorecard & Success Stories Service — proof layer (Phase 5).

Stockopedia's NAPS model is the reference: instead of vague "thousands of
happy users", publish dated, auditable evidence. The monthly scorecard derives
from the walk-forward backtest + live verification log — the exact numbers the
product actually produced. Success stories are explicitly illustrative
educational walkthroughs (never fabricated claims of individual returns), which
keeps the proof honest and compliant.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from screener.core.config import config
from screener.core.container import container
from screener.core.models import BacktestReport, VerificationReport
from screener.services.backtest_service import BacktestService
from screener.services.verification_service import VerificationService

import json
from pathlib import Path

# --------------------------------------------------------------------------- #
# Illustrative stories — labeled as such; never presented as real users.
# --------------------------------------------------------------------------- #

STORIES: list[dict[str, Any]] = [
    {
        "id": "story-startup-sip",
        "kind": "illustrative",
        "title": "Turning a SIP into a systematic review habit",
        "persona": "A 27-year-old starting a \u20b910,000/month equity SIP",
        "walkthrough": (
            "They completed the risk profile (moderate), picked a goal with a "
            "10-year horizon, and let the goal planner build a starter basket. "
            "Each month they re-run their saved screen and check the mutual-fund "
            "basket's allocation drift once a quarter. The habit \u2014 not any single "
            "pick \u2014 is what keeps the plan on track."
        ),
        "lesson": "Consistency beats stock-picking for beginners; reviews keep allocation honest.",
        "illustrative": True,
    },
    {
        "id": "story-conservative-rebalance",
        "kind": "illustrative",
        "title": "A conservative investor who never sold during a drawdown",
        "persona": "A 45-year-old, 60% equity / 40% debt allocation",
        "walkthrough": (
            "By sizing equity so that a 30% drawdown was survivable on paper, this "
            "profile treated the market dip as a rebalancing opportunity rather than "
            "a panic trigger. The plan review keeps a quarterly check: drift beyond "
            "5% triggers a rebalance back to target."
        ),
        "lesson": "Allocation sizing \u2014 not prediction \u2014 is what lets you stay invested.",
        "illustrative": True,
    },
    {
        "id": "story-tax-aware-elss",
        "kind": "illustrative",
        "title": "Using ELSS to fill the 80C equity sleeve",
        "persona": "A taxpayer building a long-horizon 80C plan",
        "walkthrough": (
            "After comparing ELSS vs PPF in the guide, this plan uses ELSS for the "
            "equity sleeve of Section 80C and PPF for the safety sleeve \u2014 matching "
            "the split to a moderate risk profile. The fund screener's ELSS badge "
            "and expense-ratio filter narrowed the shortlist before deciding."
        ),
        "lesson": "80C is a portfolio decision \u2014 blend instruments to your risk profile, not one pick.",
        "illustrative": True,
    },
]


class ScorecardService:
    """Publishes the monthly proof: a dated scorecard from real data."""

    def __init__(
        self,
        backtest_service: BacktestService | None = None,
        verification_service: VerificationService | None = None,
        cache_file: str | None = None,
    ):
        self._backtest = backtest_service
        self._verification = verification_service
        self._cache_file = Path(
            cache_file or str(config.scorecard_cache_file)
        )

    def _backtest_service(self) -> BacktestService:
        if self._backtest is None:
            return container.resolve(BacktestService)
        return self._backtest

    def _verification_service(self) -> VerificationService:
        if self._verification is None:
            return container.resolve(VerificationService)
        return self._verification

    def monthly_scorecard(self) -> dict[str, Any]:
        """Return the published monthly scorecard.

        Fast path: the scorecard is cached to disk and only regenerates when
        the cached period differs from the current month. A cold-cache build
        uses only the cached backtest report (no network); the full live
        verification pass is reserved for the admin ``refresh`` endpoint so the
        GET stays responsive. Either way the payload is a dated snapshot.
        """
        period = datetime.now(timezone.utc).strftime("%Y-%m")
        cached = self._load_cache()
        if cached and cached.get("period") == period:
            return cached
        scorecard = self._build(period, include_live=False)
        self._save_cache(scorecard)
        return scorecard

    def refresh(self) -> dict[str, Any]:
        """Force a fresh monthly scorecard including live verification.

        Used by the protected product-owner route; this is the slow path that
        touches the network.
        """
        period = datetime.now(timezone.utc).strftime("%Y-%m")
        scorecard = self._build(period, include_live=True)
        self._save_cache(scorecard)
        return scorecard

    def _build(self, period: str, include_live: bool = True) -> dict[str, Any]:
        report: BacktestReport = self._backtest_service().get()
        verify: VerificationReport | None = None
        if include_live:
            try:
                verify = self._verification_service().verify()
            except Exception:
                verify = None

        now = datetime.now(timezone.utc)
        horizon_cards = []
        for h in report.horizons:
            horizon_cards.append({
                "horizon_days": h.horizon_days,
                "n": h.n,
                "hit_rate": h.hit_rate,
                "avg_return": h.avg_return,
                "benchmark_avg_return": h.benchmark_avg_return,
                "vs_benchmark": h.vs_benchmark,
                "max_drawdown": h.max_drawdown,
            })

        return {
            "period": period,
            "generated_at": now.isoformat(),
            "source": (
                "walk-forward backtest + live verification log"
                if include_live
                else "walk-forward backtest (live verification pending monthly refresh)"
            ),
            "universe_size": report.universe_size,
            "universe_coverage": report.universe_coverage,
            "window_start": report.window_start.isoformat() if report.window_start else None,
            "window_end": report.window_end.isoformat() if report.window_end else None,
            "horizons": horizon_cards,
            "live_evaluated": verify.total_evaluated if verify else None,
            "live_overall_hit_rate": verify.overall_hit_rate if verify else None,
            "benchmark_symbol": config.verification.benchmark_symbol,
            "methodology": report.methodology,
            "notes": report.notes,
            "disclaimer": (
                "Educational track record of a rule-based signal engine. No fees, "
                "slippage or taxes modelled. Past performance is not a guarantee of "
                "future results."
            ),
        }

    def success_stories(self) -> list[dict[str, Any]]:
        """Illustrative educational walkthroughs — never claimed as real users."""
        return list(STORIES)

    # ------------------------------------------------------------------- cache

    def _load_cache(self) -> dict[str, Any] | None:
        try:
            return json.loads(self._cache_file.read_text())
        except (OSError, ValueError):
            return None

    def _save_cache(self, scorecard: dict[str, Any]) -> None:
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            self._cache_file.write_text(json.dumps(scorecard, indent=2))
        except OSError:
            pass  # Cache is best-effort; a failed write must not break the API.


# Global instance
scorecard_service = ScorecardService()
