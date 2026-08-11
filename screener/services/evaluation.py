"""Shared evaluation math for the verification & backtest services.

Both the live rolling verification (/api/verify) and the published walk-forward
backtest (/api/backtest) score the same thing: did the signal's expectation
materialise over each horizon? Keeping that math in one place guarantees the
two numbers are computed identically.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterable

import pandas as pd

from screener.core.models import HorizonStats, PredictionRecord


def asof_close(df: pd.DataFrame, on: date, index: pd.Index | None = None) -> float | None:
    """Last close on or before ``on`` (None when no data by then).

    ``index`` is an optional precomputed ``pd.DatetimeIndex`` of ``df.index``;
    pass it when calling this in a hot loop to avoid re-deriving it per call.
    Uses ``searchsorted`` so a whole evaluation runs in log-time, not by
    allocating a filtered DataFrame on every call.
    """
    if df is None or df.empty:
        return None
    idx = index if index is not None else pd.DatetimeIndex(df.index)
    pos = int(idx.searchsorted(pd.Timestamp(on), side="right")) - 1
    if pos < 0:
        return None
    return float(df["Close"].iloc[pos])


def max_drawdown(returns: list[float]) -> float | None:
    """Peak-to-trough max drawdown (negative fraction) of a return series."""
    if not returns:
        return None
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in returns:
        equity *= 1.0 + r
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)
    return round(max_dd, 4)


def _round(x: float | None, ndigits: int = 4) -> float | None:
    return round(x, ndigits) if x is not None else None


def horizon_stats(
    horizon_days: int,
    samples: list[tuple[PredictionRecord, float]],
    benchmark: pd.DataFrame | None = None,
) -> HorizonStats:
    """Aggregate statistics over ``samples`` = [(record, price_at_horizon)].

    ``benchmark`` (optional) is the index history used to compute the average
    buy-and-hold return over the same windows, for the vs-market comparison.
    """
    if not samples:
        return HorizonStats(horizon_days=horizon_days, n=0)

    returns = [rec.return_at(price) for rec, price in samples]
    hits = sum(1 for rec, price in samples if rec.directional_win(price))
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]

    avg_return = sum(returns) / len(returns)

    benchmark_avg = None
    if benchmark is not None and not benchmark.empty:
        bench_index = pd.DatetimeIndex(benchmark.index)
        bench = []
        for rec, _price in samples:
            end = rec.ts.date() + timedelta(days=horizon_days)
            b0 = asof_close(benchmark, rec.ts.date(), bench_index)
            b1 = asof_close(benchmark, end, bench_index)
            if b0 and b1 and b0 > 0:
                bench.append(b1 / b0 - 1.0)
        if bench:
            benchmark_avg = sum(bench) / len(bench)

    by_action: dict[str, dict[str, Any]] = {}
    for action in ("BUY", "SELL", "HOLD"):
        sub_returns = [
            rec.return_at(price)
            for rec, price in samples
            if rec.action.value == action
        ]
        if not sub_returns:
            continue
        sub_hits = sum(
            1 for rec, price in samples
            if rec.action.value == action and rec.directional_win(price)
        )
        by_action[action] = {
            "n": len(sub_returns),
            "hit_rate": round(sub_hits / len(sub_returns) * 100, 1),
            "avg_return": round(sum(sub_returns) / len(sub_returns), 4),
        }

    return HorizonStats(
        horizon_days=horizon_days,
        n=len(samples),
        hit_rate=round(hits / len(samples) * 100, 1),
        avg_return=_round(avg_return),
        avg_win=_round(sum(wins) / len(wins)) if wins else None,
        avg_loss=_round(sum(losses) / len(losses)) if losses else None,
        max_drawdown=max_drawdown(returns),
        benchmark_avg_return=_round(benchmark_avg),
        vs_benchmark=_round(avg_return - benchmark_avg) if benchmark_avg is not None else None,
        by_action=by_action,
    )


def load_benchmark(
    data_provider,
    symbol: str = "^NSEI",
) -> pd.DataFrame | None:
    """Buy-and-hold reference series for the vs-market comparison.

    Prefers the provider (so tests can inject a mock), then falls back to a
    direct yfinance pull so the numbers still work when the provider only
    knows equities. The fallback result is stored into the provider's history
    cache (when it has one) so repeat evaluations don't re-download a slow
    index series on every call.
    """
    df = None
    if data_provider is not None:
        try:
            df = data_provider.fetch_history(symbol, period="5y")
        except Exception:  # noqa: BLE001
            df = None
    if df is not None and not df.empty:
        return df
    try:
        import yfinance as yf

        raw = yf.download(
            symbol, period="5y", interval="1d", progress=False, auto_adjust=True
        )
        if raw is not None and not raw.empty:
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            # Persist into the provider's history cache so the next evaluation
            # reads the index from disk instead of hitting the network again.
            cache = getattr(data_provider, "_history", None)
            if cache is not None and hasattr(cache, "set"):
                try:
                    cache.set(symbol, "5y", "1d", raw)
                except Exception:  # noqa: BLE001
                    pass
            return raw
    except Exception:  # noqa: BLE001
        return None
    return None


def evaluation_samples(
    records: Iterable[PredictionRecord],
    horizons: list[int],
    history_for: callable,
    today: date,
) -> dict[int, list[tuple[PredictionRecord, float]]]:
    """Map horizon -> [(record, price at ts+horizon)] for elapsed horizons.

    ``history_for(symbol, max_span_days)`` returns the OHLCV DataFrame (with a
    ``Close`` column) covering up to today. Horizons that have not elapsed yet
    are skipped — the window is rolling, so the number stays honest and current.
    """
    out: dict[int, list[tuple[PredictionRecord, float]]] = {h: [] for h in horizons}
    max_h = max(horizons)
    cache: dict[str, pd.DataFrame | None] = {}
    indexes: dict[str, pd.Index] = {}

    for rec in records:
        if rec.symbol not in cache:
            df = history_for(rec.symbol, max_h)
            cache[rec.symbol] = df
            indexes[rec.symbol] = (
                pd.DatetimeIndex(df.index) if df is not None and not df.empty else pd.Index([])
            )
        df = cache.get(rec.symbol)
        index = indexes[rec.symbol]
        for h in horizons:
            end = rec.ts.date() + timedelta(days=h)
            if end > today:
                continue
            price = asof_close(df, end, index)
            if price is None:
                continue
            out[h].append((rec, price))
    return out
