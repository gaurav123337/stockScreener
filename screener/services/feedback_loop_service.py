"""Feedback Loop Service — instrument outcomes, suggest weight changes (Phase 5).

The honest version of "AI gets smarter": we log every signal, evaluate it at
maturity, and compare score bands against realized outcomes. If high-score
signals outperform low-score ones, the scoring model is predictive and the
weights are left alone; if the relationship inverts or flattens, the loop
*suggests* rebalancing pillar weights — never applies them silently. Suggested
changes are published through the changelog so users can see exactly what
moved and why.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from screener.core.config import config
from screener.core.container import container
from screener.core.interfaces import PredictionRepository
from screener.core.models import Outcome, PredictionRecord
from screener.core.subscription_models import (
    ChangelogEntry,
    SubscriptionStore,
    subscription_store,
)
from screener.core.user_models import UserProfile


# Pillar weight buckets in ScoringConfig, in score-point terms.
PILLAR_KEYS: dict[str, list[str]] = {
    "trend": ["trend_weight_sma50", "trend_weight_sma200", "trend_weight_cross"],
    "momentum": ["momentum_weight_rsi", "momentum_weight_macd", "momentum_weight_crossover"],
    "volume": ["volume_weight"],
    "fundamentals": ["fundamental_peg_weight", "fundamental_roe_weight", "fundamental_debt_weight"],
}


WIN_OUTCOMES = {Outcome.CORRECT, Outcome.TARGET_HIT}


class FeedbackLoopService:
    """Reads realized outcomes and produces transparent weight suggestions."""

    def __init__(
        self,
        repo: PredictionRepository | None = None,
        store: SubscriptionStore | None = None,
    ):
        self._repo = repo
        self._store = store or subscription_store

    def _prediction_repo(self) -> PredictionRepository:
        if self._repo is None:
            return container.resolve(PredictionRepository)
        return self._repo

    # ------------------------------------------------------------------- stats

    def outcome_stats(self) -> dict[str, Any]:
        """Per-band hit rates from matured predictions (the instrumentation)."""
        records = [r for r in self._prediction_repo().get_all() if r.evaluated]
        if not records:
            return self._empty_stats()

        wins = sum(1 for r in records if r.outcome in WIN_OUTCOMES)
        bands = {"high": [], "mid": [], "low": []}
        for r in records:
            band = self._band(r.score)
            bands[band].append(r)
        band_stats = {
            name: self._band_summary(rows)
            for name, rows in bands.items()
            if rows
        }

        by_action: dict[str, dict[str, Any]] = {}
        for action, rows in _group(records, lambda r: r.action.value).items():
            by_action[action] = self._band_summary(rows)

        # How predictive is the score? Compare the high band against the low.
        high = band_stats.get("high")
        low = band_stats.get("low")
        predictive = None
        if high and low and high["n"] >= 5 and low["n"] >= 5:
            predictive = high["hit_rate"] - low["hit_rate"]

        return {
            "evaluated": len(records),
            "overall_hit_rate": round(wins / len(records), 3),
            "by_score_band": band_stats,
            "by_action": by_action,
            "score_predictiveness": predictive,
            "horizon_days": _common_horizon(records),
            "window_start": min((r.eval_date or r.ts for r in records)),
            "generated_at": date.today().isoformat(),
        }

    def weight_suggestions(self) -> dict[str, Any]:
        """Suggested ScoringConfig changes, with reasoning and zero blind apply.

        The rule set is deliberately conservative:
          * only react to a predictive relationship (high band beats low band
            by a meaningful margin, or *worse* than the low band);
          * suggest nudging a single pillar's weight by a small delta;
          * always emit a human-readable rationale the PO can review.
        Suggestions are returned, not applied.
        """
        stats = self.outcome_stats()
        if stats["evaluated"] < 20:
            return {
                "sufficient_data": False,
                "evaluated": stats["evaluated"],
                "suggestions": [],
                "message": "Not enough matured signals to justify a weight change yet.",
            }

        predictive = stats.get("score_predictiveness")
        suggestions: list[dict[str, Any]] = []
        if predictive is None:
            message = "No stable relationship between score and outcome — keep weights as-is."
        elif predictive > 0.05:
            message = "High-score signals are beating low-score ones — weights are working."
        elif predictive < -0.05:
            suggestions.append({
                "pillar": "trend",
                "current_weight": self._pillar_total("trend"),
                "suggested_weight": round(self._pillar_total("trend") - 5, 1),
                "direction": "decrease",
                "reason": (
                    "High-score signals underperform low-score ones; the trend pillar "
                    "may be overweighting what the market is not paying for."
                ),
            })
            message = "Inverted predictiveness — a modest trend re-weight is suggested."
        else:
            message = "Flat predictiveness — the score does not discriminate yet; revisit after more data."

        return {
            "sufficient_data": True,
            "evaluated": stats["evaluated"],
            "score_predictiveness": predictive,
            "suggestions": suggestions,
            "message": message,
            "pillar_totals": {k: self._pillar_total(k) for k in PILLAR_KEYS},
            "generated_at": date.today().isoformat(),
        }

    # ----------------------------------------------------------------- publish

    def publish_change(self, user: UserProfile, payload: dict[str, Any]) -> ChangelogEntry:
        """Record a reviewed weight change so it is publicly auditable."""
        entry = ChangelogEntry(
            entry_id=_slug_id(payload.get("title", "scoring-update")),
            version=payload.get("version") or "1.0.0",
            date=payload.get("date") or date.today().isoformat(),
            title=payload["title"],
            summary=payload.get("summary") or "",
            weight_changes=payload.get("weight_changes") or {},
        )
        self._store.upsert_changelog(entry)
        return entry

    def changelog(self) -> list[dict[str, Any]]:
        return [e.model_dump(mode="json") for e in self._store.list_changelog()]

    # ------------------------------------------------------------------- util

    @staticmethod
    def _band(score: float | None) -> str:
        if score is None:
            return "mid"
        if score >= 20:
            return "high"
        if score <= -20:
            return "low"
        return "mid"

    @staticmethod
    def _band_summary(rows: list[PredictionRecord]) -> dict[str, Any]:
        n = len(rows)
        wins = sum(1 for r in rows if r.outcome in WIN_OUTCOMES)
        return {
            "n": n,
            "hit_rate": round(wins / n, 3) if n else None,
            "avg_return_pct": round(sum(r.return_pct or 0.0 for r in rows) / n, 3) if n else None,
        }

    @staticmethod
    def _empty_stats() -> dict[str, Any]:
        return {
            "evaluated": 0,
            "overall_hit_rate": None,
            "by_score_band": {},
            "by_action": {},
            "score_predictiveness": None,
            "horizon_days": None,
            "window_start": None,
            "generated_at": date.today().isoformat(),
        }

    def _pillar_total(self, pillar: str) -> float:
        return round(sum(getattr(config.scoring, k, 0.0) for k in PILLAR_KEYS[pillar]), 1)


def _group(records, key):
    out: dict[Any, list] = {}
    for r in records:
        out.setdefault(key(r), []).append(r)
    return out


def _common_horizon(records: list[PredictionRecord]) -> int | None:
    counts = Counter(r.horizon_days for r in records)
    return max(counts, key=counts.get) if counts else None


def _slug_id(title: str) -> str:
    base = "".join(ch for ch in title.lower() if ch.isalnum() or ch in "-_ ").strip().replace(" ", "-")
    return (base or "change")[:60]


# Global instance
feedback_loop_service = FeedbackLoopService()
