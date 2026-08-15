"""Hybrid implementation of MarketDataProvider.

A primary source with an ordered set of fallbacks. Each symbol fails over
independently: if a provider cannot produce history or fundamentals, the next
one in the chain is tried before giving up. This keeps scans resilient when a
provider is rate-limited or missing a listing.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from screener.core.interfaces import MarketDataProvider


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

    @property
    def provider_name(self) -> str:
        return "hybrid"

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
                return df
        return None

    def fetch_info(self, symbol: str) -> dict[str, Any]:
        for provider in self._providers:
            try:
                info = provider.fetch_info(symbol) or {}
            except Exception:
                info = {}
            if info:
                return info
        return {}

    def history_updated_at(self):
        primary = getattr(self._providers[0], "history_updated_at", None)
        if callable(primary):
            return primary()
        return None
