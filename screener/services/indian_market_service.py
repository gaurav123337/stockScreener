"""Application orchestration for the optional Indian market workspace."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from screener.core.config import config
from screener.core.indian_market import IndianApiEnvelope, IndianMarketGateway
from screener.core.responses import DataSourceError, ValidationError


class IndianMarketService:
    """Keep provider checks and stable response metadata out of HTTP handlers."""

    def __init__(self, gateway: IndianMarketGateway | None = None):
        self.gateway = gateway

    def _gateway(self) -> IndianMarketGateway:
        if not config.indian_api.enabled:
            raise DataSourceError("Indian market API is disabled")
        if self.gateway is None:
            raise DataSourceError("Indian market API is not configured")
        return self.gateway

    @staticmethod
    def _envelope(data: Any, warnings: list[str] | None = None) -> dict[str, Any]:
        return IndianApiEnvelope(
            data=data, fetched_at=datetime.now(timezone.utc), warnings=warnings or []
        ).model_dump(mode="json")

    @staticmethod
    def _required(value: str, field: str) -> str:
        value = value.strip()
        if not value:
            raise ValidationError(f"{field} must not be empty")
        return value

    def stock(self, query: str) -> dict[str, Any]:
        return self._envelope(self._gateway().stock(self._required(query, "q")))

    def search(self, endpoint: str, query: str) -> dict[str, Any]:
        return self._envelope(self._gateway().search(endpoint, self._required(query, "q")))

    def snapshot(self, endpoint: str) -> dict[str, Any]:
        return self._envelope(self._gateway().snapshot(endpoint))

    def history(self, stock_id: str, **params: str) -> dict[str, Any]:
        return self._envelope(self._gateway().history(self._required(stock_id, "stock_id"), **params))

    def stats(self, stock_id: str, **params: str) -> dict[str, Any]:
        return self._envelope(self._gateway().historical_stats(self._required(stock_id, "stock_id"), **params))

    def analysis(self, endpoint: str, stock_id: str, **params: str) -> dict[str, Any]:
        return self._envelope(self._gateway().analysis(endpoint, self._required(stock_id, "stock_id"), **params))

    def rollout_status(self) -> dict[str, Any]:
        gateway = self.gateway
        telemetry = gateway.telemetry().model_dump() if gateway is not None else None
        return {
            "enabled": config.indian_api.enabled,
            "configured": bool(config.indian_api.base_url and config.indian_api.api_key),
            "market_data_provider": config.market_data_provider,
            "telemetry": telemetry,
        }
