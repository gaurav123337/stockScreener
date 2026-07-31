"""Provider-neutral contracts for the Indian market research workspace.

The contracts deliberately keep the unverified upstream payload available as a
dictionary.  Only fields already described consistently by the provider docs
are promoted to typed values in this first phase.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class StockSummary(BaseModel):
    ticker_id: str
    company_name: str | None = None
    industry: str | None = None
    current_price: dict[str, float] = Field(default_factory=dict)
    percent_change: float | None = None
    year_high: float | None = None
    year_low: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict, exclude=True)


class MarketSnapshot(BaseModel):
    category: str
    items: list[dict[str, Any]] = Field(default_factory=list)


class HistoricalSeries(BaseModel):
    stock_id: str
    points: list[dict[str, Any]] = Field(default_factory=list)


class HistoricalStats(BaseModel):
    stock_id: str
    stats: Any = None


class IndianApiEnvelope(BaseModel):
    """Stable internal result metadata shared by later application routes."""
    data: Any
    provider: str = "indian_api"
    fetched_at: datetime
    stale: bool = False
    warnings: list[str] = Field(default_factory=list)


class IndianApiTelemetry(BaseModel):
    requests: int = 0
    cache_hits: int = 0
    successes: int = 0
    errors: int = 0
    rate_limits: int = 0
    average_latency_ms: float = 0.0
    last_status_code: int | None = None
    last_error: str | None = None


class IndianMarketGateway:
    """Protocol-like gateway boundary without coupling core to HTTP."""

    def stock(self, name: str) -> StockSummary:  # pragma: no cover - contract
        raise NotImplementedError

    def search(self, endpoint: str, query: str) -> list[dict[str, Any]]:  # pragma: no cover
        raise NotImplementedError

    def snapshot(self, endpoint: str) -> Any:  # pragma: no cover
        raise NotImplementedError

    def history(self, stock_id: str, **params: str) -> HistoricalSeries:  # pragma: no cover
        raise NotImplementedError

    def historical_stats(self, stock_id: str, **params: str) -> HistoricalStats:  # pragma: no cover
        raise NotImplementedError

    def analysis(self, endpoint: str, stock_id: str, **params: str) -> Any:  # pragma: no cover
        raise NotImplementedError

    def telemetry(self) -> IndianApiTelemetry:  # pragma: no cover
        raise NotImplementedError