"""Offline tests for the data-source visibility surface.

Covers:
- ``show_data_source`` is an editable config flag surfaced in the snapshot /
  registry and validated on publish
- provider id -> display label mapping
- ``HybridDataProvider.active_source`` reports which provider actually served
  the last call (per thread)
- ``Recommendation.data_source`` flows through ``to_scan_row``
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from screener.core.compliance import PROVIDER_LABELS, provider_label
from screener.core.config import config
from screener.core.interfaces import MarketDataProvider
from screener.core.models import Recommendation
from screener.infrastructure.data.hybrid_provider import HybridDataProvider
from screener.services.control_center_service import ControlCenterService


class EmptyProvider(MarketDataProvider):
    provider_name = "empty"

    def normalize_symbol(self, symbol):
        return symbol.upper()

    def fetch_history(self, symbol, period="1y", interval="1d"):
        return None

    def fetch_info(self, symbol):
        return {}


class RichProvider(MarketDataProvider):
    provider_name = "fmp"

    def normalize_symbol(self, symbol):
        return symbol.upper()

    def fetch_history(self, symbol, period="1y", interval="1d"):
        idx = pd.date_range("2026-01-01", periods=3)
        return pd.DataFrame(
            {"Open": [1, 2, 3], "High": [2, 3, 4], "Low": [1, 1, 2],
             "Close": [2, 3, 4], "Volume": [10, 10, 10]}, index=idx,
        )

    def fetch_info(self, symbol):
        return {"longName": "Fake Ltd."}


# --------------------------------------------------------------------------- #
# Config surface
# --------------------------------------------------------------------------- #
def test_snapshot_exposes_show_data_source():
    snapshot = config.editable_snapshot()
    assert "show_data_source" in snapshot
    assert snapshot["show_data_source"] is True


def test_registry_lists_show_data_source():
    keys = {item["key"] for item in ControlCenterService.registry()}
    assert "show_data_source" in keys


def test_publish_validates_show_data_source(monkeypatch):
    service = ControlCenterService()
    monkeypatch.setattr(config, "show_data_source", True)
    result = service.validate_config({"show_data_source": False})
    assert result["values"]["show_data_source"] is False


# --------------------------------------------------------------------------- #
# Provider labels
# --------------------------------------------------------------------------- #
def test_provider_label_maps_known_providers():
    assert provider_label("yahoo") == "Yahoo Finance"
    assert provider_label("fmp") == "Financial Modeling Prep"
    assert provider_label("alphavantage") == "Alpha Vantage"
    assert provider_label("finnhub") == "Finnhub"
    assert provider_label("indian_api") == "Indian API"
    assert PROVIDER_LABELS["hybrid"] == "Hybrid (Yahoo + Indian API)"


def test_provider_label_falls_back_to_id():
    assert provider_label("mystery") == "mystery"
    assert provider_label(None) == config.compliance.data_source_label


# --------------------------------------------------------------------------- #
# Hybrid active source
# --------------------------------------------------------------------------- #
def test_hybrid_active_source_reports_serving_provider():
    chain = HybridDataProvider(primary=EmptyProvider(), fallbacks=[RichProvider()])
    df = chain.fetch_history("ANY")
    assert df is not None
    assert chain.active_source == "fmp"


def test_hybrid_active_source_uses_primary_when_it_succeeds():
    chain = HybridDataProvider(primary=RichProvider(), fallbacks=[EmptyProvider()])
    assert chain.fetch_history("ANY") is not None
    assert chain.active_source == "fmp"


def test_hybrid_active_source_none_when_all_fail():
    chain = HybridDataProvider(primary=EmptyProvider(), fallbacks=[EmptyProvider()])
    assert chain.fetch_history("ANY") is None
    assert chain.active_source is None


# --------------------------------------------------------------------------- #
# Recommendation data_source
# --------------------------------------------------------------------------- #
def test_recommendation_to_scan_row_includes_data_source():
    rec = Recommendation(
        symbol="AAPL", action="BULLISH", score=50.0, price=100.0, data_source="fmp",
    )
    assert rec.to_scan_row()["data_source"] == "fmp"


def test_recommendation_data_source_defaults_to_none():
    rec = Recommendation(symbol="AAPL", action="NEUTRAL", score=0.0, price=100.0)
    assert rec.to_scan_row()["data_source"] is None
