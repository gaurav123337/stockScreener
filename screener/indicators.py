"""Technical indicators computed with pandas (no external TA lib needed)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    # Wilder's smoothing
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    # When avg_loss == 0 -> RSI 100; when both 0 -> 50 (neutral)
    out = out.fillna(50)
    out[avg_loss == 0] = 100.0
    out[(avg_gain == 0) & (avg_loss == 0)] = 50.0
    return out


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def add_all(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of OHLCV df with indicator columns appended."""
    out = df.copy()
    close = out["Close"]
    out["SMA50"] = sma(close, 50)
    out["SMA200"] = sma(close, 200)
    out["RSI14"] = rsi(close, 14)
    m, s, h = macd(close)
    out["MACD"], out["MACDsig"], out["MACDhist"] = m, s, h
    out["ATR14"] = atr(out, 14)
    out["VolAvg20"] = sma(out["Volume"], 20)
    out["High52"] = out["High"].rolling(252, min_periods=20).max()
    out["Low52"] = out["Low"].rolling(252, min_periods=20).min()
    return out
