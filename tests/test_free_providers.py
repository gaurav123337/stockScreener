"""Offline tests for the free REST market-data providers.

Covers:
- Alpha Vantage / FMP / Finnhub providers implement the MarketDataProvider
  contract over their real wire shapes (daily history, fundamentals mapping)
- rate-limit envelopes degrade to a miss (None / {}) instead of crashing
- the bootstrap factory honours ``alphavantage`` / ``fmp`` / ``finnhub`` and
  builds a ``chain`` from ``provider_chain`` (skipping unconfigured leaves)
- the config snapshot exposes the new provider sections + chain, and the
  admin registry marks ``api_key`` entries as sensitive
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from screener.core.config import config
from screener.core.interfaces import MarketDataProvider
from screener.infrastructure.data.alphavantage_provider import AlphaVantageProvider
from screener.infrastructure.data.finnhub_provider import FinnhubProvider
from screener.infrastructure.data.fmp_provider import FmpProvider
from screener.infrastructure.data.fundamentals_cache import FundamentalsCache
from screener.infrastructure.data.history_cache import HistoryCache
from screener.infrastructure.data.hybrid_provider import HybridDataProvider
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
    """Dispatches by substring against both the URL and the query params."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, **kwargs):
        params = kwargs.get("params") or {}
        signature = f"{url} {params}"
        self.calls.append({"url": url, "params": params})
        for needle, payload in self.responses.items():
            if needle in signature:
                return payload if isinstance(payload, FakeResponse) else FakeResponse(payload)
        return FakeResponse({}, status_code=404)


def _history(**overrides) -> HistoryCache:
    return HistoryCache(path=None, **overrides)


def _fundamentals(**overrides) -> FundamentalsCache:
    return FundamentalsCache(path=None, **overrides)


# --------------------------------------------------------------------------- #
# Alpha Vantage
# --------------------------------------------------------------------------- #
def _av_provider(session) -> AlphaVantageProvider:
    return AlphaVantageProvider(
        base_url="https://www.alphavantage.co/query",
        api_key="demo-key",
        retry_attempts=0,
        session=session,
        history_cache=_history(),
        fundamentals_cache=_fundamentals(),
    )


def test_av_normalize_strips_exchange_suffix():
    provider = _av_provider(FakeSession({}))
    assert provider.normalize_symbol("RELIANCE.NS") == "RELIANCE"
    assert provider.normalize_symbol(" tata.bo ") == "TATA"
    assert provider.provider_name == "alphavantage"


def test_av_fetch_history_builds_daily_frame():
    session = FakeSession({"TIME_SERIES_DAILY": {
        "Meta Data": {"2. Symbol": "AAPL"},
        "Time Series (Daily)": {
            "2026-07-31": {"1. open": "230", "2. high": "235", "3. low": "228", "4. close": "233", "5. volume": "1000000"},
            "2026-07-30": {"1. open": "225", "2. high": "231", "3. low": "224", "4. close": "229", "5. volume": "900000"},
        },
    }})
    df = _av_provider(session).fetch_history("AAPL")
    assert df is not None
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert float(df["Close"].iloc[-1]) == 233.0
    assert str(df.index[-1].date()) == "2026-07-31"


def test_av_rate_limit_envelope_is_a_miss():
    session = FakeSession({"TIME_SERIES_DAILY": {"Note": "Thank you for using Alpha Vantage..."}})
    assert _av_provider(session).fetch_history("AAPL") is None
    info_session = FakeSession({"OVERVIEW": {"Information": "limit reached"}})
    assert _av_provider(info_session).fetch_info("AAPL") == {}


def test_av_fetch_info_maps_overview_and_quote():
    session = FakeSession({
        "OVERVIEW": {
            "Name": "Apple Inc.", "Sector": "Technology", "Industry": "Consumer Electronics",
            "MarketCapitalization": "3000000000000", "Currency": "USD",
            "PERatio": "29.1", "PEGRatio": "2.3", "PriceToBookRatio": "45.2",
            "ReturnOnEquityTTM": "1.5", "ProfitMargin": "0.25", "Beta": "1.2",
        },
        "GLOBAL_QUOTE": {"Global Quote": {"05. price": "233.50", "10. change percent": "1.75%"}},
    })
    info = _av_provider(session).fetch_info("AAPL")
    assert info["longName"] == "Apple Inc."
    assert info["marketCap"] == 3000000000000
    assert info["trailingPE"] == 29.1
    assert info["currentPrice"] == 233.5


