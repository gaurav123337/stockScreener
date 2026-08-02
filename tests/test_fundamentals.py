"""Offline tests for the Phase-0 fundamentals + universe work:
NSE master metadata, fundamentals cache, universe loading, provider fallback,
and the value/quality filters now returning genuinely different results.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from screener import universe
from screener.core.config import config
from screener.infrastructure.data.fundamentals_cache import FundamentalsCache
from screener.infrastructure.data.nse_master import NseMasterStore
from screener.infrastructure.data.yahoo_provider import YahooDataProvider
from screener.services.analysis_service import AnalysisService
from screener.services.filter_service import FilterService
from screener.services.scoring_engine import ScoringEngine


# --------------------------------------------------------------------------- #
# NSE master metadata
# --------------------------------------------------------------------------- #
def test_nse_master_loads_nifty500_symbols():
    store = NseMasterStore()
    assert store.available
    symbols = store.symbols()
    assert len(symbols) == 500
    assert "RELIANCE" in symbols
    assert "HDFCBANK" in symbols
    assert "M&M" in symbols
    print(f"  NSE master: {len(symbols)} symbols loaded")


def test_nse_master_name_and_industry_lookup():
    store = NseMasterStore()
    assert store.name("RELIANCE") == "Reliance Industries Ltd."
    assert store.industry("RELIANCE") == "Oil Gas & Consumable Fuels"
    # Suffix- and case-tolerant lookup
    assert store.name("reliance.ns") == "Reliance Industries Ltd."
    assert store.name("RELIANCE.NS") == "Reliance Industries Ltd."
    # Separator-tolerant lookup (M&M)
    assert store.name("M%26M") == "Mahindra & Mahindra Ltd."
    # Unknown symbol -> None, never an exception
    assert store.lookup("NOTAREALSYMBOL") is None
    assert store.name("NOTAREALSYMBOL") is None
    print("  NSE master lookups OK (suffix/case/separator tolerant)")


def test_nse_master_missing_file_is_graceful(tmp_path):
    store = NseMasterStore(csv_path=tmp_path / "nope.csv")
    assert not store.available
    assert store.symbols() == []
    assert store.lookup("RELIANCE") is None


def test_universe_falls_back_to_nifty50_when_csv_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(universe, "_NIFTY500_CSV", tmp_path / "missing.csv")
    symbols = universe.nifty500_symbols()
    assert symbols == universe.NIFTY50
    assert len(symbols) == 50


def test_universe_loads_nifty500():
    symbols = universe.nifty500_symbols()
    assert len(symbols) == 500
    assert "RELIANCE" in symbols
    assert len(set(symbols)) == len(symbols)


# --------------------------------------------------------------------------- #
# Fundamentals cache
# --------------------------------------------------------------------------- #
def test_fundamentals_cache_roundtrip(tmp_path):
    cache = FundamentalsCache(tmp_path / "cache.json", ttl_seconds=3600)
    cache.set("RELIANCE", {"trailingPE": 23.7, "longName": "Reliance Industries Ltd."})
    payload = cache.get("RELIANCE")
    assert payload["trailingPE"] == 23.7
    assert payload["longName"] == "Reliance Industries Ltd."
    # Bare + suffix keys hit the same entry via the cache's own normalisation
    assert cache.get("reliance") == payload
    # Reload from disk
    reloaded = FundamentalsCache(tmp_path / "cache.json", ttl_seconds=3600)
    assert reloaded.get("RELIANCE")["trailingPE"] == 23.7


def test_fundamentals_cache_ttl_expiry(tmp_path):
    cache = FundamentalsCache(tmp_path / "cache.json", ttl_seconds=0)
    cache.set("RELIANCE", {"trailingPE": 23.7})
    assert cache.get("RELIANCE") is None


def test_fundamentals_cache_corrupt_file_is_graceful(tmp_path):
    bad = tmp_path / "cache.json"
    bad.write_text("{not valid json", encoding="utf-8")
    cache = FundamentalsCache(bad, ttl_seconds=3600)
    assert cache.get("RELIANCE") is None
    cache.set("RELIANCE", {"trailingPE": 1.0})
    assert cache.get("RELIANCE")["trailingPE"] == 1.0


# --------------------------------------------------------------------------- #
# Yahoo provider fundamentals enrichment
# --------------------------------------------------------------------------- #
def test_fetch_info_uses_cache_and_skips_scrape(tmp_path, monkeypatch):
    cache = FundamentalsCache(tmp_path / "cache.json", ttl_seconds=3600)
    cache.set("RELIANCE", {"trailingPE": 23.7, "longName": "Reliance Industries Ltd."})
    provider = YahooDataProvider(fundamentals_cache=cache, nse_master=NseMasterStore())

    def _boom(sym):
        raise AssertionError("scrape should not be called when cache is warm")

    monkeypatch.setattr(provider, "_scrape_info", _boom)
    info = provider.fetch_info("RELIANCE.NS")
    assert info["trailingPE"] == 23.7


def test_fetch_info_falls_back_to_nse_metadata(tmp_path, monkeypatch):
    cache = FundamentalsCache(tmp_path / "cache.json", ttl_seconds=3600)
    provider = YahooDataProvider(fundamentals_cache=cache, nse_master=NseMasterStore())
    monkeypatch.setattr(provider, "_scrape_info", lambda sym: {})
    info = provider.fetch_info("RELIANCE.NS")
    assert info["longName"] == "Reliance Industries Ltd."
    assert info["sector"] == "Oil Gas & Consumable Fuels"
    # Result is persisted so the next call is served from cache
    assert cache.get("RELIANCE")["sector"] == "Oil Gas & Consumable Fuels"


# --------------------------------------------------------------------------- #
# value/quality filters are now genuinely different
# --------------------------------------------------------------------------- #
def test_value_and_quality_filters_are_distinct():
    filter_service = FilterService()
    value = filter_service.get_filter("value")
    quality = filter_service.get_filter("quality")

    # Cheap but low-ROE: value agrees, quality rejects
    cheap_low_roe = {
        "peg": 0.5, "roe": 0.10, "debt_to_equity": 50,
        "rsi": 60, "score": 50, "above_sma50": True, "above_sma200": True,
        "golden_cross": True, "action": "BUY",
    }
    assert value.matches(cheap_low_roe)
    assert not quality.matches(cheap_low_roe)

    # Pricey but high-quality: quality agrees, value rejects
    pricey_high_roe = {
        "peg": 1.5, "roe": 0.25, "debt_to_equity": 40,
        "rsi": 60, "score": 50, "above_sma50": True, "above_sma200": True,
        "golden_cross": True, "action": "BUY",
    }
    assert not value.matches(pricey_high_roe)
    assert quality.matches(pricey_high_roe)
    print("  value/quality filters return distinct results")


def test_filter_fields_include_name_and_sector():
    fields = FilterService().get_filter_fields()
    assert "name" in fields
    assert "sector" in fields


# --------------------------------------------------------------------------- #
# History retry on insufficient data (TATAMOTORS-style failures)
# --------------------------------------------------------------------------- #
class _ShortThenLongProvider:
    """Mock provider: 1y yields too few rows, 2y yields a full series."""

    def __init__(self):
        self.calls: list[str] = []
        self.full = self._make_series(260)

    @staticmethod
    def _make_series(n):
        import numpy as np

        prices = list(np.linspace(100, 160, n))
        idx = pd.date_range("2025-01-01", periods=n, freq="B")
        return pd.DataFrame({
            "Open": prices, "High": [p * 1.01 for p in prices],
            "Low": [p * 0.99 for p in prices], "Close": prices,
            "Volume": [1_000_000] * n,
        }, index=idx)

    def fetch_history(self, symbol, period="1y", interval="1d"):
        self.calls.append(period)
        if period == "1y":
            return self.full.iloc[:30]  # < min_history_rows
        return self.full

    def fetch_info(self, symbol):
        return {}

    def normalize_symbol(self, symbol):
        return symbol.upper()


def test_analyze_retries_longer_period_on_insufficient_history():
    provider = _ShortThenLongProvider()
    analysis = AnalysisService(data_provider=provider, scoring_engine=ScoringEngine(use_registry=False))
    rec = analysis.analyze("TATAMOTORS")
    assert rec.error is None
    assert rec.action.value in ("BUY", "HOLD")
    assert provider.calls == ["1y", "2y"]
    print(f"  Insufficient-history retry OK (periods tried: {provider.calls})")


def test_analyze_still_reports_insufficient_history_when_all_periods_short():
    class _AlwaysShortProvider:
        def fetch_history(self, symbol, period="1y", interval="1d"):
            return pd.DataFrame({"Open": [1, 2], "High": [1.1, 2.1],
                                 "Low": [0.9, 1.9], "Close": [1, 2],
                                 "Volume": [100, 100]})

        def fetch_info(self, symbol):
            return {}

        def normalize_symbol(self, symbol):
            return symbol.upper()

    analysis = AnalysisService(
        data_provider=_AlwaysShortProvider(), scoring_engine=ScoringEngine(use_registry=False)
    )
    rec = analysis.analyze("TATAMOTORS")
    assert rec.error is not None
    assert "insufficient price history" in rec.error


def test_default_universe_is_expanded():
    # A fresh config (no persisted overrides) defaults to the Nifty 500.
    from screener.core.config import AppConfig

    assert len(AppConfig().default_universe) == 500


def test_stale_persisted_nifty50_universe_is_migrated(tmp_path):
    """A persisted config still holding the old Nifty-50 default is migrated
    to the Nifty 500 on load; custom universes are left untouched."""
    import json

    from screener.core.config import AppConfig

    legacy = {
        "data": {},
        "scoring": {},
        "risk": {},
        "knowledge": {},
        "verification": {},
        "default_universe": list(universe.NIFTY50),
    }
    cfg_file = tmp_path / "user_config.json"
    cfg_file.write_text(json.dumps(legacy), encoding="utf-8")

    app = AppConfig(data_dir=tmp_path)
    app.load_user_overrides()
    assert len(app.default_universe) == 500
    assert "RELIANCE" in app.default_universe

    # A deliberately custom universe must be preserved.
    custom = dict(legacy)
    custom["default_universe"] = ["CUSTOM1", "CUSTOM2"]
    cfg_file.write_text(json.dumps(custom), encoding="utf-8")
    app2 = AppConfig(data_dir=tmp_path)
    app2.load_user_overrides()
    assert app2.default_universe == ["CUSTOM1", "CUSTOM2"]

