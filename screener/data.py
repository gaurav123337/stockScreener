"""Data fetching for Indian stocks (NSE/BSE) via yfinance with graceful fallback.

Tickers are normalised to Yahoo format, e.g. RELIANCE -> RELIANCE.NS
All network calls are wrapped so a source failure never crashes the app.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None


def normalize_ticker(symbol: str, exchange: str = "NS") -> str:
    """Convert 'RELIANCE' -> 'RELIANCE.NS'. Pass-through if already suffixed."""
    s = symbol.strip().upper()
    if s.endswith(".NS") or s.endswith(".BO"):
        return s
    return f"{s}.{exchange}"


@dataclass
class StockData:
    symbol: str
    history: pd.DataFrame = field(default_factory=pd.DataFrame)  # OHLCV daily
    info: dict = field(default_factory=dict)  # fundamentals snapshot
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None and not self.history.empty


def fetch_history(symbol: str, period: str = "1y", interval: str = "1d",
                  retries: int = 2, pause: float = 1.0) -> StockData:
    """Fetch OHLCV history. Returns StockData with .error set on failure."""
    sym = normalize_ticker(symbol)
    if yf is None:
        return StockData(sym, error="yfinance not installed")
    last_err = None
    for attempt in range(retries + 1):
        try:
            df = yf.download(sym, period=period, interval=interval,
                             progress=False, auto_adjust=True)
            if df is not None and not df.empty:
                # Flatten possible MultiIndex columns from newer yfinance
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                return StockData(sym, history=df)
            last_err = "empty data (ticker may be wrong or source down)"
        except Exception as e:  # network / rate limit / parse errors
            last_err = str(e)
        if attempt < retries:
            time.sleep(pause)
    return StockData(sym, error=last_err)


def fetch_info(symbol: str) -> dict:
    """Fetch fundamentals snapshot. Returns {} on failure (non-fatal)."""
    sym = normalize_ticker(symbol)
    if yf is None:
        return {}
    try:
        t = yf.Ticker(sym)
        info = t.get_info() or {}
        keys = [
            "longName", "sector", "industry", "marketCap", "currency",
            "trailingPE", "forwardPE", "pegRatio", "priceToBook",
            "returnOnEquity", "debtToEquity", "profitMargins",
            "revenueGrowth", "earningsGrowth", "currentPrice",
            "fiftyTwoWeekHigh", "fiftyTwoWeekLow", "fiftyDayAverage",
            "twoHundredDayAverage", "dividendYield", "beta",
        ]
        return {k: info.get(k) for k in keys if info.get(k) is not None}
    except Exception:
        return {}