# --------------------------------------------------------------------------- #
# FMP
# --------------------------------------------------------------------------- #
def _fmp_provider(session) -> FmpProvider:
    return FmpProvider(
        base_url="https://financialmodelingprep.com/stable",
        api_key="demo-key",
        retry_attempts=0,
        session=session,
        history_cache=_history(),
        fundamentals_cache=_fundamentals(),
    )


def test_fmp_normalize_and_name():
    provider = _fmp_provider(FakeSession({}))
    assert provider.normalize_symbol("reliance.NS") == "RELIANCE"
    assert provider.provider_name == "fmp"


def test_fmp_fetch_history_builds_frame_from_array():
    session = FakeSession({"/historical-price-eod/full": [
        {"symbol": "AAPL", "date": "2026-07-30", "open": 225, "high": 231, "low": 224, "close": 229, "volume": 900000},
        {"symbol": "AAPL", "date": "2026-07-31", "open": 230, "high": 235, "low": 228, "close": 233, "volume": 1000000},
    ]})
    df = _fmp_provider(session).fetch_history("AAPL")
    assert df is not None
    assert float(df["Close"].iloc[-1]) == 233.0
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]


def test_fmp_fetch_history_returns_none_on_empty():
    session = FakeSession({"/historical-price-eod/full": []})
    assert _fmp_provider(session).fetch_history("AAPL") is None


def test_fmp_fetch_info_maps_profile_array():
    session = FakeSession({"/profile": [{
        "symbol": "AAPL", "companyName": "Apple Inc.", "sector": "Technology",
        "industry": "Consumer Electronics", "marketCap": 3000000000000,
        "currency": "USD", "price": 233.5, "beta": 1.2,
    }]})
    info = _fmp_provider(session).fetch_info("AAPL")
    assert info["longName"] == "Apple Inc."
    assert info["marketCap"] == 3000000000000
    assert info["currentPrice"] == 233.5


# --------------------------------------------------------------------------- #
# Finnhub
# --------------------------------------------------------------------------- #
def _finnhub_provider(session) -> FinnhubProvider:
    return FinnhubProvider(
        base_url="https://finnhub.io/api/v1",
        api_key="demo-key",
        retry_attempts=0,
        session=session,
        history_cache=_history(),
        fundamentals_cache=_fundamentals(),
    )


def test_finnhub_normalize_and_name():
    provider = _finnhub_provider(FakeSession({}))
    assert provider.normalize_symbol("RELIANCE.NS") == "RELIANCE"
    assert provider.provider_name == "finnhub"


def test_finnhub_fetch_history_maps_columnar_candles():
    session = FakeSession({"/stock/candle": {
        "s": "ok",
        "o": [221.03, 218.55, 220.0],
        "h": [222.49, 221.5, 220.94],
        "l": [217.19, 217.14, 218.83],
        "c": [217.68, 221.03, 219.89],
        "v": [33463820, 24018876, 20730608],
        "t": [1569297600, 1569384000, 1569470400],
    }})
    df = _finnhub_provider(session).fetch_history("AAPL")
    assert df is not None
    assert float(df["Close"].iloc[-1]) == 219.89
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]


def test_finnhub_no_data_is_a_miss():
    session = FakeSession({"/stock/candle": {"s": "no_data", "o": [], "h": [], "l": [], "c": [], "v": [], "t": []}})
    assert _finnhub_provider(session).fetch_history("AAPL") is None


def test_finnhub_fetch_info_maps_profile2_and_quote():
    session = FakeSession({
        "/stock/profile2": {
            "country": "US", "currency": "USD", "exchange": "NASDAQ/NMS (GLOBAL MARKET)",
            "ipo": "1980-12-12", "marketCapitalization": 1415993, "name": "Apple Inc",
            "phone": "14089961010", "shareOutstanding": 4375.48, "ticker": "AAPL",
            "weburl": "https://www.apple.com/", "logo": "https://static.finnhub.io/logo/x.png",
            "finnhubIndustry": "Technology",
        },
        "/quote": {"c": 261.74, "d": 2.29, "dp": 0.88, "h": 263.31, "l": 260.68, "o": 261.07, "pc": 259.45},
    })
    info = _finnhub_provider(session).fetch_info("AAPL")
    assert info["longName"] == "Apple Inc"
    assert info["industry"] == "Technology"
    # marketCapitalization is reported in USD millions.
    assert info["marketCap"] == 1415993 * 1_000_000
    assert info["currentPrice"] == 261.74


