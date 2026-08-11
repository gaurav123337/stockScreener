"""Hybrid implementation of MarketDataProvider.

Yahoo is the primary source; the Indian API is the fallback. Each symbol
fails over independently: if the primary cannot produce history or
fundamentals, the fallback provider is tried before giving up. This keeps
scans resilient when one provider is rate-limited or missing a listing.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from screener.core.interfaces import MarketDataProvider


class HybridDataProvider(MarketDataProvider):
    """Primary (Yahoo) with per-symbol fallback to a secondary provider."""

    def __init__(
        self,
        primary: MarketDataProvider,
        fallback: MarketDataProvider,
    ):
        self._primary = primary
        self._fallback = fallback

    @property
    def provider_name(self) -> str:
        return "hybrid"

    def normalize_symbol(self, symbol: str) -> str:
        return self._primary.normalize_symbol(symbol)

    def resolve_symbol(self, symbol: str) -> str | None:
        resolver = getattr(self._primary, "resolve_symbol", None)
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
        df = self._primary.fetch_history(symbol, period=period, interval=interval)
        if df is not None and not df.empty:
            return df
        try:
            return self._fallback.fetch_history(symbol, period=period, interval=interval)
        except Exception:
            return None

    def fetch_info(self, symbol: str) -> dict[str, Any]:
        info = self._primary.fetch_info(symbol)
        if info:
            return info
        try:
            return self._fallback.fetch_info(symbol) or {}
        except Exception:
            return {}

    def history_updated_at(self):
        primary = getattr(self._primary, "history_updated_at", None)
        if callable(primary):
            return primary()
        return None
