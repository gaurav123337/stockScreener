"""Offline tests for the configurable market-data provider switching.

Covers:
- ``IndianDataProvider`` implements the MarketDataProvider contract over the
  Indian API client (history -> OHLCV frame, fundamentals, symbol normalise)
- ``HybridDataProvider`` fails over per symbol when the primary provider fails
- the bootstrap factory honours ``config.market_data_provider``
- a config publish re-registers the provider in the DI container (runtime swap)
- the two provider switches are surfaced in the admin registry / snapshot
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from screener.core.config import IndianApiConfig, config
from screener.core.interfaces import MarketDataProvider
from screener.infrastructure.data.hybrid_provider import HybridDataProvider
from screener.infrastructure.data.indian_api_client import IndianApiClient
from screener.infrastructure.data.indian_data_provider import IndianDataProvider
from screener.services.control_center_service import ControlCenterService


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload

    @property
    def headers(self):
        return {}


class FakeSession:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        key = "stock" if url.endswith("/stock") else "historical_data" if url.endswith("/historical_data") else "historical_stats" if url.endswith("/historical_stats") else "other"
        return self.responses.get(key, FakeResponse({}))


class FailingProvider(MarketDataProvider):
    def normalize_symbol(self, symbol):
        return symbol.upper()

    def fetch_history(self, symbol, period="1y", interval="1d"):
        return None

    def fetch_info(self, symbol):
        return {}


def _indian_provider() -> IndianDataProvider:
    settings = IndianApiConfig(
        enabled=True,
        base_url="https://api.example.test",
        api_key="secret-do-not-return",
        cache_ttl_seconds=0,
    )
    session = FakeSession({
        "stock": FakeResponse({
            "tickerId": "RELIANCE", "companyName": "Reliance Industries Limited",
            "industry": "Conglomerate", "currentPrice": {"NSE": "2,195.75"},
            "percentChange": "1.25%", "yearHigh": "2,400", "yearLow": "2,000",
        }),
        "historical_data": FakeResponse([
            {"date": "2026-01-01", "open": 100, "high": 105, "low": 99, "close": 104, "volume": 1000},
            {"date": "2026-01-02", "open": 104, "high": 106, "low": 102, "close": 105, "volume": 1200},
        ]),
        "historical_stats": FakeResponse({"trailingPE": 23.7, "marketCap": 1500000000000}),
    })
    return IndianDataProvider(client=IndianApiClient(settings, session=session))


# --------------------------------------------------------------------------- #
# IndianDataProvider
# --------------------------------------------------------------------------- #
def test_indian_provider_normalizes_to_bare_nse():
    provider = _indian_provider()
    assert provider.normalize_symbol("RELIANCE.NS") == "RELIANCE"
    assert provider.normalize_symbol("TATA.bo") == "TATA"
    assert provider.normalize_symbol(" m%26m ") == "M&M"


def test_indian_provider_fetch_history_builds_ohlcv_frame():
    provider = _indian_provider()
    df = provider.fetch_history("RELIANCE", period="1y")
    assert df is not None
    assert len(df) == 2
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert float(df["Close"].iloc[-1]) == 105.0


def test_indian_provider_fetch_history_returns_none_on_missing_ticker():
    settings = IndianApiConfig(enabled=True, base_url="https://api.example.test", api_key="k", cache_ttl_seconds=0)
    session = FakeSession({"stock": FakeResponse({})})
    provider = IndianDataProvider(client=IndianApiClient(settings, session=session))
    assert provider.fetch_history("NOPE") is None


def test_indian_provider_fetch_info_merges_fundamentals():
    provider = _indian_provider()
    info = provider.fetch_info("RELIANCE")
    assert info["longName"] == "Reliance Industries Limited"
    assert info["industry"] == "Conglomerate"
    assert info["currentPrice"] == 2195.75
    assert info["trailingPE"] == 23.7
    assert info["fiftyTwoWeekHigh"] == 2400


# --------------------------------------------------------------------------- #
# HybridDataProvider
# --------------------------------------------------------------------------- #
def test_hybrid_uses_primary_when_it_succeeds():
    primary = _indian_provider()
    fallback = FailingProvider()
    hybrid = HybridDataProvider(primary=primary, fallback=fallback)
    df = hybrid.fetch_history("RELIANCE")
    assert df is not None and len(df) == 2
    assert hybrid.provider_name == "hybrid"


def test_hybrid_falls_back_per_symbol():
    primary = FailingProvider()

    class RichFallback(MarketDataProvider):
        def normalize_symbol(self, symbol):
            return symbol.upper()

        def fetch_history(self, symbol, period="1y", interval="1d"):
            idx = pd.date_range("2026-01-01", periods=2)
            return pd.DataFrame({"Open": [1, 2], "High": [2, 3], "Low": [1, 1], "Close": [2, 3], "Volume": [10, 10]}, index=idx)

        def fetch_info(self, symbol):
            return {"longName": "Fallback Ltd."}

    hybrid = HybridDataProvider(primary=primary, fallback=RichFallback())
    assert hybrid.fetch_history("ANY") is not None
    assert hybrid.fetch_info("ANY")["longName"] == "Fallback Ltd."


def test_hybrid_normalize_and_resolve_delegate_to_primary():
    primary = _indian_provider()
    hybrid = HybridDataProvider(primary=primary, fallback=primary)
    assert hybrid.normalize_symbol("RELIANCE.NS") == "RELIANCE"


# --------------------------------------------------------------------------- #
# Bootstrap factory + runtime re-registration
# --------------------------------------------------------------------------- #
def test_bootstrap_factory_honours_market_data_provider(monkeypatch):
    from screener.bootstrap import _market_data_provider, bootstrap
    from screener.infrastructure.data.yahoo_provider import YahooDataProvider

    bootstrap()
    monkeypatch.setattr(config, "market_data_provider", "yahoo")
    assert isinstance(_market_data_provider(), YahooDataProvider)

    monkeypatch.setattr(config, "market_data_provider", "indian_api")
    assert isinstance(_market_data_provider(), IndianDataProvider)

    monkeypatch.setattr(config, "market_data_provider", "hybrid")
    assert isinstance(_market_data_provider(), HybridDataProvider)


def test_refresh_providers_re_registers_in_container(monkeypatch):
    from screener.core.container import container
    from screener.core.interfaces import MarketDataProvider
    from screener.infrastructure.data.yahoo_provider import YahooDataProvider
    from screener.bootstrap import refresh_providers, bootstrap

    bootstrap()
    monkeypatch.setattr(config, "market_data_provider", "yahoo")
    refresh_providers()
    assert isinstance(container.resolve(MarketDataProvider), YahooDataProvider)

    monkeypatch.setattr(config, "market_data_provider", "indian_api")
    refresh_providers()
    assert isinstance(container.resolve(MarketDataProvider), IndianDataProvider)


# --------------------------------------------------------------------------- #
# Admin registry / snapshot surface
# --------------------------------------------------------------------------- #
def test_editable_snapshot_exposes_provider_switches():
    snapshot = config.editable_snapshot()
    assert snapshot["market_data_provider"] in {"yahoo", "indian_api", "hybrid"}
    assert snapshot["indian_market_provider"] in {"indian_api", "yahoo"}


def test_registry_lists_provider_switches():
    keys = {item["key"] for item in ControlCenterService.registry()}
    assert "market_data_provider" in keys
    assert "indian_market_provider" in keys


def test_publish_config_validates_provider_enum(monkeypatch):
    service = ControlCenterService()
    monkeypatch.setattr(config, "market_data_provider", "yahoo")
    monkeypatch.setattr(config, "indian_market_provider", "indian_api")
    result = service.validate_config({"market_data_provider": "hybrid"})
    assert result["values"]["market_data_provider"] == "hybrid"
