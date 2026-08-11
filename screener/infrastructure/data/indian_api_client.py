"""HTTP adapter for indianapi.in; no credentials are ever returned to callers."""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

import requests

from screener.core.config import IndianApiConfig
from screener.core.indian_market import (
    HISTORY_POINT_KEYS,
    HistoricalSeries,
    HistoricalStats,
    IndianMarketGateway,
    IndianApiTelemetry,
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
        self._request_times: deque[float] = deque()
        self._rate_lock = threading.Lock()
        self._telemetry = IndianApiTelemetry()
        self._telemetry_lock = threading.Lock()

    @property
    def provider_name(self) -> str:
        return "indian_api"

    def _record(self, **changes: Any) -> None:
        with self._telemetry_lock:
            current = self._telemetry.model_dump()
            for key, value in changes.items():
                current[key] = current[key] + value if key in {"requests", "cache_hits", "successes", "errors", "rate_limits"} else value
            self._telemetry = IndianApiTelemetry(**current)

    def telemetry(self) -> IndianApiTelemetry:
        with self._telemetry_lock:
            return self._telemetry.model_copy(deep=True)

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
                self._record(cache_hits=1)
                return cached[1]
            if cached:
                self._cache.pop(cache_key, None)
            self._evict_expired_cache(now)
        request_params = dict(params or {})
        headers = {"Accept": "application/json", "User-Agent": "stockScreener/indian-market"}
        if self.settings.api_key:
            prefix = f"{self.settings.auth_scheme.strip()} " if self.settings.auth_scheme.strip() else ""
            headers[self.settings.auth_header] = f"{prefix}{self.settings.api_key}"
        url = f"{self.settings.base_url.rstrip('/')}{meta.path}"
        last_error: Exception | None = None
        for attempt in range(self.settings.retry_attempts + 1):
            self._wait_for_rate_limit(time.monotonic())
            started_at = time.monotonic()
            self._record(requests=1)
            try:
                response = self.session.get(url, params=request_params, headers=headers,
                                            timeout=self.settings.timeout_seconds)
                latency_ms = (time.monotonic() - started_at) * 1000
                self._record(last_status_code=response.status_code)
                if response.status_code == 429:
                    self._record(errors=1, rate_limits=1, last_error="rate_limit")
                    raise DataSourceError("Indian market API rate limit reached")
                if response.status_code >= 400:
                    self._record(errors=1, last_error=f"http_{response.status_code}")
                    if response.status_code >= 500 and attempt < self.settings.retry_attempts:
                        time.sleep(min(0.25 * (2 ** attempt), 2.0))
                        continue
                    raise DataSourceError(f"Indian market API returned HTTP {response.status_code}")
                payload = response.json()
                previous_successes = self.telemetry().successes
                previous_average = self.telemetry().average_latency_ms
                average = ((previous_average * previous_successes) + latency_ms) / (previous_successes + 1)
                self._record(successes=1, average_latency_ms=round(average, 2), last_error=None)
                with self._cache_lock:
                    self._cache[cache_key] = (time.monotonic(), payload)
                return payload
            except DataSourceError:
                raise
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                self._record(errors=1, last_error=type(exc).__name__)
                if attempt < self.settings.retry_attempts:
                    time.sleep(min(0.25 * (2 ** attempt), 2.0))
        raise DataSourceError("Indian market API request failed") from last_error

    def _evict_expired_cache(self, now: float) -> None:
        ttl = self.settings.cache_ttl_seconds
        if ttl <= 0:
            self._cache.clear()
            return
        self._cache = {
            key: value for key, value in self._cache.items() if now - value[0] < ttl
        }

    def _wait_for_rate_limit(self, now: float) -> None:
        limit = self.settings.rate_limit_per_minute
        while True:
            with self._rate_lock:
                cutoff = now - 60.0
                while self._request_times and self._request_times[0] <= cutoff:
                    self._request_times.popleft()
                if len(self._request_times) < limit:
                    self._request_times.append(now)
                    return
                wait = max(0.01, 60.0 - (now - self._request_times[0]))
            time.sleep(wait)
            now = time.monotonic()

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
        return HistoricalSeries(
            stock_id=stock_id,
            points=self._normalize_points(payload if isinstance(payload, list) else []),
        )

    @staticmethod
    def _normalize_points(points: list[Any]) -> list[dict[str, Any]]:
        """Map provider-specific point keys onto the common OHLCV contract.

        Unknown keys are preserved so no information is dropped; canonical keys
        are added from common aliases when the provider uses different names.
        """
        alias_sets = {
            "date": ("date", "timestamp", "datetime", "time"),
            "open": ("open", "Open"),
            "high": ("high", "High"),
            "low": ("low", "Low"),
            "close": ("close", "Close", "price", "last"),
            "volume": ("volume", "Volume", "vol"),
        }
        out: list[dict[str, Any]] = []
        for point in points:
            if not isinstance(point, dict):
                out.append(point)
                continue
            item = dict(point)
            for canon, aliases in alias_sets.items():
                for alias in aliases:
                    if alias in item:
                        item.setdefault(canon, item[alias])
                        break
            out.append(item)
        return out

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