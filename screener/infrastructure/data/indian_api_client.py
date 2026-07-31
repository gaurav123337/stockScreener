"""HTTP adapter for indianapi.in; no credentials are ever returned to callers."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

import requests

from screener.core.config import IndianApiConfig
from screener.core.indian_market import (
    HistoricalSeries,
    HistoricalStats,
    IndianMarketGateway,
    StockSummary,
)
from screener.core.responses import DataSourceError


@dataclass(frozen=True)
class Endpoint:
    path: str
    query_key: str | None = None


ENDPOINTS = {
    "stock": Endpoint("/stock", "name"),
    "industry_search": Endpoint("/industry_search", "query"),
    "mutual_fund_search": Endpoint("/mutual_fund_search", "query"),
    "trending": Endpoint("/trending"),
    "52_week_high_low": Endpoint("/fetch_52_week_high_low_data"),
    "nse_most_active": Endpoint("/NSE_most_active"),
    "bse_most_active": Endpoint("/BSE_most_active"),
    "price_shockers": Endpoint("/price_shockers"),
    "commodities": Endpoint("/commodities"),
    "historical_data": Endpoint("/historical_data"),
    "historical_stats": Endpoint("/historical_stats"),
    "stock_target_price": Endpoint("/stock_target_price", "stock_id"),
    "stock_forecasts": Endpoint("/stock_forecasts"),
    "mutual_funds": Endpoint("/mutual_funds"),
}


class IndianApiClient(IndianMarketGateway):
    """Small, injectable client with retries and bounded TTL caching."""

    def __init__(self, settings: IndianApiConfig, session: requests.Session | None = None):
        self.settings = settings
        self.session = session or requests.Session()
        self._cache: dict[tuple[str, tuple[tuple[str, str], ...]], tuple[float, Any]] = {}
        self._cache_lock = threading.Lock()

    def _request(self, endpoint: str, params: dict[str, str] | None = None) -> Any:
        if not self.settings.enabled:
            raise DataSourceError("Indian market API is disabled")
        if not self.settings.base_url:
            raise DataSourceError("Indian market API base URL is not configured")
        meta = ENDPOINTS.get(endpoint)
        if meta is None:
            raise ValueError(f"unknown Indian API endpoint: {endpoint}")
        query = tuple(sorted((params or {}).items()))
        cache_key = (endpoint, query)
        now = time.monotonic()
        with self._cache_lock:
            cached = self._cache.get(cache_key)
            if cached and now - cached[0] < self.settings.cache_ttl_seconds:
                return cached[1]
        request_params = dict(params or {})
        headers = {"Accept": "application/json", "User-Agent": "stockScreener/indian-market"}
        if self.settings.api_key:
            headers["X-Api-Key"] = self.settings.api_key
        url = f"{self.settings.base_url.rstrip('/')}{meta.path}"
        last_error: Exception | None = None
        for attempt in range(self.settings.retry_attempts + 1):
            try:
                response = self.session.get(url, params=request_params, headers=headers,
                                            timeout=self.settings.timeout_seconds)
                if response.status_code == 429:
                    raise DataSourceError("Indian market API rate limit reached")
                if response.status_code >= 400:
                    raise DataSourceError(f"Indian market API returned HTTP {response.status_code}")
                payload = response.json()
                with self._cache_lock:
                    self._cache[cache_key] = (time.monotonic(), payload)
                return payload
            except DataSourceError:
                raise
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt < self.settings.retry_attempts:
                    time.sleep(min(0.25 * (2 ** attempt), 2.0))
        raise DataSourceError("Indian market API request failed") from last_error

    def stock(self, name: str) -> StockSummary:
        payload = self._request("stock", {"name": name.strip()})
        if not isinstance(payload, dict) or not payload.get("tickerId"):
            raise DataSourceError("Indian market API returned an invalid stock response")
        prices = payload.get("currentPrice") or {}
        return StockSummary(
            ticker_id=str(payload["tickerId"]), company_name=payload.get("companyName"),
            industry=payload.get("industry"), current_price=self._numbers(prices),
            percent_change=self._number(payload.get("percentChange")),
            year_high=self._number(payload.get("yearHigh")), year_low=self._number(payload.get("yearLow")),
            raw=payload,
        )

    def search(self, endpoint: str, query: str) -> list[dict[str, Any]]:
        payload = self._request(endpoint, {"query": query.strip()})
        return payload if isinstance(payload, list) else []

    def snapshot(self, endpoint: str) -> Any:
        return self._request(endpoint)

    def history(self, stock_id: str, **params: str) -> HistoricalSeries:
        payload = self._request("historical_data", {"stock_id": stock_id, **params})
        return HistoricalSeries(stock_id=stock_id, points=payload if isinstance(payload, list) else [])

    def historical_stats(self, stock_id: str, **params: str) -> HistoricalStats:
        return HistoricalStats(stock_id=stock_id, stats=self._request("historical_stats", {"stock_id": stock_id, **params}))

    def analysis(self, endpoint: str, stock_id: str, **params: str) -> Any:
        if endpoint not in {"stock_target_price", "stock_forecasts", "mutual_funds"}:
            raise ValueError(f"unsupported analytical endpoint: {endpoint}")
        return self._request(endpoint, {"stock_id": stock_id, **params})

    @staticmethod
    def _number(value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(str(value).replace(",", "").replace("%", ""))
        except (TypeError, ValueError):
            return None

    @classmethod
    def _numbers(cls, values: Any) -> dict[str, float]:
        if not isinstance(values, dict):
            return {}
        return {str(key): number for key, value in values.items() if (number := cls._number(value)) is not None}