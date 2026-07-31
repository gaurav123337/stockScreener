"""Offline contract tests for the Indian API Phase 1 boundary."""
from __future__ import annotations

from typing import Any

import pytest

from screener.core.config import AppConfig, IndianApiConfig, config
from screener.core.responses import DataSourceError
from screener.infrastructure.data.indian_api_client import IndianApiClient
from screener.services.indian_market_service import IndianMarketService


class FakeResponse:
    def __init__(self, payload: Any, status_code: int = 200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def get(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return self.response


def client(session: FakeSession, **overrides) -> IndianApiClient:
    settings = IndianApiConfig(
        enabled=True,
        base_url="https://api.example.test",
        api_key="secret-do-not-return",
        **overrides,
    )
    return IndianApiClient(settings, session=session)


def test_stock_maps_numeric_strings_and_keeps_provider_raw_payload():
    session = FakeSession(FakeResponse({
        "tickerId": "RELIANCE",
        "companyName": "Reliance Industries Limited",
        "industry": "Conglomerate",
        "currentPrice": {"NSE": "2,195.75", "BSE": 2200.5, "unknown": None},
        "percentChange": "1.25%",
        "yearHigh": "2,400",
        "yearLow": None,
    }))

    result = client(session).stock(" Reliance ")

    assert result.ticker_id == "RELIANCE"
    assert result.current_price == {"NSE": 2195.75, "BSE": 2200.5}
    assert result.percent_change == 1.25
    assert result.raw["tickerId"] == "RELIANCE"
    assert session.calls[0]["url"].endswith("/stock")
    assert session.calls[0]["params"] == {"name": "Reliance"}
    assert session.calls[0]["headers"]["X-Api-Key"] == "secret-do-not-return"


def test_identical_requests_use_ttl_cache():
    session = FakeSession(FakeResponse([{"id": "S1"}]))
    api = client(session, cache_ttl_seconds=60)

    assert api.search("industry_search", "bank") == [{"id": "S1"}]
    assert api.search("industry_search", "bank") == [{"id": "S1"}]
    assert len(session.calls) == 1


def test_disabled_and_http_errors_are_structured():
    disabled = IndianApiClient(IndianApiConfig())
    with pytest.raises(DataSourceError, match="disabled"):
        disabled.snapshot("trending")

    session = FakeSession(FakeResponse({"error": "too many requests"}, status_code=429))
    with pytest.raises(DataSourceError, match="rate limit"):
        client(session, retry_attempts=3).snapshot("trending")
    assert len(session.calls) == 1


class FakeGateway:
    def stock(self, name):
        return {"name": name}

    def search(self, endpoint, query):
        return [{"endpoint": endpoint, "query": query}]

    def snapshot(self, endpoint):
        return [{"endpoint": endpoint}]

    def history(self, stock_id, **params):
        return {"stock_id": stock_id, "params": params}

    def historical_stats(self, stock_id, **params):
        return {"stock_id": stock_id, "params": params}

    def analysis(self, endpoint, stock_id, **params):
        return {"endpoint": endpoint, "stock_id": stock_id, "params": params}


def test_indian_market_service_wraps_provider_metadata(monkeypatch):
    monkeypatch.setattr(config.indian_api, "enabled", True)
    result = IndianMarketService(FakeGateway()).analysis(
        "stock_forecasts", "RELIANCE", period_type="annual"
    )
    assert result["provider"] == "indian_api"
    assert result["stale"] is False
    assert result["data"]["stock_id"] == "RELIANCE"
    assert result["data"]["params"] == {"period_type": "annual"}


def test_analysis_rejects_unsupported_endpoint():
    settings = IndianApiConfig(enabled=True, api_key="secret")
    client = IndianApiClient(settings, FakeSession(FakeResponse({})))
    with pytest.raises(ValueError, match="unsupported analytical endpoint"):
        client.analysis("unknown", "RELIANCE")


def test_secret_is_not_in_editable_snapshot():
    settings = AppConfig(indian_api=IndianApiConfig(api_key="secret"))
    snapshot = settings.editable_snapshot()
    assert "indian_api" not in snapshot
    assert "secret" not in repr(snapshot)