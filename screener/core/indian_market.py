"""Provider-neutral contracts for the Indian market research workspace.

Every adapter (indian_api, yahoo, ...) must conform to these contracts. The
typed models below are the *common keys* — the stable vocabulary the rest of
the application and the front end consume. Swapping providers therefore only
means selecting a different adapter in configuration; the front end and
services are never touched.

The contracts deliberately keep the unverified upstream payload available as a
dictionary.  Only fields already described consistently by the provider docs
are promoted to typed values in this first phase.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# Common keys for OHLCV history points produced by every adapter.
# Adapters normalise provider-specific point dicts onto these keys.
HISTORY_POINT_KEYS = ("date", "open", "high", "low", "close", "volume")


class StockSummary(BaseModel):
    ticker_id: str
    company_name: str | None = None
    industry: str | None = None
    current_price: dict[str, float] = Field(default_factory=dict)
    percent_change: float | None = None
    year_high: float | None = None
    year_low: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict, exclude=True)


class StockSearchResult(BaseModel):
    """Common-key result for ``industry_search``."""
    ticker_id: str
    company_name: str | None = None
    industry: str | None = None
    exchange: str | None = "NSE"


class MutualFundResult(BaseModel):
    """Common-key result for ``mutual_fund_search`` (Phase 3 asset class)."""
    scheme_code: str
    scheme_name: str | None = None
    category: str | None = None
    nav: float | None = None


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


class IndianMarketGateway(ABC):
    """Adapter boundary decoupling application code from any provider.

    Subclasses implement a single data provider (indianapi.in, Yahoo, ...) and
    normalise its responses onto the common-key contracts above. Selecting a
    provider is a configuration concern, never a code change here.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:  # pragma: no cover - contract
        """Stable identifier reported in envelopes/rollout status."""
        raise NotImplementedError

    @abstractmethod
    def stock(self, name: str) -> StockSummary:  # pragma: no cover - contract
        raise NotImplementedError

    @abstractmethod
    def search(self, endpoint: str, query: str) -> list[dict[str, Any]]:  # pragma: no cover
        raise NotImplementedError

    @abstractmethod
    def snapshot(self, endpoint: str) -> Any:  # pragma: no cover
        raise NotImplementedError

    @abstractmethod
    def history(self, stock_id: str, **params: str) -> HistoricalSeries:  # pragma: no cover
        raise NotImplementedError

    @abstractmethod
    def historical_stats(self, stock_id: str, **params: str) -> HistoricalStats:  # pragma: no cover
        raise NotImplementedError

    @abstractmethod
    def analysis(self, endpoint: str, stock_id: str, **params: str) -> Any:  # pragma: no cover
        raise NotImplementedError

    @abstractmethod
    def telemetry(self) -> IndianApiTelemetry:  # pragma: no cover
        raise NotImplementedError