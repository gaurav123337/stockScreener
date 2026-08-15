"""Alpha Vantage implementation of MarketDataProvider.

Free tier: ~25 requests/day and 5/minute. Quota responses arrive as HTTP 200
with a ``Note``/``Information`` envelope — those are detected in the shared
base and surfaced as a miss so the failover chain (or the disk cache) can
serve instead.

History uses ``TIME_SERIES_DAILY`` (``compact`` = last 100 trading days; the
full output is premium-only) or ``TIME_SERIES_INTRADAY`` for intraday
intervals. Fundamentals come from the flat ``OVERVIEW`` payload, augmented
with a ``GLOBAL_QUOTE`` call for the live price.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from screener.core.config import AlphaVantageConfig, config
from screener.infrastructure.data.rest_provider import RestMarketDataProvider

_INTRAVAL = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min",
             "1h": "60min", "1wk": "60min", "1mo": "60min"}
_BAR_KEY = {"Open": "1. open", "High": "2. high", "Low": "3. low",
            "Close": "4. close", "Volume": "5. volume"}


class AlphaVantageProvider(RestMarketDataProvider):
    """Fetches OHLCV and fundamentals from Alpha Vantage."""

    provider_name = "alphavantage"

    def __init__(self, settings: AlphaVantageConfig | None = None, **kwargs: Any):
        settings = settings or config.alphavantage
        kwargs.setdefault("base_url", settings.base_url)
        kwargs.setdefault("api_key", settings.api_key)
        kwargs.setdefault("timeout", settings.timeout_seconds)
        super().__init__(api_key_param="apikey", **kwargs)

    # ------------------------------------------------------------------ #
    # History
    # ------------------------------------------------------------------ #
    def _history_path(self, symbol: str, period: str, interval: str) -> str:
        return "/query"

    def _history_params(self, symbol: str, period: str, interval: str) -> dict[str, Any]:
        interval_key = str(interval or "").lower()
        if interval_key in _INTRAVAL:
            return {
                "function": "TIME_SERIES_INTRADAY",
                "symbol": symbol,
                "interval": _INTRAVAL[interval_key],
            }
        return {"function": "TIME_SERIES_DAILY", "symbol": symbol, "outputsize": "compact"}

    def _history_frame(self, payload: Any) -> pd.DataFrame | None:
        if not isinstance(payload, dict):
            return None
        series = payload.get("Time Series (Daily)") or {}
        for label in ("Time Series (1min)", "Time Series (5min)", "Time Series (15min)",
                      "Time Series (30min)", "Time Series (60min)"):
            if isinstance(payload.get(label), dict):
                series = payload[label]
                break
        if not isinstance(series, dict) or not series:
            return None
        items = sorted(series.items())  # oldest -> newest
        rows = []
        for _, bar in items:
            if not isinstance(bar, dict):
                continue
            rows.append({col: self._to_number(bar.get(key)) for col, key in _BAR_KEY.items()})
        if not rows:
            return None
        df = pd.DataFrame(rows)
        df.index = pd.to_datetime([d for d, _ in items], errors="coerce")
        return df

    # ------------------------------------------------------------------ #
    # Fundamentals
    # ------------------------------------------------------------------ #
    def _info_path(self, symbol: str) -> str:
        return "/query"

    def _info_params(self, symbol: str) -> dict[str, Any]:
        return {"function": "OVERVIEW", "symbol": symbol}

    def _info_dict(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._compact({
            "longName": payload.get("Name"),
            "sector": payload.get("Sector"),
            "industry": payload.get("Industry"),
            "marketCap": self._to_number(payload.get("MarketCapitalization")),
            "currency": payload.get("Currency"),
            "trailingPE": self._to_number(payload.get("PERatio")),
            "forwardPE": self._to_number(payload.get("ForwardPE")),
            "pegRatio": self._to_number(payload.get("PEGRatio")),
            "priceToBook": self._to_number(payload.get("PriceToBookRatio")),
            "returnOnEquity": self._to_number(payload.get("ReturnOnEquityTTM")),
            "debtToEquity": self._to_number(payload.get("DebtToEquityTTM")),
            "profitMargins": self._to_number(payload.get("ProfitMargin")),
            "revenueGrowth": self._to_number(payload.get("RevenueGrowthTTM")),
            "earningsGrowth": self._to_number(payload.get("EarningsGrowth")),
            "dividendYield": self._to_number(payload.get("DividendYield")),
            "beta": self._to_number(payload.get("Beta")),
            "fiftyTwoWeekHigh": self._to_number(payload.get("52WeekHigh")),
            "fiftyTwoWeekLow": self._to_number(payload.get("52WeekLow")),
        })

    def _info_extra(self, symbol: str) -> dict[str, Any]:
        payload = self._get("/query", {"function": "GLOBAL_QUOTE", "symbol": symbol})
        quote = payload.get("Global Quote") if isinstance(payload, dict) else None
        if not isinstance(quote, dict):
            return {}
        price = self._to_number(quote.get("05. price"))
        out: dict[str, Any] = {}
        if price is not None:
            out["currentPrice"] = price
        change = self._to_number(quote.get("10. change percent"))
        if change is not None:
            out["priceChangePercent"] = change
        return out
