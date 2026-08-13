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

    @property
    def headers(self):
        return {}


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


def test_stock_maps_new_contract_and_keeps_provider_raw_payload():
    session = FakeSession(FakeResponse({
        "companyName": "Reliance Industries",
        "currentPrice": {"NSE": "2,195.75", "BSE": 2200.5, "unknown": None},
        "percentChange": "1.25%",
        "companyProfile": {
            "mgIndustry": "Oil & Gas Operations",
            "peerCompanyList": [{"tickerId": "S0003030"}],
        },
        "stockDetailsReusableData": {"yhigh": "2,400", "ylow": None},
        "stockCorporateActionData": {"dividend": [{"tickerId": "S0003018"}]},
    }))

    result = client(session).stock(" Reliance ")

    assert result.ticker_id == "S0003018"
    assert result.company_name == "Reliance Industries"
    assert result.industry == "Oil & Gas Operations"
    assert result.current_price == {"NSE": 2195.75, "BSE": 2200.5}
    assert result.percent_change == 1.25
    assert result.year_high == 2400.0
    assert result.raw["companyName"] == "Reliance Industries"
    assert session.calls[0]["url"].endswith("/stock")
    assert session.calls[0]["params"] == {"name": "Reliance"}
    assert session.calls[0]["headers"]["X-Api-Key"] == "secret-do-not-return"


def test_stock_falls_back_to_name_when_ticker_id_is_nested_missing():
    session = FakeSession(FakeResponse({
        "companyName": "TCS",
        "companyProfile": {"mgIndustry": "Software"},
        "currentPrice": {"NSE": 4200.0},
    }))
    result = client(session).stock("tcs")
    assert result.ticker_id == "TCS"
    assert result.industry == "Software"


def test_history_maps_datasets_to_ohlcv_points():
    session = FakeSession(FakeResponse({
        "datasets": [
            {"metric": "Price", "label": "Price on NSE", "values": [
                ["2025-08-13", "1382.60"], ["2025-08-14", "1373.80"],
            ]},
            {"metric": "DMA50", "label": "50 DMA", "values": [
                ["2025-08-13", "1422.75"], ["2025-08-14", "1420.83"],
            ]},
            {"metric": "Volume", "label": "Volume", "values": [
                ["2025-08-13", 7826188, {"delivery": 65}],
                ["2025-08-14", 7573899, {"delivery": 53}],
            ]},
        ]
    }))
    api = client(session)
    series = api.history("RELIANCE", period="1y")

    assert session.calls[0]["params"] == {
        "stock_name": "RELIANCE", "filter": "default", "period": "1yr"
    }
    assert len(series.points) == 2
    point = series.points[0]
    assert point["date"] == "2025-08-13"
    assert point["close"] == pytest.approx(1382.6)
    assert point["open"] == point["high"] == point["low"] == point["close"]
    assert point["volume"] == 7826188
    assert series.points[1]["volume"] == 7573899


def test_history_period_tokens_map_onto_live_enum():
    assert IndianApiClient._map_history_period("1d") == "1m"
    assert IndianApiClient._map_history_period("6mo") == "6m"
    assert IndianApiClient._map_history_period("1y") == "1yr"
    assert IndianApiClient._map_history_period("2y") == "3yr"
    assert IndianApiClient._map_history_period("10y") == "10yr"
    assert IndianApiClient._map_history_period("bogus") == "1yr"


def test_historical_stats_uses_stock_name_and_stats_param():
    session = FakeSession(FakeResponse({"profit_loss_stats": []}))
    api = client(session)
    stats = api.historical_stats("RELIANCE", stats="all")
    assert stats.stats == {"profit_loss_stats": []}
    assert session.calls[0]["params"] == {"stock_name": "RELIANCE", "stats": "all"}


def test_identical_requests_use_ttl_cache():
    session = FakeSession(FakeResponse([{"id": "S1"}]))
    api = client(session, cache_ttl_seconds=60)

    assert api.search("industry_search", "bank") == [{"id": "S1"}]
    assert api.search("industry_search", "bank") == [{"id": "S1"}]
    assert len(session.calls) == 1
    telemetry = api.telemetry()
    assert telemetry.requests == 1
    assert telemetry.cache_hits == 1
    assert telemetry.successes == 1


