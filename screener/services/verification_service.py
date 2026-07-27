"""Verification Service — self-scoring of past predictions."""
from __future__ import annotations

from datetime import date, datetime

from screener.core.config import config
from screener.core.container import container
from screener.core.interfaces import MarketDataProvider, PredictionRepository
from screener.core.models import (
    Action,
    Outcome,
    PredictionRecord,
    Recommendation,
    VerificationReport,
)


class VerificationService:
    """Logs and verifies predictions."""

    def __init__(
        self,
        repository: PredictionRepository | None = None,
        data_provider: MarketDataProvider | None = None,
    ):
        self._repo = repository or container.resolve(PredictionRepository)
        self._data = data_provider or container.resolve(MarketDataProvider)

    def log_prediction(self, rec: Recommendation) -> None:
        """Persist a BUY/SELL prediction for later verification."""
        if rec.action not in (Action.BUY, Action.SELL) or rec.price is None:
            return
        record = PredictionRecord(
            ts=datetime.now(),
            symbol=rec.symbol,
            action=rec.action,
            price_at_call=rec.price,
            target=rec.target,
            stop_loss=rec.stop_loss,
            horizon_days=config.verification.horizon_days,
        )
        self._repo.save(record)

    def get_current_price(self, symbol: str) -> float | None:
        """Fetch current price for a symbol via the data provider."""
        df = self._data.fetch_history(symbol, period="5d")
        if df is not None and not df.empty:
            return float(df["Close"].iloc[-1])
        return None

    def verify(self, price_fetcher: callable | None = None) -> VerificationReport:
        """Score all due predictions against current prices.

        Args:
            price_fetcher: Optional callable that takes a symbol and returns a price.
                           If None, uses the built-in data provider.
        """
        fetcher = price_fetcher or self.get_current_price
        due = self._repo.get_due()
        for record in due:
            price = fetcher(record.symbol)
            if price is None:
                continue
            outcome, ret = self._compute_outcome(
                record.action, record.price_at_call, price, record.target, record.stop_loss
            )
            record.evaluated = True
            record.eval_date = datetime.now()
            record.price_at_eval = price
            record.outcome = outcome
            record.return_pct = round(ret, 2)
            self._repo.update(record)

        all_records = self._repo.get_all()
        done = [r for r in all_records if r.evaluated]
        wins = [r for r in done if r.outcome in (Outcome.TARGET_HIT, Outcome.CORRECT)]

        by_action: dict[str, dict] = {}
        for action in (Action.BUY, Action.SELL):
            sub = [r for r in done if r.action == action]
            w = [r for r in sub if r.outcome in (Outcome.TARGET_HIT, Outcome.CORRECT)]
            by_action[action.value] = {
                "n": len(sub),
                "hit_rate": round(len(w) / len(sub) * 100, 1) if sub else None,
            }

        return VerificationReport(
            evaluated_now=len(due),
            total_evaluated=len(done),
            overall_hit_rate=round(len(wins) / len(done) * 100, 1) if done else None,
            by_action=by_action,
        )

    def _compute_outcome(
        self,
        action: Action,
        p0: float,
        p1: float,
        target: float | None,
        stop: float | None,
    ) -> tuple[Outcome, float]:
        """Determine if a prediction was correct."""
        ret = (p1 - p0) / p0 * 100 if action == Action.BUY else (p0 - p1) / p0 * 100

        if action == Action.BUY:
            if target and p1 >= target:
                return Outcome.TARGET_HIT, ret
            if stop and p1 <= stop:
                return Outcome.STOP_HIT, ret
        else:
            if target and p1 <= target:
                return Outcome.TARGET_HIT, ret
            if stop and p1 >= stop:
                return Outcome.STOP_HIT, ret

        return (Outcome.CORRECT if ret > 0 else Outcome.WRONG), ret
