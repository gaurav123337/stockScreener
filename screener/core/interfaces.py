"""Abstract interfaces — Dependency Inversion Principle.

All services depend on these abstractions, not concrete implementations.
This enables testing, swapping providers, and future extension.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

import pandas as pd

from screener.core.models import (
    Action,
    BrokerStatus,
    Holding,
    PredictionRecord,
    Recommendation,
    ScanResult,
    VerificationReport,
)


class MarketDataProvider(ABC):
    """Abstract source of market data (OHLCV + fundamentals)."""

    @abstractmethod
    def fetch_history(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> pd.DataFrame | None:
        """Return OHLCV DataFrame or None on failure."""
        ...

    @abstractmethod
    def fetch_info(self, symbol: str) -> dict:
        """Return fundamentals dict (empty on failure)."""
        ...

    @abstractmethod
    def normalize_symbol(self, symbol: str) -> str:
        """Normalize to provider's ticker format."""
        ...


class ScoringStrategy(ABC):
    """Abstract scoring component — pluggable into the engine."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def score(
        self,
        last: pd.Series,
        prev: pd.Series | None,
        info: dict,
    ) -> tuple[float, list[str]]:
        """Return (score_contribution, reasons)."""
        ...


class FilterStrategy(ABC):
    """Abstract stock filter."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    def matches(self, row: dict) -> bool: ...


class BrokerAdapter(ABC):
    """Abstract broker integration."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    def status(self) -> BrokerStatus: ...

    @abstractmethod
    def get_ltp(self, symbol: str) -> float | None: ...

    @abstractmethod
    def get_holdings(self) -> list[Holding]: ...

    @abstractmethod
    def connect(self, credentials: dict) -> bool: ...

    @abstractmethod
    def disconnect(self) -> bool: ...


class PredictionRepository(ABC):
    """Abstract persistence for predictions."""

    @abstractmethod
    def save(self, record: PredictionRecord) -> None: ...

    @abstractmethod
    def get_all(self) -> list[PredictionRecord]: ...

    @abstractmethod
    def get_due(self, horizon_days: int = 30) -> list[PredictionRecord]: ...

    @abstractmethod
    def update(self, record: PredictionRecord) -> None: ...


class KnowledgeStore(ABC):
    """Abstract knowledge base persistence."""

    @abstractmethod
    def append_rules(self, source: str, rules: list[str]) -> None: ...

    @abstractmethod
    def get_content(self) -> str: ...

    @abstractmethod
    def has_ingested(self, source_hash: str) -> bool: ...

    @abstractmethod
    def mark_ingested(self, source_name: str, source_hash: str) -> None: ...


class EventBus(ABC):
    """Simple pub/sub for decoupled notifications."""

    @abstractmethod
    def publish(self, event: str, payload: dict) -> None: ...

    @abstractmethod
    def subscribe(self, event: str, handler: Callable[[dict], None]) -> None: ...