def test_disabled_and_http_errors_are_structured():
    disabled = IndianApiClient(IndianApiConfig(enabled=False))
    with pytest.raises(DataSourceError, match="disabled"):
        disabled.snapshot("trending")

    session = FakeSession(FakeResponse({"error": "too many requests"}, status_code=429))
    with pytest.raises(DataSourceError, match="rate limit"):
        client(session, retry_attempts=3).snapshot("trending")
    assert len(session.calls) == 1


def test_free_plan_defaults_to_official_host_and_surfaces_api_errors():
    settings = IndianApiConfig(enabled=True, api_key="secret")
    api = IndianApiClient(settings, FakeSession(FakeResponse({})))

    assert settings.base_url == "https://stock.indianapi.in"

    # Dedicated-endpoint restrictions are enforced by the API host, not the
    # client; rejections surface as DataSourceError instead of being swallowed.
    rejected = FakeSession(FakeResponse({"error": "payment required"}, status_code=403))
    api_403 = IndianApiClient(settings, rejected)
    with pytest.raises(DataSourceError, match="HTTP 403"):
        api_403.history("RELIANCE")
    with pytest.raises(DataSourceError, match="HTTP 403"):
        api_403.historical_stats("RELIANCE")
    with pytest.raises(DataSourceError, match="HTTP 403"):
        api_403.analysis("stock_forecasts", "RELIANCE")
    assert len(rejected.calls) == 3


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


def test_configurable_bearer_auth_and_redacted_rollout_status(monkeypatch):
    session = FakeSession(FakeResponse([]))
    api = client(session)
    api.settings.auth_header = "Authorization"
    api.settings.auth_scheme = "Bearer"
    api.snapshot("trending")

    assert session.calls[0]["headers"]["Authorization"] == "Bearer secret-do-not-return"

    monkeypatch.setattr(config.indian_api, "enabled", True)
    monkeypatch.setattr(config.indian_api, "base_url", "https://api.example.test")
    monkeypatch.setattr(config.indian_api, "api_key", "secret-do-not-return")
    status = IndianMarketService(api).rollout_status()
    assert status["configured"] is True
    assert "secret-do-not-return" not in repr(status)
    assert status["telemetry"]["successes"] == 1


def test_transient_server_errors_are_retried():
    session = FakeSession(FakeResponse({}, status_code=503))
    api = client(session, retry_attempts=2)
    with pytest.raises(DataSourceError, match="HTTP 503"):
        api.snapshot("trending")
    assert len(session.calls) == 3


def test_rate_limit_window_is_enforced_without_waiting(monkeypatch):
    api = client(FakeSession(FakeResponse([])), rate_limit_per_minute=1)
    sleeps: list[float] = []
    monkeypatch.setattr("screener.infrastructure.data.indian_api_client.time.monotonic", lambda: 160.0)
    monkeypatch.setattr("screener.infrastructure.data.indian_api_client.time.sleep", sleeps.append)
    api._wait_for_rate_limit(100.0)
    api._wait_for_rate_limit(100.0)
    assert sleeps == [60.0]


def test_indian_overview_returns_one_stable_envelope(monkeypatch):
    import api as api_module

    class FakeOverviewService:
        def snapshot(self, endpoint):
            if endpoint == "commodities":
                raise DataSourceError("temporarily unavailable")
            return {
                "data": [{"endpoint": endpoint}],
                "provider": "indian_api",
                "fetched_at": "2026-07-31T00:00:00+00:00",
                "stale": False,
                "warnings": [],
            }

    monkeypatch.setattr(api_module, "_indian_market", lambda: FakeOverviewService())
    result = api_module.indian_overview()
    assert result["data"]["snapshots"]["trending"] == [{"endpoint": "trending"}]
    assert "commodities" not in result["data"]["snapshots"]
    assert result["provider"] == "indian_api"
    assert result["warnings"] == ["commodities: temporarily unavailable"]


def test_indian_routes_require_strict_authentication():
    import api as api_module

    route = next(
        route for route in api_module.app.routes
        if getattr(route, "path", None) == "/api/indian-market/overview"
    )
    dependencies = [dependency.call for dependency in route.dependant.dependencies]
    assert api_module.require_auth in dependencies
    assert api_module.get_current_user not in dependencies