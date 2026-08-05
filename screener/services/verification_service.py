"""Verification Service — self-scoring of past signals.

Every logged signal produces one PredictionRecord per horizon. ``verify()``
recomputes each signal's outcome from historical prices as horizons elapse, so
the published hit-rates are dated and rolling rather than point-in-time guesses.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd

from screener.core.config import config
from screener.core.container import container
from screener.core.interfaces import MarketDataProvider, PredictionRepository
from screener.core.models import (
    Action,
    PredictionRecord,
    Recommendation,
    VerificationReport,
)
from screener.services.evaluation import (
    asof_close,
    evaluation_samples,
    horizon_stats,
    load_benchmark,
)


class VerificationService:
    """Logs and verifies predictions."""

    # User id stamped on the backfilled walk-forward replay so /api/verify can
    # show dated, nonzero results from day one while staying auditable.
    BACKTEST_USER = "system/backtest"

    def __init__(
        self,
        repository: PredictionRepository | None = None,
        data_provider: MarketDataProvider | None = None,
    ):
        self._repo = repository or container.resolve(PredictionRepository)
        self._data = data_provider or container.resolve(MarketDataProvider)

    # ------------------------------------------------------------------ logging

    def log_prediction(self, rec: Recommendation, user_id: str | None = None) -> None:
        """Persist a signal (BUY/SELL/HOLD) for later verification.

        All actions are stored so the track record is auditable — a HOLD that
        was right to avoid a loser should count, not just a BUY that went up.
        """
        if rec.error is not None or rec.price is None:
            return
        record = PredictionRecord(
            ts=datetime.now(),
            symbol=rec.symbol,
            action=rec.action,
            price_at_call=rec.price,
            target=rec.target,
            stop_loss=rec.stop_loss,
            horizon_days=config.verification.horizon_days,
            score=rec.score,
            confidence=rec.confidence,
            user_id=user_id,
        )
        self._repo.save(record)

    def log_recommendations(
        self, recs: list[Recommendation], user_id: str | None = None
    ) -> None:
        """Batch-log a set of signals, never failing the caller."""
        for rec in recs:
            try:
                self.log_prediction(rec, user_id)
            except Exception:  # noqa: BLE001 — logging must not break the request
                continue

    # ------------------------------------------------------------------- prices

    def get_current_price(self, symbol: str) -> float | None:
        """Fetch current price for a symbol via the data provider."""
        df = self._data.fetch_history(symbol, period="5d")
        if df is not None and not df.empty:
            return float(df["Close"].iloc[-1])
        return None

    def _history_for(self, symbol: str, span_days: int) -> pd.DataFrame | None:
        period = "5y" if span_days <= 365 * 3 else "max"
        return self._data.fetch_history(symbol, period=period)

    # ------------------------------------------------------------ backfill seed

    def has_backtest_seed(self) -> bool:
        """True when the walk-forward replay is already in the verification log."""
        return any(
            r.user_id == self.BACKTEST_USER for r in self._repo.get_all()
        )

    def seed_from_backtest(self, records: list[PredictionRecord]) -> int:
        """Persist the replay's signal records into the verification log.

        Records are stamped ``system/backtest`` and deduplicated by (ts, symbol)
        so restarts never double-count. Returns how many new rows were added.
        """
        existing = self._repo.get_all()
        seen = {
            (r.ts.replace(microsecond=0), r.symbol)
            for r in existing
            if r.user_id == self.BACKTEST_USER
        }
        added = 0
        for rec in records:
            rec.user_id = self.BACKTEST_USER
            key = (rec.ts.replace(microsecond=0), rec.symbol)
            if key in seen:
                continue
            self._repo.save(rec)
            seen.add(key)
            added += 1
        return added

    # --------------------------------------------------------------- evaluation

    def verify(self) -> VerificationReport:
        """Evaluate every logged signal over each configured horizon.

        The window is rolling: predictions whose horizon has not elapsed yet are
        excluded, and the numbers change as more history accrues.
        """
        records = self._repo.get_all()
        today = date.today()
        horizons = list(config.verification.horizons)

        samples = evaluation_samples(
            records,
            horizons,
            history_for=self._history_for,
            today=today,
        )

        benchmark = load_benchmark(self._data, config.verification.benchmark_symbol)
        # ``horizon_stats`` is both the shared helper and a model name; alias.
        compute = horizon_stats
        horizon_stats_list = [
            compute(h, samples[h], benchmark) for h in horizons
        ]

        window_start = None
        if records:
            window_start = min(r.ts for r in records)

        # Overall = the shortest (most mature) horizon, so the headline number
        # is the one with the most signal, and every signal counts once.
        mature = horizon_stats_list[0] if horizon_stats_list else None
        overall_hit_rate = mature.hit_rate if mature else None
        by_action = mature.by_action if mature else None
        evaluated = sum(1 for r in records if _has_elapsed(r.ts.date(), min(horizons), today))

        return VerificationReport(
            evaluated_now=len(records),
            total_evaluated=evaluated,
            overall_hit_rate=overall_hit_rate,
            by_action=by_action,
            horizons=horizon_stats_list,
            benchmark_symbol=config.verification.benchmark_symbol,
            window_start=window_start,
            generated_at=datetime.now(timezone.utc),
        )


def _has_elapsed(called_on: date, shortest_horizon: int, today: date) -> bool:
    from datetime import timedelta

    return (called_on + timedelta(days=shortest_horizon)) <= today
