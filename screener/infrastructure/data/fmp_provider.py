"""Financial Modeling Prep (FMP) implementation of MarketDataProvider.

The free tier is generous (tens of thousands of requests per minute) and the
``/stable`` API is a clean, keyed JSON surface: ``historical-price-eod/full``
for daily OHLCV (bounded by ``from``/``to``), ``historical-chart/<interval>``
for intraday bars, and ``profile`` for fundamentals. Auth is the ``apikey``
query parameter on every request.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from screener.core.config import FmpConfig, config
from screener.infrastructure.data.rest_provider import RestMarketDataProvider

_INTRAVAL = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min",
             "1h": "1hour", "4h": "4hour", "1wk": "1hour", "1mo": "1hour"}


class FmpProvider(RestMarketDataProvider):
    """Fetches OHLCV and fundamentals from Financial Modeling Prep."""

    provider_name = "fmp"

    def __init__(self, settings: FmpConfig | None = None, **kwargs: Any):
        settings = settings or config.fmp
        kwargs.setdefault("base_url", settings.base_url)
        kwargs.setdefault("api_key", settings.api_key)
        kwargs.setdefault("timeout", settings.timeout_seconds)
        super().__init__(api_key_param="apikey", **kwargs)

    # ------------------------------------------------------------------ #
    # History
    # ------------------------------------------------------------------ #
    def _history_path(self, symbol: str, period: str, interval: str) -> str:
        interval_key = str(interval or "").lower()
        if interval_key in _INTRAVAL:
            return f"/historical-chart/{_INTRAVAL[interval_key]}"
        return "/historical-price-eod/full"

    def _history_params(self, symbol: str, period: str, interval: str) -> dict[str, Any]:
        interval_key = str(interval or "").lower()
        if interval_key in _INTRAVAL:
            return {"symbol": symbol}
        from_date, to_date = self._range_from_period(period)
        return {"symbol": symbol, "from": from_date, "to": to_date}

    def _history_frame(self, payload: Any) -> pd.DataFrame | None:
        if not isinstance(payload, list) or not payload:
            return None
        items = [item for item in payload if isinstance(item, dict)]
        if not items:
            return None
        rows = []
        for item in items:
            close = self._to_number(item.get("close"))
            if close is None:
                close = self._to_number(item.get("price"))
            rows.append({
                "Open": self._to_number(item.get("open")),
                "High": self._to_number(item.get("high")),
                "Low": self._to_number(item.get("low")),
                "Close": close,
                "Volume": self._to_number(item.get("volume")),
            })
        df = pd.DataFrame(rows)
        df.index = pd.to_datetime([item.get("date") for item in items], errors="coerce")
        return df

    # ------------------------------------------------------------------ #
    # Fundamentals
    # ------------------------------------------------------------------ #
    def _info_path(self, symbol: str) -> str:
        return "/profile"

    def _info_params(self, symbol: str) -> dict[str, Any]:
        return {"symbol": symbol}

    def _info_dict(self, payload: dict[str, Any]) -> dict[str, Any]:
        if isinstance(payload, list):
            payload = payload[0] if payload else {}
        if not isinstance(payload, dict):
            return {}
        return self._compact({
            "longName": payload.get("companyName"),
            "sector": payload.get("sector"),
            "industry": payload.get("industry"),
            "marketCap": self._to_number(payload.get("marketCap")),
            "currency": payload.get("currency"),
            "currentPrice": self._to_number(payload.get("price")),
            "beta": self._to_number(payload.get("beta")),
            "website": payload.get("website"),
        })
