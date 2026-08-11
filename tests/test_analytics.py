"""Offline tests for the Phase-5 analytics layer.

The analytics store is a thin SQLite event log; every metric (DAU/WAU, funnel,
conversion, retention) is a SQL aggregate over it. These tests construct events
directly (no network, no auth) and assert the derived numbers.
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from screener.core.analytics_models import AnalyticsEvent
from screener.core.subscription_models import (
    PushSubscription,
    Subscription,
    SubscriptionStatus,
    SubscriptionStore,
)
from screener.core.user_models import UserRecord, UserStore
from screener.infrastructure.persistence.analytics_store import AnalyticsStore
from screener.services.analytics_service import AnalyticsService, FUNNEL_STEPS
from screener.services.analytics_service import _BillingMetrics


def make_db_path(tmp_path: Path) -> Path:
    return tmp_path / "analytics_test.db"


def _event(user_id: str, name: str, at: datetime, event_id: str) -> AnalyticsEvent:
    return AnalyticsEvent(
        event_id=event_id,
        user_id=user_id,
        event_name=name,
        created_at=at,
    )


class AnalyticsStoreTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "analytics.db"
        self.store = AnalyticsStore(db_path=self.db_path)
        self.now = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self._tmp.cleanup()

    def test_track_and_count_events(self):
        self.store.track(_event("u1", "scan_run", self.now, "e1"))
        self.store.track(_event("u1", "scan_run", self.now, "e2"))
        self.store.track(_event("u2", "auth_register", self.now, "e3"))
        assert self.store.count_events("scan_run") == 2
        assert self.store.distinct_users("scan_run") == 1
        assert self.store.distinct_users() == 2

    def test_dau_and_wau(self):
        today = self.now
        yesterday = today - timedelta(days=1)
        six_days_ago = today - timedelta(days=6)
        eight_days_ago = today - timedelta(days=8)
        self.store.track(_event("u1", "scan_run", today, "e1"))
        self.store.track(_event("u2", "scan_run", yesterday, "e2"))
        self.store.track(_event("u3", "scan_run", six_days_ago, "e3"))
        self.store.track(_event("u4", "scan_run", eight_days_ago, "e4"))
        assert self.store.daily_active_users(today) == 1
        assert self.store.weekly_active_users(end=today) == 3
        assert self.store.daily_active_users(six_days_ago) == 1

    def test_funnel_counts_distinct_users_per_step(self):
        self.store.track(_event("u1", "auth_register", self.now, "e1"))
        self.store.track(_event("u1", "risk_profile_saved", self.now, "e2"))
        self.store.track(_event("u2", "auth_register", self.now, "e3"))
        steps = self.store.funnel(FUNNEL_STEPS)
        by_step = {s.step: s.users for s in steps}
        assert by_step["auth_register"] == 2
        assert by_step["risk_profile_saved"] == 1
        assert by_step["scan_run"] == 0

    def test_conversion_requires_user_who_did_both(self):
        self.store.track(_event("u1", "checkout_created", self.now, "e1"))
        self.store.track(_event("u1", "checkout_paid", self.now, "e2"))
        self.store.track(_event("u2", "checkout_created", self.now, "e3"))
        rate = self.store.conversion("checkout_created", "checkout_paid")
        assert rate == 0.5

    def test_conversion_zero_when_no_base(self):
        assert self.store.conversion("checkout_created", "checkout_paid") == 0.0

    def test_retention(self):
        now = self.now
        cohort_start = now - timedelta(days=31)
        cohort_end = now - timedelta(days=30)
        return_after = cohort_end + timedelta(days=10)
        self.store.track(_event("u1", "scan_run", cohort_start, "e1"))
        self.store.track(_event("u1", "scan_run", return_after, "e2"))  # returns
        self.store.track(_event("u2", "scan_run", cohort_start, "e3"))  # never returns
        r = self.store.retention(
            cohort_window_days=2, lookback_days=30, return_window_days=90, now=now
        )
        assert r.cohort_users == 2
        assert r.returned_users == 1
        assert r.retention_rate == 0.5


class AnalyticsBillingTest(unittest.TestCase):
    """MRR / trial->paid / push opt-in derived from the billing stores."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "users.db"
        self.store = SubscriptionStore(db_path=self.db_path)
        self.user_db = UserStore(db_path=self.db_path)

    def tearDown(self):
        self._tmp.cleanup()

    def test_mrr_aggregates_active_monthly_and_yearly(self):
        self.store.upsert_subscription(Subscription(
            user_id="a", plan_id="pro_monthly",
            status=SubscriptionStatus.ACTIVE,
            renews_at=datetime.utcnow() + timedelta(days=10),
        ))
        self.store.upsert_subscription(Subscription(
            user_id="b", plan_id="pro_yearly",
            status=SubscriptionStatus.ACTIVE,
            renews_at=datetime.utcnow() + timedelta(days=100),
        ))
        self.store.upsert_subscription(Subscription(
            user_id="c", plan_id="pro_monthly",
            status=SubscriptionStatus.CANCELED,
            renews_at=datetime.utcnow() - timedelta(days=5),
        ))
        metrics = _BillingMetrics(self.store, self.user_db)
        # 199 (monthly) + 1999/12 (yearly normalized)
        assert metrics.paid_mrr() == round(199.0 + 1999.0 / 12, 2)

    def test_trial_to_paid_conversion(self):
        self.store.create_checkout("s1", "a", "pro_yearly", "sandbox", 1999.0)
        self.store.create_checkout("s2", "b", "pro_yearly", "sandbox", 1999.0)
        self.store.mark_checkout_paid("s2")
        metrics = _BillingMetrics(self.store, self.user_db)
        assert metrics.trial_to_paid_conversion() == 0.5

    def test_push_opt_in_rate(self):
        self.user_db.create_user(UserRecord(
            user_id="a", username="a", password_hash="x", password_salt="y",
        ))
        self.user_db.create_user(UserRecord(
            user_id="b", username="b", password_hash="x", password_salt="y",
        ))
        self.store.upsert_push_subscription(PushSubscription(
            user_id="a", endpoint="https://push.example/a",
        ))
        metrics = _BillingMetrics(self.store, self.user_db)
        assert metrics.push_opt_in_rate() == 0.5

    def test_overview_assembles_with_billing(self):
        # Seed one user + one paid checkout so MRR & conversion are non-zero.
        self.user_db.create_user(UserRecord(
            user_id="a", username="a", password_hash="x", password_salt="y",
        ))
        self.store.create_checkout("s1", "a", "pro_yearly", "sandbox", 1999.0)
        self.store.mark_checkout_paid("s1")
        self.store.upsert_subscription(Subscription(
            user_id="a", plan_id="pro_yearly",
            status=SubscriptionStatus.ACTIVE,
            renews_at=datetime.utcnow() + timedelta(days=100),
        ))

        store = AnalyticsStore(db_path=Path(self._tmp.name) / "analytics2.db")
        now = datetime.utcnow()
        store.track(_event("a", "auth_register", now, "e1"))
        store.track(_event("a", "checkout_created", now, "e2"))
        store.track(_event("a", "checkout_paid", now, "e3"))
        svc = AnalyticsService(store=store, billing_store=self.store, user_db=self.user_db)
        overview = svc.overview_dict()
        assert overview["total_users"] == 1
        assert overview["dau"] == 1
        assert overview["mrr_inr"] == round(1999.0 / 12, 2)
        assert overview["free_to_pro_conversion"] == 1.0
        assert overview["push_opt_in_rate"] == 0.0


class AnalyticsServiceTest(unittest.TestCase):
    def test_track_never_raises(self):
        service = AnalyticsService(
            store=AnalyticsStore(db_path=Path("/tmp/nonexistent-dir-x/x.db"))
        )
        service.track("u1", "scan_run")  # must not raise even though dir missing
