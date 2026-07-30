"""Offline tests: verify indicators, signals, filters on synthetic data."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from screener.indicators import add_all, rsi
from screener.core.config import config
from screener.core.container import container
from screener.core.interfaces import MarketDataProvider, PredictionRepository, KnowledgeStore
from screener.core.models import Action, Recommendation
from screener.services.analysis_service import AnalysisService
from screener.services.filter_service import FilterService, PredefinedFilter
from screener.services.scoring_engine import ScoringEngine
from screener.infrastructure.persistence.csv_repository import MarkdownKnowledgeStore


class MockDataProvider(MarketDataProvider):
    """Mock data provider for testing."""

    def __init__(self, history: pd.DataFrame | None = None, info: dict | None = None):
        self._history = history
        self._info = info or {}

    def fetch_history(self, symbol: str, period: str = "1y", interval: str = "1d"):
        return self._history

    def fetch_info(self, symbol: str) -> dict:
        return self._info

    def normalize_symbol(self, symbol: str) -> str:
        return symbol.upper()


def make_df(prices, volumes=None):
    n = len(prices)
    volumes = volumes or [1_000_000] * n
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "Open": prices, "High": [p * 1.01 for p in prices],
        "Low": [p * 0.99 for p in prices], "Close": prices, "Volume": volumes,
    }, index=idx)


def test_rsi_bounds():
    up = make_df(list(range(100, 200)))  # monotonic up
    r = rsi(up["Close"]).iloc[-1]
    assert r == 100.0, f"uptrend RSI should be 100, got {r}"
    down = make_df(list(range(200, 100, -1)))
    r2 = rsi(down["Close"]).iloc[-1]
    assert r2 <= 5, f"downtrend RSI should be ~0, got {r2}"
    print(f"  RSI bounds OK (up={r}, down={r2:.1f})")


def test_buy_on_uptrend():
    prices = list(np.linspace(100, 160, 260))  # steady uptrend, enough for SMA200
    history = make_df(prices)
    provider = MockDataProvider(history, info={"pegRatio": 0.8, "returnOnEquity": 0.2})
    analysis = AnalysisService(data_provider=provider, scoring_engine=ScoringEngine(use_registry=False))
    rec = analysis.analyze("TEST.NS")
    assert rec.action in (Action.BUY, Action.HOLD), rec.action
    assert rec.score > 0, rec.score
    assert any("200-DMA" in r or "50-DMA" in r for r in rec.reasons)
    if rec.action == Action.BUY:
        assert rec.target and rec.stop_loss and rec.target > rec.price > rec.stop_loss
    print(f"  Uptrend -> {rec.action.value} score={rec.score:+.0f} reasons={len(rec.reasons)}")


def test_sell_on_downtrend():
    prices = list(np.linspace(160, 100, 260))  # steady downtrend
    history = make_df(prices)
    provider = MockDataProvider(history, info={})
    analysis = AnalysisService(data_provider=provider, scoring_engine=ScoringEngine(use_registry=False))
    rec = analysis.analyze("TEST.NS")
    assert rec.action in (Action.SELL, Action.HOLD), rec.action
    assert rec.score < 0, rec.score
    if rec.action == Action.SELL:
        assert rec.target < rec.price < rec.stop_loss
    print(f"  Downtrend -> {rec.action.value} score={rec.score:+.0f}")


def test_filters():
    filter_service = FilterService()

    row = {"rsi": 25, "score": 40, "roe": 0.2, "peg": 0.5,
           "above_sma50": True, "above_sma200": True, "golden_cross": True,
           "action": "BUY", "debt_to_equity": 50}

    assert filter_service.get_filter("oversold").matches(row)
    assert filter_service.get_filter("uptrend").matches(row)
    assert filter_service.get_filter("value").matches(row)
    assert filter_service.get_filter("quality").matches(row)
    assert filter_service.get_filter("buy_signals").matches(row)

    custom = filter_service.compile_custom("rsi < 30 and roe > 0.15")
    assert custom.matches(row)
    assert not filter_service.compile_custom("rsi > 30").matches(row)
    print("  Pre-defined + custom filters OK")


def test_missing_knowledge_base_is_empty(tmp_path=None):
    """A fresh deployment can view an empty knowledge base without a 500."""
    import tempfile

    if tmp_path is None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = MarkdownKnowledgeStore(root / "missing.md", root / "manifest.json")
            assert store.get_content() == ""
    else:
        store = MarkdownKnowledgeStore(tmp_path / "missing.md", tmp_path / "manifest.json")
        assert store.get_content() == ""


def test_scoring_engine_pluggable():
    """Verify that custom scorers can be registered and used."""
    from screener.core.interfaces import ScoringStrategy
    from screener.core.plugins import registry

    class BonusScorer(ScoringStrategy):
        @property
        def name(self):
            return "bonus"

        def score(self, last, prev, info):
            return 5.0, ["Bonus +5"]

    registry.register_scorer(BonusScorer())
    engine = ScoringEngine(use_registry=True)

    df = make_df(list(np.linspace(100, 160, 260)))
    df = add_all(df)
    last, prev = df.iloc[-1], df.iloc[-2]

    score, reasons = engine.total_score(last, prev, {})
    assert "Bonus +5" in reasons
    print(f"  Pluggable scorer OK (total={score:+.1f})")


if __name__ == "__main__":
    test_rsi_bounds()
    test_buy_on_uptrend()
    test_sell_on_downtrend()
    test_filters()
    test_missing_knowledge_base_is_empty()
    test_scoring_engine_pluggable()
    print("ALL OFFLINE TESTS PASSED")
