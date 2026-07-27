"""Offline tests: verify indicators, signals, filters on synthetic data."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from screener.indicators import add_all, rsi

from screener.signals import analyze
from screener import filters as F


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
    rec = analyze("TEST.NS", make_df(prices), info={"pegRatio": 0.8, "returnOnEquity": 0.2})
    assert rec.action in ("BUY", "HOLD"), rec.action
    assert rec.score > 0, rec.score
    assert any("200-DMA" in r or "50-DMA" in r for r in rec.reasons)
    if rec.action == "BUY":
        assert rec.target and rec.stop_loss and rec.target > rec.price > rec.stop_loss
    print(f"  Uptrend -> {rec.action} score={rec.score:+.0f} reasons={len(rec.reasons)}")


def test_sell_on_downtrend():
    prices = list(np.linspace(160, 100, 260))  # steady downtrend
    rec = analyze("TEST.NS", make_df(prices), info={})
    assert rec.action in ("SELL", "HOLD"), rec.action
    assert rec.score < 0, rec.score
    if rec.action == "SELL":
        assert rec.target < rec.price < rec.stop_loss
    print(f"  Downtrend -> {rec.action} score={rec.score:+.0f}")


def test_filters():
    row = {"rsi": 25, "score": 40, "roe": 0.2, "peg": 0.5,
           "above_sma50": True, "above_sma200": True, "golden_cross": True,
           "action": "BUY", "debt_to_equity": 50}
    assert F.get_predefined("oversold")(row)
    assert F.get_predefined("uptrend")(row)
    assert F.get_predefined("value")(row)
    assert F.get_predefined("quality")(row)
    assert F.get_predefined("buy_signals")(row)
    custom = F.compile_custom("rsi < 30 and roe > 0.15")
    assert custom(row)
    assert not F.compile_custom("rsi > 30")(row)
    print("  Pre-defined + custom filters OK")


if __name__ == "__main__":
    test_rsi_bounds()
    test_buy_on_uptrend()
    test_sell_on_downtrend()
    test_filters()
    print("ALL OFFLINE TESTS PASSED")
