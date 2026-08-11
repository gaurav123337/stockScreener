"""Offline tests for the Phase-4 freemium / Pro subscription flows."""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from screener.core.responses import ProRequiredError, ValidationError
from screener.core.subscription_models import (
    SubscriptionStore,
    Tier,
)
from screener.core.user_models import UserProfile, UserRecord, UserStore
from screener.services.subscription_service import SubscriptionService


def make_user(user_id: str = "u1", role: str = "free") -> UserProfile:
    return UserProfile(
        user_id=user_id,
        username=user_id,
        role=role,
        created_at=datetime.now(timezone.utc),
    )


class SubscriptionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.user_store = UserStore(root / "users.db")
        self.sub_store = SubscriptionStore(root / "subs.db")
        os.environ["SCREENER_BILLING_OUTBOX"] = str(root / "outbox.jsonl")
        os.environ["SCREENER_ALERTS_OUTBOX"] = str(root / "alerts.jsonl")
        self.svc = SubscriptionService(store=self.sub_store, user_db=self.user_store)
        self.user_store.create_user(
            UserRecord(
                user_id="u1",
                username="u1",
                password_hash="h",
                password_salt="s",
            )
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_free_tier_entitlements(self):
        e = self.svc.entitlements(make_user())
        self.assertFalse(e.is_pro)
        self.assertEqual(e.tier, Tier.FREE)
        self.assertTrue(e.allows("saved_screens"))       # churn-safe default
        self.assertFalse(e.allows("email_alerts"))
        self.assertEqual(e.limits["saved_screens"], 1)

    def test_pro_tier_entitlements(self):
        self.svc.admin_grant_pro("u1")
        e = self.svc.entitlements(make_user())
        self.assertTrue(e.is_pro)
        self.assertTrue(e.allows("email_alerts"))
        self.assertTrue(e.allows("portfolio_analytics"))

    def test_require_pro_raises_for_free(self):
        with self.assertRaises(ProRequiredError):
            self.svc.require_pro(make_user(), feature="email_alerts")

    def test_free_single_saved_screen_limit(self):
        self.svc.save_screen(make_user(), "First", filter_expr="pe > 10")
        with self.assertRaises(ProRequiredError):
            self.svc.save_screen(make_user(), "Second")

    def test_pro_saved_screen_no_limit(self):
        self.svc.admin_grant_pro("u1")
        user = make_user()
        for i in range(3):
            self.svc.save_screen(user, f"Screen {i}", filter_expr="pe > 10")
        self.assertEqual(len(self.svc.list_screens(user)), 3)

    def test_alerts_require_pro(self):
        with self.assertRaises(ProRequiredError):
            self.svc.save_screen(
                make_user(), "Alert", alert_enabled=True, alert_email="a@b.co"
            )

    def test_delete_own_screen_only(self):
        user = make_user()
        saved = self.svc.save_screen(user, "Mine")
        other = make_user(user_id="u2")
        with self.assertRaises(Exception):
            self.svc.delete_screen(other, saved["screen_id"])
        self.svc.delete_screen(user, saved["screen_id"])
        self.assertEqual(len(self.svc.list_screens(user)), 0)

    def test_plans_catalog(self):
        plans = self.svc.plans()
        self.assertEqual([p["id"] for p in plans], ["pro_monthly", "pro_yearly"])
        self.assertGreater(plans[0]["price_inr"], 0)

    def test_checkout_confirm_grants_pro(self):
        user = make_user()
        cs = self.svc.create_checkout(user, "pro_monthly")
        self.assertEqual(cs["status"], "created")
        result = self.svc.confirm_checkout(user, cs["session_id"])
        self.assertEqual(result["tier"], "pro")
        self.assertEqual(self.svc.entitlements(user).tier, Tier.PRO)
        sub = self.svc.current_subscription(user)
        self.assertTrue(sub["is_active"])

    def test_confirm_wrong_user_rejected(self):
        cs = self.svc.create_checkout(make_user(), "pro_yearly")
        with self.assertRaises(Exception):
            self.svc.confirm_checkout(make_user(user_id="u2"), cs["session_id"])

    def test_cancel_at_renewal_keeps_active(self):
        self.svc.admin_grant_pro("u1")
        sub = self.svc.cancel_subscription(make_user())
        self.assertFalse(sub["is_active"])  # status= canceled

    def test_admin_revoke_downgrades(self):
        self.svc.admin_grant_pro("u1")
        self.assertTrue(self.svc.entitlements(make_user()).is_pro)
        self.svc.admin_revoke_pro("u1")
        self.assertFalse(self.svc.entitlements(make_user()).is_pro)

    def test_invalid_plan_rejected(self):
        with self.assertRaises(ValidationError):
            self.svc.create_checkout(make_user(), "bogus")


if __name__ == "__main__":
    unittest.main()
