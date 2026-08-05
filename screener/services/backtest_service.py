"""Backtest Service — walk-forward replay that produces the published track record.

The product's "AI" is only honest when it sits on real, dated evidence. This
service replays the exact same AnalysisService signal logic across the NIFTY50
universe over the last ~2.5 years, sampling a signal every 21 calendar days per
symbol (no lookahead: indicators at time t only use data up to t), and measures
each signal against every configured horizon. The resulting report is cached to
disk and published via GET /api/backtest.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from screener.core.config import config
from screener.core.container import container
from screener.core.indicators import add_all
from screener.core.interfaces import MarketDataProvider
from screener.core.models import BacktestReport, HorizonStats, PredictionRecord
from screener.services.evaluation import asof_close, horizon_stats, load_benchmark
from screener.services.scoring_engine import ScoringEngine


class BacktestService:
    """Replays the signal engine over history and publishes the results."""

    def __init__(
        self,
        data_provider: MarketDataProvider | None = None,
        scoring_engine: ScoringEngine | None = None,
        report_file: str | None = None,
    ):
        self._data = data_provider or container.resolve(MarketDataProvider)
        self._engine = scoring_engine or ScoringEngine(use_registry=False)
        self._report_file = report_file or str(config.backtest_report_file)

    # ------------------------------------------------------------------- public

    def get(self) -> BacktestReport:
        """Return the published report, (re)generating it when stale/missing."""
        cached = self._load_cache()
        if cached is not None:
            age = datetime.now(timezone.utc) - _as_utc(cached.generated_at)
            if age.total_seconds() < config.backtest.cache_ttl_seconds:
                return cached
        return self.run()

    def run(self) -> BacktestReport:
        """Run (or re-run) the walk-forward replay and persist the report."""
        report, _records = self._replay()
        self._save_cache(report)
        return report

    def replay_records(self) -> list[PredictionRecord]:
        """Run the walk-forward replay and return its raw signal records.

        Also caches the aggregated report so /api/backtest stays warm. The
        records let the verification service backfill the historical track
        record into the live log (labeled ``system/backtest``), so /api/verify
        shows dated, nonzero results from day one.
        """
        report, records = self._replay()
        self._save_cache(report)
        return records

    # ------------------------------------------------------------------- replay

    def _replay(self) -> tuple[BacktestReport, list[PredictionRecord]]:
        today = date.today()
        start = datetime.strptime(config.backtest.start_date, "%Y-%m-%d").date()
        horizons = list(config.verification.horizons)
        max_h = max(horizons)

        engine = ScoringEngine(
            use_registry=False,
            scoring_config=config.scoring,
        )

        eval_dates = self._eval_dates(start, today, max_h)
        data = self._load_universe_data()

        benchmark = load_benchmark(self._data, config.verification.benchmark_symbol)

        samples: dict[int, list[tuple[PredictionRecord, float]]] = {
            h: [] for h in horizons
        }
        records: list[PredictionRecord] = []
        signals = 0
        for symbol, df in data.items():
            if df is None or df.empty:
                continue
            info = self._safe_info(symbol)
            last_idx = pd.to_datetime(df.index)
            for t in eval_dates:
                pos = last_idx.searchsorted(pd.Timestamp(t), side="right") - 1
                if pos < 1:
                    continue
                on = last_idx[pos]
                if on < pd.Timestamp(start):
                    continue
                last, prev = df.iloc[pos], df.iloc[pos - 1]
                try:
                    score, _ = engine.total_score(last, prev, info)
                    confidence = engine.confidence(
                        last, prev, info, apply_age_penalty=False
                    )
                except Exception:  # noqa: BLE001 — skip glitchy rows
                    continue
                score = float(max(-100, min(100, score)))
                if score >= config.scoring.buy_threshold:
                    action = "BUY"
                elif score <= config.scoring.sell_threshold:
                    action = "SELL"
                else:
                    action = "HOLD"

                rec = PredictionRecord(
                    ts=pd.Timestamp(on).to_pydatetime().replace(tzinfo=None),
                    symbol=symbol,
                    action=action,
                    price_at_call=float(last["Close"]),
                    horizon_days=max_h,
                    score=score,
                    confidence=confidence,
                )
                records.append(rec)
                signals += 1
                for h in horizons:
                    end = on + timedelta(days=h)
                    if end.date() > today:
                        continue
                    price = asof_close(df, end.date())
                    if price is None:
                        continue
                    samples[h].append((rec, price))

        stats = [horizon_stats(h, samples[h], benchmark) for h in horizons]
        report = BacktestReport(
            generated_at=datetime.now(timezone.utc),
            window_start=datetime.combine(start, datetime.min.time()),
            window_end=datetime.combine(today, datetime.min.time()),
            universe=list(data.keys()),
            universe_size=len(data),
            horizons=stats,
            methodology=[
                f"Walk-forward replay of the exact production signal engine",
                f"Universe: {len(data)} NIFTY50 constituents",
                f"One signal sampled per symbol every {config.backtest.sample_every_days} days from {start}",
                f"Indicators at time t use only data up to t (no lookahead)",
                f"Each signal measured at {len(horizons)} horizons: {', '.join(f'{h}d' for h in horizons)}",
                "HOLD counted as correct when the stock stayed within +-2% (stayed flat)",
                f"Benchmark: {config.verification.benchmark_symbol} buy-and-hold over the same windows",
            ],
            notes=[
                f"Current fundamentals (P/E, ROE) at the replay date are used throughout — "
                "historical fundamentals are not yet backfilled, a known caveat.",
                f"Signals evaluated: {signals}; counts below reflect only horizons that have elapsed.",
                "No fees, slippage, or taxes are modelled. Past performance is not a guarantee of future results.",
            ],
        )
        return report, records

    # ----------------------------------------------------------------- helpers

    def _eval_dates(self, start: date, today: date, max_h: int) -> list[date]:
        last_allowed = today - timedelta(days=max_h)
        if last_allowed <= start:
            return []
        dates = list(pd.bdate_range(start=start, end=last_allowed).date)
        return dates[:: config.backtest.sample_every_days]

    def _load_universe_data(self) -> dict[str, pd.DataFrame | None]:
        out: dict[str, pd.DataFrame | None] = {}
        for symbol in config.backtest.universe:
            try:
                raw = self._data.fetch_history(symbol, period="5y")
            except Exception:  # noqa: BLE001
                raw = None
            if raw is None or raw.empty:
                out[symbol] = None
                continue
            raw = raw.dropna(subset=["Close"])
            if len(raw) < config.data.min_history_rows:
                out[symbol] = None
                continue
            out[symbol] = add_all(raw)
        return out

    def _safe_info(self, symbol: str) -> dict:
        try:
            return self._data.fetch_info(symbol) or {}
        except Exception:  # noqa: BLE001
            return {}

    # ------------------------------------------------------------------ cache

    def _load_cache(self) -> BacktestReport | None:
        from pathlib import Path

        path = Path(self._report_file)
        if not path.exists():
            return None
        try:
            return BacktestReport.model_validate_json(path.read_text())
        except Exception:  # noqa: BLE001
            return None

    def _save_cache(self, report: BacktestReport) -> None:
        from pathlib import Path

        path = Path(self._report_file)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(report.model_dump_json(indent=2))
        except Exception:  # noqa: BLE001
            pass


def _as_utc(dt: datetime) -> datetime:
    """Normalize a possibly-naive timestamp to aware UTC for age math."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
