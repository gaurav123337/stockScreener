"""Shared base for free, keyed JSON REST market-data providers.

Concrete providers (Alpha Vantage, Financial Modeling Prep, Finnhub) share a
lot of plumbing: keyed requests with timeouts and retries, the disk history /
fundamentals caches, symbol normalisation, and graceful degradation. This
base class holds that plumbing; each subclass implements four small hooks that
translate its wire format onto the canonical OHLCV / fundamentals shapes.

Free-tier providers are aggressively rate-limited (Alpha Vantage ~25/day, FMP
and Finnhub in the tens of thousands / minute), so the design leans on three
things: the disk caches (a universe scan warms once, later scans read disk),
error-envelope detection (rate-limited responses become a miss, not a crash),
and the failover chain (when one provider is exhausted, the next serves).
"""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import requests

from screener.core.config import config
from screener.core.interfaces import MarketDataProvider
from screener.infrastructure.data.fundamentals_cache import FundamentalsCache
from screener.infrastructure.data.history_cache import HistoryCache

_PERIOD_DAYS = {
    "1d": 1, "5d": 5, "1w": 7, "1mo": 30, "3mo": 91, "6mo": 182,
    "1y": 365, "2y": 730, "3y": 1095, "5y": 1826, "10y": 3652,
}


class RestMarketDataProvider(MarketDataProvider):
    """Base class for keyed JSON REST providers (Alpha Vantage / FMP / Finnhub).

    Subclasses implement: ``_history_path`` / ``_history_params`` /
    ``_history_frame`` (history) and ``_info_path`` / ``_info_params`` /
    ``_info_dict`` plus an optional ``_info_extra`` (fundamentals).
    """

    provider_name = "rest"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        api_key_param: str | None = None,
        api_key_header: str | None = None,
        timeout: float = 10.0,
        retry_attempts: int | None = None,
        retry_pause: float | None = None,
        session: requests.Session | None = None,
        headers: dict[str, str] | None = None,
        history_cache: HistoryCache | None = None,
        fundamentals_cache: FundamentalsCache | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key or ""
        self._api_key_param = api_key_param
        self._api_key_header = api_key_header
        self._timeout = timeout
        self._retry_attempts = (
            config.data.retry_attempts if retry_attempts is None else retry_attempts
        )
        self._retry_pause = (
            config.data.retry_pause_seconds if retry_pause is None else retry_pause
        )
        self._session = session or requests.Session()
        self._headers = dict(headers or {})
        self._history = history_cache or HistoryCache(
            config.data_dir / "history_cache.json",
            ttl_seconds=config.data.history_cache_ttl_seconds,
        )
        self._fundamentals = fundamentals_cache or FundamentalsCache(
            config.data_dir / "fundamentals_cache.json",
            ttl_seconds=config.data.fundamentals_cache_ttl_seconds,
        )

    # ------------------------------------------------------------------ #
    # MarketDataProvider API
    # ------------------------------------------------------------------ #
    def normalize_symbol(self, symbol: str) -> str:
        """Bare uppercase ticker (these providers have no exchange suffixes)."""
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
        period = period or config.data.default_period
        interval = interval or config.data.default_interval

        cached = self._history.get(bare, period, interval)
        if cached is not None and not cached.empty:
            return cached

        payload = self._get(
            self._history_path(bare, period, interval),
            self._history_params(bare, period, interval),
        )
        if self._is_error(payload):
            return None
        df = self._history_frame(payload)
        if df is not None and not df.empty:
            self._history.set(bare, period, interval, df)
            return df
        return None

    def fetch_info(self, symbol: str) -> dict[str, Any]:
        bare = self.normalize_symbol(symbol)
        cached = self._fundamentals.get(bare)
        if cached:
            return cached

        payload = self._get(self._info_path(bare), self._info_params(bare))
        if self._is_error(payload):
            return {}
        info = self._info_dict(payload) or {}
        extra = self._info_extra(bare)
        if extra:
            info.update(extra)
        if info:
            self._fundamentals.set(bare, info)
        return info

    def history_updated_at(self):
        return self._history.last_fetched_at()

    # ------------------------------------------------------------------ #
    # Request plumbing
    # ------------------------------------------------------------------ #
    def _get(
        self, path: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None
    ) -> Any:
        """GET a JSON resource with retries; None on any failure."""
        query = dict(params or {})
        extra_headers = dict(headers or {})
        if self._api_key_param:
            query[self._api_key_param] = self._api_key
        if self._api_key_header:
            extra_headers[self._api_key_header] = self._api_key
        url = f"{self._base_url}{path}"
        for attempt in range(self._retry_attempts + 1):
            try:
                resp = self._session.get(
                    url,
                    params=query,
                    headers={**self._headers, **extra_headers},
                    timeout=self._timeout,
                )
                if resp.status_code >= 400:
                    raise requests.HTTPError(f"HTTP {resp.status_code}")
                return resp.json()
            except (requests.RequestException, ValueError):
                if attempt < self._retry_attempts:
                    time.sleep(self._retry_pause)
        return None

    @staticmethod
    def _is_error(payload: Any) -> bool:
        """Free providers signal quota errors with a 200 + error envelope."""
        if not isinstance(payload, dict):
            return False
        return any(key in payload for key in ("Note", "Information", "Error Message"))

    # ------------------------------------------------------------------ #
    # Period / number helpers
    # ------------------------------------------------------------------ #
    @classmethod
    def _period_days(cls, period: str) -> int:
        key = str(period or "").lower().replace(" ", "")
        if key in _PERIOD_DAYS:
            return _PERIOD_DAYS[key]
        try:
            if key.endswith("y"):
                return int(key[:-1]) * 365
            if key.endswith("mo"):
                return int(key[:-2]) * 30
            if key.endswith("w"):
                return int(key[:-1]) * 7
            if key.endswith("d"):
                return int(key[:-1])
        except ValueError:
            pass
        return 365

    @classmethod
    def _range_from_period(cls, period: str) -> tuple[str, str]:
        """ISO (from, to) covering the requested lookback, both inclusive."""
        end = date.today()
        start = end - timedelta(days=cls._period_days(period))
        return start.isoformat(), end.isoformat()

    @staticmethod
    def _to_number(value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(str(value).replace(",", "").replace("%", ""))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _compact(mapping: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in mapping.items() if v is not None}

    # ------------------------------------------------------------------ #
    # Hooks implemented by concrete providers
    # ------------------------------------------------------------------ #
    def _history_path(self, symbol: str, period: str, interval: str) -> str:
        raise NotImplementedError

    def _history_params(self, symbol: str, period: str, interval: str) -> dict[str, Any]:
        return {}

    def _history_frame(self, payload: Any) -> pd.DataFrame | None:
        raise NotImplementedError

    def _info_path(self, symbol: str) -> str:
        raise NotImplementedError

    def _info_params(self, symbol: str) -> dict[str, Any]:
        return {}

    def _info_dict(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def _info_extra(self, symbol: str) -> dict[str, Any]:
        return {}
