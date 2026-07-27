"""Yahoo Finance implementation of MarketDataProvider."""
from __future__ import annotations

import time
from typing import Any

import pandas as pd

from screener.core.config import config
from screener.core.interfaces import MarketDataProvider

try:
    import yfinance as yf
except ImportError:  # pragma: no cover
    yf = None


class YahooDataProvider(MarketDataProvider):
    """Fetches OHLCV and fundamentals from Yahoo Finance."""

    def normalize_symbol(self, symbol: str, exchange: str = "NS") -> str:
        """Convert 'RELIANCE' -> 'RELIANCE.NS'. Pass-through if already suffixed."""
        s = symbol.strip().upper()
        if s.endswith(".NS") or s.endswith(".BO"):
            return s
        return f"{s}.{exchange}"

    def fetch_history(
        self,
        symbol: str,
        period: str | None = None,
        interval: str | None = None,
    ) -> pd.DataFrame | None:
        """Fetch OHLCV history with retries. Returns None on failure."""
        if yf is None:
            return None

        sym = self.normalize_symbol(symbol)
        period = period or config.data.default_period
        interval = interval or config.data.default_interval

        last_err: Exception | None = None
        for attempt in range(config.data.retry_attempts + 1):
            try:
                df = yf.download(
                    sym,
                    period=period,
                    interval=interval,
                    progress=False,
                    auto_adjust=True,
                )
                if df is not None and not df.empty:
                    # Flatten possible MultiIndex columns from newer yfinance
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    return df
                last_err = ValueError("empty data")
            except Exception as e:
                last_err = e
            if attempt < config.data.retry_attempts:
                time.sleep(config.data.retry_pause_seconds)
        return None

    def fetch_info(self, symbol: str) -> dict[str, Any]:
        """Fetch fundamentals snapshot. Returns {} on failure (non-fatal)."""
        if yf is None:
            return {}
        sym = self.normalize_symbol(symbol)
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