# --------------------------------------------------------------------------- #
# Failover chain
# --------------------------------------------------------------------------- #
class EmptyProvider(MarketDataProvider):
    def normalize_symbol(self, symbol):
        return symbol.upper()

    def fetch_history(self, symbol, period="1y", interval="1d"):
        return None

    def fetch_info(self, symbol):
        return {}


def test_hybrid_chain_tries_providers_in_order():
    fmp = _fmp_provider(FakeSession({"/historical-price-eod/full": [
        {"symbol": "AAPL", "date": "2026-07-31", "open": 1, "high": 2, "low": 1, "close": 1.5, "volume": 10},
    ]}))
    chain = HybridDataProvider(primary=EmptyProvider(), fallbacks=[EmptyProvider(), fmp])
    df = chain.fetch_history("AAPL")
    assert df is not None and len(df) == 1


def test_hybrid_chain_info_falls_back():
    fmp = _fmp_provider(FakeSession({"/profile": [{"companyName": "Apple Inc.", "price": 233.5}]}))
    chain = HybridDataProvider(primary=EmptyProvider(), fallbacks=[fmp])
    assert chain.fetch_info("AAPL")["longName"] == "Apple Inc."


# --------------------------------------------------------------------------- #
# Bootstrap factory + config surface
# --------------------------------------------------------------------------- #
def test_bootstrap_factory_honours_free_providers(monkeypatch):
    from screener.bootstrap import _market_data_provider, bootstrap

    bootstrap()
    monkeypatch.setattr(config, "market_data_provider", "alphavantage")
    assert isinstance(_market_data_provider(), AlphaVantageProvider)
    monkeypatch.setattr(config, "market_data_provider", "fmp")
    assert isinstance(_market_data_provider(), FmpProvider)
    monkeypatch.setattr(config, "market_data_provider", "finnhub")
    assert isinstance(_market_data_provider(), FinnhubProvider)


def test_bootstrap_chain_skips_unconfigured_free_providers(monkeypatch):
    from screener.bootstrap import _market_data_provider
    from screener.infrastructure.data.yahoo_provider import YahooDataProvider

    monkeypatch.setattr(config, "market_data_provider", "chain")
    # No free keys configured -> chain reduces to Yahoo.
    monkeypatch.setattr(config.alphavantage, "api_key", "")
    monkeypatch.setattr(config.fmp, "api_key", "")
    monkeypatch.setattr(config.finnhub, "api_key", "")
    monkeypatch.setattr(config, "provider_chain", ["fmp", "alphavantage", "finnhub", "yahoo"])
    assert isinstance(_market_data_provider(), YahooDataProvider)


def test_bootstrap_chain_includes_configured_free_provider(monkeypatch):
    from screener.bootstrap import _market_data_provider
    from screener.infrastructure.data.hybrid_provider import HybridDataProvider

    monkeypatch.setattr(config, "market_data_provider", "chain")
    monkeypatch.setattr(config.fmp, "api_key", "fmp-secret")
    monkeypatch.setattr(config.alphavantage, "api_key", "")
    monkeypatch.setattr(config, "provider_chain", ["fmp", "alphavantage", "yahoo"])
    chain = _market_data_provider()
    assert isinstance(chain, HybridDataProvider)
    assert isinstance(chain._providers[0], FmpProvider)


def test_snapshot_exposes_provider_sections_and_chain():
    snapshot = config.editable_snapshot()
    for section in ("alphavantage", "fmp", "finnhub"):
        assert isinstance(snapshot[section], dict)
        assert "api_key" in snapshot[section]
    assert isinstance(snapshot["provider_chain"], list)
    assert snapshot["market_data_provider"] in {
        "yahoo", "indian_api", "hybrid", "alphavantage", "fmp", "finnhub", "chain",
    }


def test_registry_marks_api_keys_sensitive():
    entries = {item["key"]: item for item in ControlCenterService.registry()}
    assert entries["fmp.api_key"]["sensitive"] is True
    assert entries["alphavantage.api_key"]["sensitive"] is True
    assert entries["finnhub.api_key"]["sensitive"] is True


def test_publish_validates_chain(monkeypatch):
    service = ControlCenterService()
    monkeypatch.setattr(config, "market_data_provider", "yahoo")
    result = service.validate_config({
        "market_data_provider": "chain",
        "provider_chain": ["fmp", "yahoo"],
    })
    assert result["values"]["market_data_provider"] == "chain"
    assert result["values"]["provider_chain"] == ["fmp", "yahoo"]

    with pytest.raises(Exception):
        service.validate_config({"provider_chain": ["bogus"]})
