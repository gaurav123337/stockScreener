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
        if not isinstance(payload, dict):
            raise DataSourceError("Indian market API returned an invalid stock response")
        profile = payload.get("companyProfile") or {}
        details = payload.get("stockDetailsReusableData") or {}
        return StockSummary(
            ticker_id=self._extract_ticker_id(payload) or name.strip().upper(),
            company_name=payload.get("companyName"),
            industry=profile.get("mgIndustry"),
            current_price=self._numbers(payload.get("currentPrice") or {}),
            percent_change=self._number(payload.get("percentChange") or details.get("percentChange")),
            year_high=self._number(details.get("yhigh") or details.get("high")),
            year_low=self._number(details.get("ylow") or details.get("low")),
            raw=payload,
        )

    @staticmethod
    def _extract_ticker_id(payload: dict) -> str | None:
        """The live API nests ``tickerId`` inside sub-resources."""
        corporate = payload.get("stockCorporateActionData") or {}
        for key in ("dividend", "bonus", "annualGeneralMeeting", "boardMeetings"):
            items = corporate.get(key) or []
            if items and isinstance(items[0], dict) and items[0].get("tickerId"):
                return str(items[0]["tickerId"])
        for section in (payload.get("companyProfile") or {}, payload.get("stockDetailsReusableData") or {}):
            peers = section.get("peerCompanyList") or []
            if peers and isinstance(peers[0], dict) and peers[0].get("tickerId"):
                return str(peers[0]["tickerId"])
        return None

    def flatten_metrics(self, payload: dict) -> dict[str, Any]:
        """Flatten ``keyMetrics`` sections + reusable-data scalars onto one dict."""
        out: dict[str, Any] = {}
        metrics = payload.get("keyMetrics") or {}
        if isinstance(metrics, dict):
            for section in metrics.values():
                if not isinstance(section, list):
                    continue
                for item in section:
                    if isinstance(item, dict) and item.get("key") is not None:
                        out[str(item["key"])] = item.get("value")
        details = payload.get("stockDetailsReusableData") or {}
        if isinstance(details, dict):
            for key, value in details.items():
                if key not in out and not isinstance(value, (list, dict)):
                    out[str(key)] = value
        return out

    def search(self, endpoint: str, query: str) -> list[dict[str, Any]]:
        payload = self._request(endpoint, {"query": query.strip()})
        return payload if isinstance(payload, list) else []

    def snapshot(self, endpoint: str) -> Any:
        return self._request(endpoint)

    def history(self, stock_id: str, **params: str) -> HistoricalSeries:
        period = self._map_history_period(str(params.get("period") or "1yr"))
        filter_ = str(params.get("filter") or "default")
        payload = self._request("historical_data", {
            "stock_name": stock_id, "filter": filter_, "period": period,
        })
        return HistoricalSeries(
            stock_id=stock_id,
            points=self._points_from_datasets(payload if isinstance(payload, dict) else {}),
        )

    @staticmethod
    def _map_history_period(period: str) -> str:
        """Map provider period tokens onto the live API's enum.

        The API accepts 1m | 6m | 1yr | 3yr | 5yr | 10yr. ``default`` is the
        nearest bucket that covers the requested lookback.
        """
        key = str(period).lower().replace(" ", "")
        mapping = {
            "1d": "1m", "1w": "1m", "1m": "1m",
            "1mo": "1m", "3mo": "6m", "6mo": "6m",
            "1y": "1yr", "2y": "3yr", "3y": "3yr",
            "5y": "5yr", "10y": "10yr",
        }
        return mapping.get(key, "1yr")

    @classmethod
    def _points_from_datasets(cls, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Map the new ``{datasets: [...]}`` shape onto OHLCV points.

        The live API only exposes close prices (plus Volume and DMA bands), so
        each point is synthesised as ``open == high == low == close`` with the
        matching volume. This keeps the common-key OHLCV contract intact.
        """
        datasets = payload.get("datasets") or []
        price_rows: list[list[Any]] = []
        volume_by_date: dict[str, Any] = {}
        for ds in datasets:
            if not isinstance(ds, dict) or not isinstance(ds.get("values"), list):
                continue
            metric = str(ds.get("metric") or "").lower()
            values = ds["values"]
            if metric == "price":
                price_rows = values
            elif metric == "volume":
                for row in values:
                    if isinstance(row, (list, tuple)) and len(row) >= 2:
                        volume_by_date[str(row[0])] = row[1]
        points: list[dict[str, Any]] = []
        for row in price_rows:
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                continue
            close = cls._number(row[1])
            if close is None:
                continue
            date = str(row[0])
            points.append({
                "date": date,
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": volume_by_date.get(date),
            })
        return points

    def historical_stats(self, stock_id: str, **params: str) -> HistoricalStats:
        stats_type = str(params.get("stats") or "all")
        return HistoricalStats(
            stock_id=stock_id,
            stats=self._request("historical_stats", {"stock_name": stock_id, "stats": stats_type}),
        )

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