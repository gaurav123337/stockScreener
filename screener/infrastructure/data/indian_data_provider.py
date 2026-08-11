"""Indian-API implementation of MarketDataProvider.

This adapter implements the core ``MarketDataProvider`` contract over the
optional Indian market API (``IndianApiClient``), so the whole screener can
be backed by the Indian API instead of Yahoo. It mirrors the degrade-gracefully
pattern of ``YahooIndianProvider``: endpoints the API cannot serve return
empty/None rather than breaking the contract.

The Indian API resolves symbols by name to a ``ticker_id``, so history and
stats lookups make one extra resolution call per symbol. Results are not
cached to disk here — the client keeps a short TTL in-memory cache.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from screener.core.config import IndianApiConfig, config
from screener.core.interfaces import MarketDataProvider
from screener.infrastructure.data.indian_api_client import IndianApiClient
from screener.infrastructure.data.nse_master import NseMasterStore

_PERIOD_MAP = {
    "1d": "1D",
    "5d": "1W",
    "1mo": "1M",
    "3mo": "3M",
    "6mo": "6M",
    "1y": "1Y",
    "2y": "2Y",
    "5y": "5Y",
    "10y": "10Y",
}

_INFO_KEYS = (
    "marketCap", "trailingPE", "forwardPE", "pegRatio", "priceToBook",
    "returnOnEquity", "debtToEquity", "profitMargins", "revenueGrowth",
    "earningsGrowth", "dividendYield", "beta",
)


class IndianDataProvider(MarketDataProvider):
    """Fetches OHLCV and fundamentals from the Indian market API."""

    def __init__(
        self,
        client: IndianApiClient | None = None,
        nse_master: NseMasterStore | None = None,
    ):
        settings = config.indian_api
        self._client = client or IndianApiClient(settings or IndianApiConfig())
        self._nse = nse_master or NseMasterStore()

    @property
    def provider_name(self) -> str:
        return "indian_api"

    def normalize_symbol(self, symbol: str) -> str:
        """Bare NSE code (Indian API resolves names itself)."""
        s = symbol.strip().upper().replace("%26", "&")
        for suffix in (".NS", ".BO"):
            if s.endswith(suffix):
                return s[: -len(suffix)]
        return s

    @staticmethod
    def _map_period(period: str | None) -> str:
        return _PERIOD_MAP.get(str(period or "1y").lower(), str(period or "1Y").upper())

    def _ticker_id(self, symbol: str) -> str | None:
        try:
            return self._client.stock(self.normalize_symbol(symbol)).ticker_id
        except Exception:
            return None

    def fetch_history(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> pd.DataFrame | None:
        ticker_id = self._ticker_id(symbol)
        if not ticker_id:
            return None
        try:
            series = self._client.history(ticker_id, period=self._map_period(period))
        except Exception:
            return None
        points = series.points
        if not points:
            return None
        rows: list[dict[str, Any]] = []
        for point in points:
            rows.append({
                "Open": point.get("open"),
                "High": point.get("high"),
                "Low": point.get("low"),
                "Close": point.get("close"),
                "Volume": point.get("volume"),
            })
        df = pd.DataFrame(rows)
        dates = [point.get("date") for point in points]
        df.index = pd.to_datetime(dates, errors="coerce")
        return df

    def fetch_info(self, symbol: str) -> dict[str, Any]:
        bare = self.normalize_symbol(symbol)
        info: dict[str, Any] = {}
        try:
            summary = self._client.stock(bare)
        except Exception:
            summary = None
        if summary is not None:
            info["longName"] = summary.company_name
            info["sector"] = summary.industry
            info["industry"] = summary.industry
            prices = summary.current_price or {}
            if prices:
                info["currentPrice"] = next(iter(prices.values()))
            if summary.year_high is not None:
                info["fiftyTwoWeekHigh"] = summary.year_high
            if summary.year_low is not None:
                info["fiftyTwoWeekLow"] = summary.year_low
        row = self._nse.lookup(bare)
        if row:
            info.setdefault("longName", row["name"] or None)
            info.setdefault("sector", row["industry"] or None)
            info.setdefault("industry", row["industry"] or None)
        ticker_id = summary.ticker_id if summary is not None else self._ticker_id(bare)
        if ticker_id:
            try:
                stats = self._client.historical_stats(ticker_id).stats
                if isinstance(stats, dict):
                    for key in _INFO_KEYS:
                        if stats.get(key) is not None:
                            info.setdefault(key, stats[key])
            except Exception:
                pass
        return info

    def history_updated_at(self):
        return None
