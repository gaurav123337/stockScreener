"""Tests for the walk-forward backtest that publishes the track record:
the replay logic, horizon statistics, caching, and staleness behaviour.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from screener.core.config import config
from screener.core.models import BacktestReport
from screener.services.backtest_service import BacktestService


class FakeProvider:
    def __init__(self, frames: dict[str, pd.DataFrame], info: dict | None = None):
        self._frames = frames
        self._info = info or {}

    def fetch_history(self, symbol: str, period: str = "1y", interval: str = "1d"):
        return self._frames.get(symbol)

    def fetch_info(self, symbol: str) -> dict:
        return self._info


def _frame(prices, start="2022-01-01"):
    idx = pd.date_range(start, periods=len(prices), freq="B")
    return pd.DataFrame(
        {
            "Open": prices,
            "High": [p * 1.01 for p in prices],
            "Low": [p * 0.99 for p in prices],
            "Close": prices,
            "Volume": [1_000_000] * len(prices),
        },
        index=idx,
    )


def _rising(n=1000, base=100.0, step=0.002):
    return _frame([base * (1 + step * i) for i in range(n)])


def _monkeypatch_backtest(monkeypatch, **kw):
    for key, value in kw.items():
        monkeypatch.setattr(config.backtest, key, value)


def test_backtest_replay_produces_dated_horizon_stats(tmp_path, monkeypatch):
    _monkeypatch_backtest(
        monkeypatch,
        start_date="2024-01-01",
        sample_every_days=21,
        max_horizon_days=365,
        universe=["TEST"],
    )
    monkeypatch.setattr(config.verification, "horizons", [30, 365])

    provider = FakeProvider(
        {"TEST": _rising(), "^NSEI": _rising(base=50.0, step=0.001)},
        info={"returnOnEquity": 0.2, "pegRatio": 0.8},
    )
    service = BacktestService(
        data_provider=provider,
        report_file=str(tmp_path / "backtest_report.json"),
    )

    report = service.run()

    assert isinstance(report, BacktestReport)
    assert report.universe == ["TEST"]
    assert report.universe_size == 1
    assert len(report.horizons) == 2

    by_h = {h.horizon_days: h for h in report.horizons}
    # A strong monotonic uptrend yields a positive signal hit-rate and a
    # positive average return at every matured horizon.
    assert by_h[30].n > 0, "expected at least one matured 30d signal"
    assert by_h[30].hit_rate is not None
    assert by_h[30].avg_return and by_h[30].avg_return > 0
    assert by_h[30].benchmark_avg_return is not None
    assert by_h[30].max_drawdown is not None
    assert by_h[365].n > 0

    assert len(report.methodology) >= 4
    assert any("NIFTY50" in m for m in report.methodology)
    assert any("no lookahead" in m for m in report.methodology)


def test_backtest_cache_serves_fresh_and_runs_when_stale(tmp_path, monkeypatch):
    _monkeypatch_backtest(
        monkeypatch,
        start_date="2024-01-01",
        sample_every_days=21,
        max_horizon_days=365,
        universe=["TEST"],
        cache_ttl_seconds=3600,
    )
    monkeypatch.setattr(config.verification, "horizons", [30])

    provider = FakeProvider({"TEST": _rising(), "^NSEI": _rising(base=50.0, step=0.001)})
    service = BacktestService(
        data_provider=provider,
        report_file=str(tmp_path / "backtest_report.json"),
    )

    first = service.run()
    assert first.horizons[0].n > 0

    # A fresh cache is served without touching the provider.
    cached = service.get()
    assert cached.horizons[0].n == first.horizons[0].n

    # A stale cache triggers a re-run.
    stale = first.model_copy(deep=True)
    stale.generated_at = datetime.now(timezone.utc) - timedelta(days=2)
    Path(tmp_path / "backtest_report.json").write_text(stale.model_dump_json())
    rerun = service.get()
    assert rerun.generated_at > first.generated_at


def test_backtest_report_file_is_gitignored():
    gitignore = Path(__file__).resolve().parent.parent / ".gitignore"
    assert "data/backtest_report.json" in gitignore.read_text()
