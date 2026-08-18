"""Hybrid implementation of MarketDataProvider.

A primary source with an ordered set of fallbacks. Each symbol fails over
independently: if a provider cannot produce history or fundamentals, the next
one in the chain is tried before giving up. This keeps scans resilient when a
provider is rate-limited or missing a listing.

``active_source`` reports which provider actually served the most recent
successful call on the current thread (scans run across a thread pool, so the
source is tracked per-thread to stay race-free). This is what lets the UI show
"data came from X" even when the configured provider is a chain.
"""
from __future__ import annotations

import threading
from typing import Any

import pandas as pd

from screener.core.interfaces import MarketDataProvider


def _provider_label(provider: MarketDataProvider) -> str:
    return getattr(provider, "provider_name", None) or type(provider).__name__.lower()


class HybridDataProvider(MarketDataProvider):
    """Primary provider with per-symbol fallback to secondary provider(s)."""

    def __init__(
        self,
        primary: MarketDataProvider,
        fallback: MarketDataProvider | None = None,
        fallbacks: list[MarketDataProvider] | None = None,
    ):
        providers: list[MarketDataProvider] = [primary]
        if fallbacks:
            providers.extend(fallbacks)
        if fallback is not None:
            providers.append(fallback)
        self._providers = providers
        self._local = threading.local()

    @property
    def provider_name(self) -> str:
        return "hybrid"

    @property
    def active_source(self) -> str | None:
        """Name of the provider that served the last call on this thread."""
        return getattr(self._local, "source", None)

    def _record_source(self, provider: MarketDataProvider) -> None:
        self._local.source = _provider_label(provider)

    def normalize_symbol(self, symbol: str) -> str:
        return self._providers[0].normalize_symbol(symbol)

    def resolve_symbol(self, symbol: str) -> str | None:
        resolver = getattr(self._providers[0], "resolve_symbol", None)
        if callable(resolver):
            return resolver(symbol)
        normalized = self.normalize_symbol(symbol)
        return normalized if normalized else None

    def fetch_history(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> pd.DataFrame | None:
        for provider in self._providers:
            try:
                df = provider.fetch_history(symbol, period=period, interval=interval)
            except Exception:
                df = None
            if df is not None and not df.empty:
                self._record_source(provider)
                return df
        return None

    def fetch_info(self, symbol: str) -> dict[str, Any]:
        for provider in self._providers:
            try:
                info = provider.fetch_info(symbol) or {}
            except Exception:
                info = {}
            if info:
                self._record_source(provider)
                return info
        return {}

    def history_updated_at(self):
        primary = getattr(self._providers[0], "history_updated_at", None)
        if callable(primary):
            return primary()
        return None
