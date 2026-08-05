"""Tests for the Phase-0 trust/compliance layer added on top of PR #9:
the compliance envelope, coverage math, staleness, and the history cache
(rate-limit layer) that stops scans hammering the price provider.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from screener.core.compliance import compliance_block, coverage_ratio, is_stale
from screener.infrastructure.data.history_cache import HistoryCache
from screener.infrastructure.data.yahoo_provider import YahooDataProvider


# --------------------------------------------------------------------------- #
# Compliance framing
# --------------------------------------------------------------------------- #
def test_compliance_block_carries_disclaimers_and_source():
    block = compliance_block()
    assert block["is_investment_advice"] is False
    assert "not SEBI-registered investment advice" in block["educational_note"]
    assert "not a guarantee" in block["disclaimer"]
    assert "Yahoo Finance" in block["data_source"]
    # An explicit provider label overrides the default attribution.
    assert compliance_block("NSE bulk file")["data_source"] == "NSE bulk file"


def test_coverage_ratio_math():
    assert coverage_ratio(250, 500) == 0.5
    assert coverage_ratio(0, 500) == 0.0
    assert coverage_ratio(500, 0) == 0.0  # no universe -> never a division error
    assert coverage_ratio(500, 500) == 1.0


def test_is_stale_against_config_ttl():
    fresh = datetime.now(timezone.utc) - timedelta(seconds=60)
    assert is_stale(fresh) is False
    # A scan with no data timestamp at all is treated as stale.
    assert is_stale(None) is True
    old = datetime.now(timezone.utc) - timedelta(days=1)
    assert is_stale(old) is True


# --------------------------------------------------------------------------- #
# History cache (rate-limit layer)
# --------------------------------------------------------------------------- #
def _make_df(n=120):
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "Open": [float(i) for i in range(n)],
        "High": [float(i) + 1 for i in range(n)],
        "Low": [float(i) - 1 for i in range(n)],
        "Close": [float(i) for i in range(n)],
        "Volume": [1_000_000] * n,
    }, index=idx)


def test_history_cache_roundtrip_and_last_fetched(tmp_path):
    cache = HistoryCache(tmp_path / "history.json", ttl_seconds=3600)
    assert cache.last_fetched_at() is None
    cache.set("RELIANCE", "1y", "1d", _make_df())
    got = cache.get("RELIANCE", "1y", "1d")
    assert got is not None and len(got) == 120
    assert list(got.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert cache.last_fetched_at() is not None
    # Reload from disk
    reloaded = HistoryCache(tmp_path / "history.json", ttl_seconds=3600)
    assert reloaded.get("RELIANCE", "1y", "1d") is not None


def test_history_cache_ttl_expiry(tmp_path):
    cache = HistoryCache(tmp_path / "history.json", ttl_seconds=0)
    cache.set("RELIANCE", "1y", "1d", _make_df())
    assert cache.get("RELIANCE", "1y", "1d") is None


def test_history_cache_key_ignores_exchange_suffix(tmp_path):
    cache = HistoryCache(tmp_path / "history.json", ttl_seconds=3600)
    cache.set("RELIANCE.NS", "1y", "1d", _make_df())
    assert cache.get("reliance", "1y", "1d") is not None


def test_provider_fetch_history_uses_cache(tmp_path, monkeypatch):
    """A warm history cache means no network call on the second fetch."""
    provider = YahooDataProvider(history_cache=HistoryCache(tmp_path / "h.json", ttl_seconds=3600))
    provider._history.set("RELIANCE", "1y", "1d", _make_df())

    def _boom(*args, **kwargs):
        raise AssertionError("provider should not be hit when the cache is warm")

    monkeypatch.setattr(provider, "_download", _boom)
    df = provider.fetch_history("RELIANCE", period="1y", interval="1d")
    assert df is not None and len(df) == 120


def test_provider_fetch_history_populates_cache_on_miss(tmp_path, monkeypatch):
    provider = YahooDataProvider(history_cache=HistoryCache(tmp_path / "h.json", ttl_seconds=3600))
    monkeypatch.setattr(provider, "_download", lambda sym, period, interval: _make_df())
    df = provider.fetch_history("RELIANCE", period="1y", interval="1d")
    assert df is not None
    # Now the cache is warm and no longer touches the network.
    assert provider._history.get("RELIANCE", "1y", "1d") is not None
