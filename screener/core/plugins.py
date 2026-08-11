"""Plugin Registry — enables extensible filters, scoring strategies, and brokers.

New capabilities are added by registering plugins, not modifying core code.
"""
from __future__ import annotations

from typing import Any, Callable

from screener.core.interfaces import FilterStrategy, ScoringStrategy, BrokerAdapter


class PluginRegistry:
    """Central registry for all pluggable components."""

    def __init__(self):
        self._filters: dict[str, FilterStrategy] = {}
        self._scorers: dict[str, ScoringStrategy] = {}
        self._brokers: dict[str, BrokerAdapter] = {}
        self._filter_factories: dict[str, Callable[[], FilterStrategy]] = {}

    # ---- Filters ----
    def register_filter(self, filter_strategy: FilterStrategy) -> None:
        """Register a filter instance."""
        self._filters[filter_strategy.name] = filter_strategy

    def register_filter_factory(self, name: str, factory: Callable[[], FilterStrategy]) -> None:
        """Register a filter factory for lazy instantiation."""
        self._filter_factories[name] = factory

    def get_filter(self, name: str) -> FilterStrategy | None:
        """Get a filter by name."""
        if name in self._filters:
            return self._filters[name]
        if name in self._filter_factories:
            instance = self._filter_factories[name]()
            self._filters[name] = instance
            return instance
        return None

    def list_filters(self) -> list[dict[str, str]]:
        """List all registered filters (guided presets flagged for the UI)."""
        out: list[dict[str, str]] = []
        for f in self._filters.values():
            item: dict[str, str] = {"name": f.name, "description": f.description}
            guided = getattr(f, "guided", False)
            if guided:
                item["guided"] = "true"
            out.append(item)
        return out

    # ---- Scorers ----
    def register_scorer(self, scorer: ScoringStrategy) -> None:
        """Register a scoring strategy."""
        self._scorers[scorer.name] = scorer

    def get_scorer(self, name: str) -> ScoringStrategy | None:
        return self._scorers.get(name)

    def get_all_scorers(self) -> list[ScoringStrategy]:
        """Get all scorers in registration order."""
        return list(self._scorers.values())

    # ---- Brokers ----
    def register_broker(self, broker: BrokerAdapter) -> None:
        """Register a broker adapter."""
        self._brokers[broker.name] = broker

    def get_broker(self, name: str) -> BrokerAdapter | None:
        return self._brokers.get(name)

    def list_brokers(self) -> list[str]:
        return list(self._brokers.keys())

    def get_connected_broker(self) -> BrokerAdapter | None:
        """Return the first connected broker, if any."""
        for broker in self._brokers.values():
            if broker.is_connected():
                return broker
        return None

    # ---- Bulk ----
    def clear(self) -> None:
        self._filters.clear()
        self._scorers.clear()
        self._brokers.clear()
        self._filter_factories.clear()


# Global registry instance
registry = PluginRegistry()
