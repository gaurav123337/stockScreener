"""Tests for the Indian market provider-adapter pattern + recommendation engine.

Covers:
- every adapter reports its ``provider_name`` (swap is a config change)
- indian_api history points are normalised onto common OHLCV keys
- the Yahoo adapter maps Yahoo data onto the same common-key contract
- unsupported research endpoints degrade gracefully instead of raising
- bootstrap selects the adapter from ``config.indian_market_provider``
- the recommendation engine ranks, filters by action, and never fails whole-run
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from screener.core.config import IndianApiConfig, config
from screener.core.indian_market import IndianMarketGateway
from screener.core.interfaces import MarketDataProvider
from screener.core.models import Action, Recommendation, StockMetrics
from screener.infrastructure.data.indian_api_client import IndianApiClient
from screener.infrastructure.data.yahoo_indian_provider import YahooIndianProvider
from screener.services.indian_market_service import IndianMarketService
from screener.services.recommendation_service import RecommendationService


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
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return self.response


class MockProvider(MarketDataProvider):
    """Deterministic offline market-data provider for adapter tests."""

    def __init__(self):
        self.calls = []

    def normalize_symbol(self, symbol, exchange="NS"):
        s = symbol.strip().upper()
        if not s.endswith((".NS", ".BO")):
            s = f"{s}.NS"
        return s

    def fetch_history(self, symbol, period="1y", interval="1d"):
        self.calls.append(("history", symbol, period))
        idx = pd.date_range("2026-01-01", periods=5, freq="D")
        return pd.DataFrame(
            {
                "Open": [100, 101, 102, 103, 104],
                "High": [101, 102, 103, 104, 105],
                "Low": [99, 100, 101, 102, 103],
                "Close": [100, 101, 102, 103, 104],
                "Volume": [1000, 1000, 1000, 1000, 1000],
            },
            index=idx,
        )

    def fetch_info(self, symbol):
        self.calls.append(("info", symbol))
        return {
            "longName": "Reliance Industries Ltd.",
            "industry": "Oil Gas & Consumable Fuels",
            "currentPrice": 104.0,
            "fiftyTwoWeekHigh": 120.0,
            "fiftyTwoWeekLow": 90.0,
            "trailingPE": 23.7,
            "pegRatio": 0.82,
        }


class StubGateway(IndianMarketGateway):
    """Minimal ABC subclass used to check envelope provider propagation."""

    provider_name = "stub"

    def stock(self, name):
        from screener.core.indian_market import StockSummary

        return StockSummary(ticker_id=name.upper())

    def search(self, endpoint, query):
        return []

    def snapshot(self, endpoint):
        from screener.core.indian_market import MarketSnapshot

        return MarketSnapshot(category=endpoint, items=[])

    def history(self, stock_id, **params):
        from screener.core.indian_market import HistoricalSeries

        return HistoricalSeries(stock_id=stock_id, points=[])

    def historical_stats(self, stock_id, **params):
        from screener.core.indian_market import HistoricalStats

        return HistoricalStats(stock_id=stock_id, stats={})

    def analysis(self, endpoint, stock_id, **params):
        return {}

    def telemetry(self):
        from screener.core.indian_market import IndianApiTelemetry

        return IndianApiTelemetry()


# --------------------------------------------------------------------------- #
# Provider identity
# --------------------------------------------------------------------------- #
def test_adapters_expose_provider_name():
    assert IndianApiClient(IndianApiConfig(enabled=True)).provider_name == "indian_api"
    assert YahooIndianProvider(MockProvider()).provider_name == "yahoo"


def test_service_envelope_reports_gateway_provider(monkeypatch):
    monkeypatch.setattr(config.indian_api, "enabled", True)
    assert IndianMarketService(StubGateway()).stock("RELIANCE")["provider"] == "stub"


# --------------------------------------------------------------------------- #
# indian_api adapter: common-key normalisation
# --------------------------------------------------------------------------- #
def test_indian_api_history_points_are_normalized():
    session = FakeSession(FakeResponse([{"timestamp": "2026-01-01", "price": 100, "volume": 5}]))
    api = IndianApiClient(IndianApiConfig(enabled=True, api_key="k"), session=session)
    series = api.history("RELIANCE")
    point = series.points[0]
    assert point["date"] == "2026-01-01"
    assert point["close"] == 100
    assert point["timestamp"] == "2026-01-01"  # original key preserved


# --------------------------------------------------------------------------- #
# Yahoo adapter: common-key contract
# --------------------------------------------------------------------------- #
def test_yahoo_stock_builds_summary():
    provider = YahooIndianProvider(MockProvider())
    summary = provider.stock("RELIANCE")
    assert summary.ticker_id == "RELIANCE"
    assert summary.company_name == "Reliance Industries Ltd."
    assert summary.industry == "Oil Gas & Consumable Fuels"
    assert summary.current_price == {"NSE": 104.0}
    assert summary.percent_change == pytest.approx(0.97, abs=0.01)
    assert summary.year_high == 120.0


def test_yahoo_industry_search_uses_offline_nse_master():
    provider = YahooIndianProvider(MockProvider())
    results = provider.search("industry_search", "RELIANCE")
    assert results and results[0]["ticker_id"] == "RELIANCE"
    assert results[0]["company_name"] == "Reliance Industries Ltd."


def test_yahoo_unsupported_endpoints_are_degraded_not_breaking():
    provider = YahooIndianProvider(MockProvider())
    assert provider.search("mutual_fund_search", "hdfc") == []
    snapshot = provider.snapshot("trending")
    assert snapshot.category == "trending"
    assert snapshot.items == []
    assert provider.analysis("stock_forecasts", "RELIANCE") == {}
    assert provider.analysis("mutual_funds", "RELIANCE") == {}


def test_yahoo_unknown_endpoints_raise():
    provider = YahooIndianProvider(MockProvider())
    with pytest.raises(ValueError, match="unsupported Indian market endpoint"):
        provider.search("nope", "x")
    with pytest.raises(ValueError, match="unsupported analytical endpoint"):
        provider.analysis("nope", "RELIANCE")


def test_yahoo_history_and_stats_map_to_common_keys():
    provider = YahooIndianProvider(MockProvider())
    series = provider.history("RELIANCE.NS", period="1Y")
    assert len(series.points) == 5
    point = series.points[0]
    assert set(("date", "open", "high", "low", "close", "volume")) <= set(point)
    assert point["close"] == 100.0
    assert point["volume"] == 1000

    stats = provider.historical_stats("RELIANCE.NS")
    assert stats.stats["trailingPE"] == 23.7
    assert stats.stats["pegRatio"] == 0.82


def test_yahoo_target_price_uses_52w_high_when_above_price():
    provider = YahooIndianProvider(MockProvider())
    result = provider.analysis("stock_target_price", "RELIANCE.NS")
    assert result == {"target_price": 120.0, "current_price": 104.0}


# --------------------------------------------------------------------------- #
# Provider selection (the actual swap)
# --------------------------------------------------------------------------- #
def test_bootstrap_selects_provider_from_config(monkeypatch):
    from screener.bootstrap import _indian_gateway, bootstrap

    bootstrap()
    monkeypatch.setattr(config, "indian_market_provider", "yahoo")
    assert _indian_gateway().provider_name == "yahoo"
    monkeypatch.setattr(config, "indian_market_provider", "indian_api")
    assert _indian_gateway().provider_name == "indian_api"


def test_rollout_status_reports_active_provider(monkeypatch):
    monkeypatch.setattr(config.indian_api, "enabled", True)
    monkeypatch.setattr(config, "indian_market_provider", "yahoo")
    status = IndianMarketService(StubGateway()).rollout_status()
    assert status["provider"] == "yahoo"
    assert status["configured"] is True


# --------------------------------------------------------------------------- #
# Recommendation engine
# --------------------------------------------------------------------------- #
class FakeAnalysis:
    def __init__(self, results):
        self._results = results

    def analyze(self, symbol, app_config=None):
        return self._results.get(symbol) or Recommendation(
            symbol=symbol.upper() + ".NS",
            action=Action.HOLD,
            score=0.0,
            price=0.0,
            error="insufficient price history",
        )


def _recommendation(symbol, action, score, price, name=None, sector=None):
    return Recommendation(
        symbol=symbol,
        action=action,
        score=score,
        price=price,
        reasons=["r1"],
        metrics=StockMetrics(name=name, sector=sector),
    )


def test_recommendation_engine_ranks_and_skips_failures():
    analysis = FakeAnalysis({
        "A": _recommendation("A.NS", Action.BUY, 80, 100, "A Ltd", "Tech"),
        "B": _recommendation("B.NS", Action.BUY, 60, 50, "B Ltd", "Fin"),
        "C": _recommendation("C.NS", Action.HOLD, 40, 20, "C Ltd"),
    })
    engine = RecommendationService(analysis=analysis, data_provider=MockProvider())

    out = engine.recommend_stocks(universe=["A", "B", "C", "MISSING"], limit=10)
    assert out["total_scanned"] == 4
    assert out["count"] == 3
    assert [r["symbol"] for r in out["results"]] == ["A.NS", "B.NS", "C.NS"]
    assert out["results"][0]["name"] == "A Ltd"
    assert out["failed"] == [{"symbol": "MISSING", "error": "insufficient price history"}]


def test_recommendation_engine_respects_limit_and_action():
    analysis = FakeAnalysis({
        "A": _recommendation("A.NS", Action.BUY, 80, 100),
        "B": _recommendation("B.NS", Action.BUY, 60, 50),
        "C": _recommendation("C.NS", Action.HOLD, 40, 20),
    })
    engine = RecommendationService(analysis=analysis, data_provider=MockProvider())

    assert engine.recommend_stocks(universe=["A", "B", "C"], limit=1)["count"] == 1
    buy = engine.recommend_stocks(universe=["A", "B", "C"], limit=10, action="BUY")
    assert buy["count"] == 2
    assert all(r["action"] == "BUY" for r in buy["results"])


def test_recommendation_endpoint_is_registered_and_authenticated():
    import api as api_module

    route = next(
        route for route in api_module.app.routes
        if getattr(route, "path", None) == "/api/recommendations"
    )
    dependencies = [dependency.call for dependency in route.dependant.dependencies]
    assert api_module.get_current_user in dependencies
