"""Indian-API implementation of MarketDataProvider.

This adapter implements the core ``MarketDataProvider`` contract over the
optional Indian market API (``IndianApiClient``), so the whole screener can
be backed by the Indian API instead of Yahoo. It mirrors the degrade-gracefully
pattern of ``YahooIndianProvider``: endpoints the API cannot serve return
empty/None rather than breaking the contract.

The live API resolves symbols by bare NSE name (``stock_name``) rather than a
numeric id, so history and stats lookups need no extra resolution call. The
``/historical_data`` endpoint only exposes close prices (plus Volume and DMA
bands), so history rows are synthesised with ``open == high == low == close``.
Results are not cached to disk here — the client keeps a short TTL in-memory
cache.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from screener.core.config import IndianApiConfig, config
from screener.core.interfaces import MarketDataProvider
from screener.infrastructure.data.indian_api_client import IndianApiClient
from screener.infrastructure.data.nse_master import NseMasterStore

_INFO_METRIC_KEYS = {
    "marketCap": ("marketCap",),
    "trailingPE": ("pPerEBasicExcludingExtraordinaryItemsTTM", "pPerEExcludingExtraordinaryItemsMostRecentFiscalYear"),
    "forwardPE": (),
    "pegRatio": ("pegRatio",),
    "priceToBook": ("priceToBookMostRecentQuarter", "priceToBookMostRecentFiscalYear"),
    "returnOnEquity": ("returnOnAverageEquityTrailing12Month", "returnOnAverageEquityMostRecentFiscalYear"),
    "debtToEquity": ("totalDebtPerTotalEquityMostRecentQuarter", "lTDebtPerEquityMostRecentQuarter"),
    "profitMargins": ("netProfitMarginPercentTrailing12Month", "netProfitMargin5YearAverage"),
    "revenueGrowth": ("revenueGrowthRate5Year",),
    "earningsGrowth": ("ePSChangePercentTTMOverTTM",),
    "dividendYield": ("currentDividendYieldCommonStockPrimaryIssueLTM", "dividendYield5YearAverage"),
    "beta": ("beta",),
}


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

    def fetch_history(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> pd.DataFrame | None:
        bare = self.normalize_symbol(symbol)
        try:
            series = self._client.history(bare, period=period)
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
            try:
                metrics = self._client.flatten_metrics(summary.raw)
                for canonical, aliases in _INFO_METRIC_KEYS.items():
                    for alias in aliases:
                        value = self._to_number(metrics.get(alias))
                        if value is not None:
                            info.setdefault(canonical, value)
                            break
            except Exception:
                pass
        row = self._nse.lookup(bare)
        if row:
            info.setdefault("longName", row["name"] or None)
            info.setdefault("sector", row["industry"] or None)
            info.setdefault("industry", row["industry"] or None)
        return info

    @staticmethod
    def _to_number(value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(str(value).replace(",", "").replace("%", ""))
        except (TypeError, ValueError):
            return None

    def history_updated_at(self):
        return None
