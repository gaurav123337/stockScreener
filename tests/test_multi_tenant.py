"""Offline tests for tenant isolation and preference-driven analysis."""
from __future__ import annotations

import copy
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from screener.core.config import config
from screener.core.models import Action
from screener.core.responses import ValidationError
from screener.core.user_models import UserRecord, UserStore
from screener.services.analysis_service import AnalysisService
from screener.services.preferences_service import PreferencesService


class StaticDataProvider:
    def __init__(self, history: pd.DataFrame):
        self._history = history

    def fetch_history(self, symbol: str, period: str = "1y", interval: str = "1d"):
        return self._history.copy()

    def fetch_info(self, symbol: str) -> dict:
        return {"pegRatio": 0.8, "returnOnEquity": 0.2}

    def normalize_symbol(self, symbol: str) -> str:
        return symbol.upper()


def make_history(size: int = 260) -> pd.DataFrame:
    prices = list(np.linspace(100, 160, size))
    index = pd.date_range("2025-01-01", periods=size, freq="B")
    return pd.DataFrame(
        {
            "Open": prices,
            "High": [price * 1.01 for price in prices],
            "Low": [price * 0.99 for price in prices],
            "Close": prices,
            "Volume": [1_000_000] * size,
        },
        index=index,
    )


class MultiTenantTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        store = UserStore(Path(self._temp_dir.name) / "users.db")
        for user_id in ("tenant-a", "tenant-b"):
            store.create_user(
                UserRecord(
                    user_id=user_id,
                    username=user_id,
                    password_hash="unused",
                    password_salt="unused",
                    created_at=datetime.now(),
                )
            )
        self.preferences = PreferencesService(store)

    def tearDown(self):
        self._temp_dir.cleanup()

    def test_preferences_and_watchlists_are_isolated(self):
        self.preferences.update_preferences(
            "tenant-a", {"scoring": {"buy_threshold": 90}}
        )
        self.preferences.set_watchlist("tenant-a", [" infy ", "INFY", "tcs"])
        self.preferences.set_watchlist("tenant-b", ["reliance"])

        self.assertEqual(
            self.preferences.get_merged_config("tenant-a")["scoring"]["buy_threshold"],
            90,
        )
        self.assertEqual(
            self.preferences.get_merged_config("tenant-b")["scoring"]["buy_threshold"],
            config.scoring.buy_threshold,
        )
        self.assertEqual(self.preferences.get_watchlist("tenant-a"), ["INFY", "TCS"])
        self.assertEqual(self.preferences.get_watchlist("tenant-b"), ["RELIANCE"])

    def test_invalid_nested_preference_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.preferences.update_preferences(
                "tenant-a", {"scoring": {"invented_weight": 10}}
            )

    def test_effective_config_changes_analysis_without_global_mutation(self):
        analysis = AnalysisService(data_provider=StaticDataProvider(make_history()))
        original_threshold = config.scoring.buy_threshold
        self.preferences.update_preferences(
            "tenant-a", {"scoring": {"buy_threshold": 90}}
        )

        default_result = analysis.analyze("TEST.NS")
        tenant_result = analysis.analyze(
            "TEST.NS", self.preferences.get_effective_config("tenant-a")
        )

        self.assertEqual(default_result.action, Action.BUY)
        self.assertEqual(tenant_result.action, Action.HOLD)
        self.assertEqual(config.scoring.buy_threshold, original_threshold)

    def test_insufficient_history_has_no_actionable_levels(self):
        analysis = AnalysisService(data_provider=StaticDataProvider(make_history(20)))

        result = analysis.analyze("TEST.NS", copy.copy(config))

        self.assertEqual(result.action, Action.HOLD)
        self.assertIsNotNone(result.error)
        self.assertIsNone(result.entry)
        self.assertIsNone(result.target)
        self.assertIsNone(result.stop_loss)


if __name__ == "__main__":
    unittest.main()