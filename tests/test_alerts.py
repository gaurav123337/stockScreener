"""Offline tests for the Phase-5 alert service (price, screen-hit, MF-NAV).

Sourcing methods are overridden with fakes so no network is touched.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from screener.core.responses import ValidationError
from screener.core.subscription_models import (
    AlertRule,
    AlertRuleType,
    SubscriptionStore,
)
from screener.core.user_models import UserProfile
from screener.services.alert_service import AlertService


def make_user(user_id: str = "u1") -> UserProfile:
    return UserProfile(
        user_id=user_id,
        username=user_id,
        role="pro",
        created_at=datetime.now(timezone.utc),
    )


class FakeAlertService(AlertService):
    """AlertService with deterministic live-market fakes."""

    def __init__(self, store, prices: dict[str, float], navs: dict[str, float], screen_new: dict[str, int]):
        super().__init__(store=store)
        self.prices = prices
        self.navs = navs
        self.screen_new = screen_new

    def _fetch_price(self, symbol: str) -> float:
        if symbol not in self.prices:
            raise ValueError(f"no price for {symbol}")
        return self.prices[symbol]

    def _fetch_nav(self, scheme_code: str) -> float:
        if scheme_code not in self.navs:
            raise ValueError(f"no nav for {scheme_code}")
        return self.navs[scheme_code]

    def _screen_new_matches(self, user, rule) -> int:
        return self.screen_new.get(rule.screen_id or "", 0)


class AlertServiceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.store = SubscriptionStore(root / "subs.db")
        os.environ["SCREENER_ALERTS_OUTBOX"] = str(root / "alerts.jsonl")
        self.outbox = root / "alerts.jsonl"
        self.svc = FakeAlertService(
            self.store,
            prices={"RELIANCE": 3100.0},
            navs={"119598": 87.4},
            screen_new={"s1": 3},
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _make_rule(self, **overrides) -> AlertRule:
        base = dict(
            alert_id="a1",
            user_id="u1",
            rule_type=AlertRuleType.PRICE,
            name="RELIANCE above 3000",
            symbol="RELIANCE",
            direction="above",
            trigger_value=3000.0,
        )
        base.update(overrides)
        return AlertRule(**base)

    # ------------------------------------------------------------------- CRUD

    def test_create_price_rule(self):
        rule = self.svc.create_rule(
            make_user(),
            {"rule_type": "price", "symbol": "RELIANCE", "direction": "above",
             "trigger_value": 3000, "name": "r"},
        )
        self.assertTrue(rule.alert_id.startswith("alr_"))
        self.assertEqual(len(self.svc.list_rules(make_user())), 1)

    def test_create_requires_required_fields(self):
        with self.assertRaises(ValidationError):
            self.svc.create_rule(make_user(), {"rule_type": "price", "direction": "above",
                                               "trigger_value": 3000})
        with self.assertRaises(ValidationError):
            self.svc.create_rule(make_user(), {"rule_type": "screen_hit", "trigger_value": 1})
        with self.assertRaises(ValidationError):
            self.svc.create_rule(make_user(), {"rule_type": "mf_nav", "trigger_value": 100})

    def test_create_rejects_bad_direction(self):
        with self.assertRaises(ValidationError):
            self.svc.create_rule(
                make_user(),
                {"rule_type": "price", "symbol": "TCS", "direction": "sideways",
                 "trigger_value": 100},
            )

    def test_delete_and_reset(self):
        rule = self.svc.create_rule(
            make_user(), {"rule_type": "price", "symbol": "RELIANCE",
                          "direction": "above", "trigger_value": 3000},
        )
        self.assertTrue(self.svc.delete_rule(make_user(), rule.alert_id))
        self.assertFalse(self.svc.delete_rule(make_user(), rule.alert_id))
        self.assertFalse(self.svc.reset_rule(make_user(), rule.alert_id))

    # --------------------------------------------------------------- evaluate

    def test_price_alert_fires_above_threshold(self):
        self.store.upsert_alert(self._make_rule())  # RELIANCE 3100 > 3000
        fired = self.svc.evaluate_user_alerts(make_user())
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0]["rule_type"], "price")
        self.assertEqual(fired[0]["value"], 3100.0)
        # outbox has the notification record
        self.assertTrue(self.outbox.exists())

    def test_price_alert_one_shot_until_reset(self):
        self.store.upsert_alert(self._make_rule())
        self.svc.evaluate_user_alerts(make_user())
        fired_again = self.svc.evaluate_user_alerts(make_user())
        self.assertEqual(fired_again, [])  # no spam

        rule = self.store.get_alert("a1", "u1")
        self.assertIsNotNone(rule.last_fired_at)
        self.store.reset_alert("a1", "u1")
        fired = self.svc.evaluate_user_alerts(make_user())
        self.assertEqual(len(fired), 1)

    def test_below_direction(self):
        self.store.upsert_alert(self._make_rule(direction="below", trigger_value=3200.0))
        fired = self.svc.evaluate_user_alerts(make_user())
        self.assertEqual(len(fired), 1)

    def test_rule_that_does_not_cross_does_not_fire(self):
        self.store.upsert_alert(self._make_rule(trigger_value=4000.0))  # 3100 < 4000
        self.assertEqual(self.svc.evaluate_user_alerts(make_user()), [])

    def test_mf_nav_alert(self):
        self.store.upsert_alert(
            self._make_rule(rule_type=AlertRuleType.MF_NAV, scheme_code="119598",
                            symbol=None, trigger_value=85.0, direction="above")
        )
        fired = self.svc.evaluate_user_alerts(make_user())
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0]["rule_type"], "mf_nav")
        self.assertEqual(fired[0]["value"], 87.4)

    def test_screen_hit_alert(self):
        self.store.upsert_alert(
            self._make_rule(rule_type=AlertRuleType.SCREEN_HIT, screen_id="s1",
                            symbol=None, trigger_value=2.0)
        )
        fired = self.svc.evaluate_user_alerts(make_user())
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0]["rule_type"], "screen_hit")
        self.assertEqual(fired[0]["value"], 3.0)

    def test_disabled_rules_are_skipped(self):
        self.store.upsert_alert(self._make_rule(enabled=False))
        self.assertEqual(self.svc.evaluate_user_alerts(make_user()), [])

    def test_evaluate_tolerates_missing_data(self):
        self.store.upsert_alert(self._make_rule(symbol="UNKNOWN"))
        self.assertEqual(self.svc.evaluate_user_alerts(make_user()), [])
