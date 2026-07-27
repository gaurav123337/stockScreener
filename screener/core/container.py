"""Dependency Injection Container — lightweight, no external DI framework needed.

Usage:
    container = Container()
    container.register(MarketDataProvider, YahooDataProvider)
    provider = container.resolve(MarketDataProvider)

For testing:
    container.register_instance(MarketDataProvider, MockDataProvider())
"""
from __future__ import annotations

from typing import Any, TypeVar, Type

T = TypeVar("T")


class Container:
    """Simple service locator / DI container."""

    def __init__(self):
        self._services: dict[type, Any] = {}
        self._instances: dict[type, Any] = {}
        self._singletons: set[type] = set()

    def register(
        self,
        interface: type[T],
        implementation: type[T] | None = None,
        *,
        singleton: bool = True,
        factory: callable | None = None,
    ) -> None:
        """Register an implementation for an interface.

        Args:
            interface: The abstract class/protocol.
            implementation: Concrete class to instantiate.
            singleton: If True, reuse the same instance.
            factory: Optional callable that returns the instance.
        """
        if singleton:
            self._singletons.add(interface)
        if factory:
            self._services[interface] = factory
        elif implementation:
            self._services[interface] = implementation
        else:
            raise ValueError("Must provide implementation or factory")

    def register_instance(self, interface: type[T], instance: T) -> None:
        """Register an already-constructed instance (useful for tests)."""
        self._instances[interface] = instance
        self._singletons.add(interface)

    def resolve(self, interface: type[T]) -> T:
        """Get an instance of the requested interface."""
        if interface in self._instances:
            return self._instances[interface]

        if interface not in self._services:
            raise KeyError(f"No service registered for {interface.__name__}")

        provider = self._services[interface]
        if isinstance(provider, type):
            # It's a class — instantiate it
            instance = provider()
        else:
            # It's a factory function
            instance = provider()

        if interface in self._singletons:
            self._instances[interface] = instance
        return instance

    def clear(self) -> None:
        """Reset container (useful between tests)."""
        self._services.clear()
        self._instances.clear()
        self._singletons.clear()


# Global application container
container = Container()
