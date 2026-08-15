"""Finnhub implementation of MarketDataProvider.

Free tier: 60 calls/minute, hard cap of 30/second; excess returns HTTP 429.
Auth is the ``token`` query parameter (``X-Finnhub-Token`` header also works).

History uses ``/stock/candle`` (resolution ``D`` for daily, ``W``/``M`` or
numeric minute buckets for intraday; ``s: "no_data"`` means no bars). The
response is columnar — parallel arrays ``o/h/l/c/v/t`` — which maps directly
onto a DataFrame. Fundamentals come from ``/stock/profile2`` (the free
profile), augmented with a ``/quote`` call for the live price. Note that
Finnhub reports ``marketCapitalization`` in USD millions.
"""
from __future__ import annotations

import time
from typing import Any

import pandas as pd

from screener.core.config import FinnhubConfig, config
from screener.infrastructure.data.rest_provider import RestMarketDataProvider

_RESOLUTION = {"1m": "1", "5m": "5", "15m": "15", "30m": "30",
               "1h": "60", "4h": "240", "1wk": "W", "1mo": "M"}


class FinnhubProvider(RestMarketDataProvider):
    """Fetches OHLCV and fundamentals from Finnhub."""

    provider_name = "finnhub"

    def __init__(self, settings: FinnhubConfig | None = None, **kwargs: Any):
        settings = settings or config.finnhub
        kwargs.setdefault("base_url", settings.base_url)
        kwargs.setdefault("api_key", settings.api_key)
        kwargs.setdefault("timeout", settings.timeout_seconds)
        super().__init__(api_key_param="token", **kwargs)

    # ------------------------------------------------------------------ #
    # History
    # ------------------------------------------------------------------ #
    def _history_path(self, symbol: str, period: str, interval: str) -> str:
        return "/stock/candle"

    def _history_params(self, symbol: str, period: str, interval: str) -> dict[str, Any]:
        days = self._period_days(period)
        now = int(time.time())
        return {
            "symbol": symbol,
            "resolution": _RESOLUTION.get(str(interval or "").lower(), "D"),
            "from": now - days * 86_400,
            "to": now,
        }

    def _history_frame(self, payload: Any) -> pd.DataFrame | None:
        if not isinstance(payload, dict) or payload.get("s") != "ok":
            return None
        closes = payload.get("c") or []
        if not closes:
            return None
        rows = [
            {"Open": o, "High": h, "Low": low, "Close": c, "Volume": v}
            for o, h, low, c, v in zip(
                payload.get("o") or [], payload.get("h") or [],
                payload.get("l") or [], closes, payload.get("v") or [],
            )
        ]
        df = pd.DataFrame(rows)
        df.index = pd.to_datetime(payload.get("t") or [], unit="s", errors="coerce")
        return df

    # ------------------------------------------------------------------ #
    # Fundamentals
    # ------------------------------------------------------------------ #
    def _info_path(self, symbol: str) -> str:
        return "/stock/profile2"

    def _info_params(self, symbol: str) -> dict[str, Any]:
        return {"symbol": symbol}

    def _info_dict(self, payload: dict[str, Any]) -> dict[str, Any]:
        market_cap = self._to_number(payload.get("marketCapitalization"))
        out = {
            "longName": payload.get("name"),
            "industry": payload.get("finnhubIndustry"),
            "currency": payload.get("currency"),
            "website": payload.get("weburl"),
            "logo": payload.get("logo"),
        }
        # Finnhub reports market cap in USD millions.
        if market_cap is not None:
            out["marketCap"] = market_cap * 1_000_000
        return self._compact(out)

    def _info_extra(self, symbol: str) -> dict[str, Any]:
        payload = self._get("/quote", {"symbol": symbol})
        if not isinstance(payload, dict):
            return {}
        out: dict[str, Any] = {}
        price = self._to_number(payload.get("c"))
        if price is not None:
            out["currentPrice"] = price
        change = self._to_number(payload.get("dp"))
        if change is not None:
            out["priceChangePercent"] = change
        return out
