"""Security and workflow tests for product-owner control-center foundations."""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from screener.core.config import config
from screener.core.feedback_models import FeedbackRecord, FeedbackWorkflowUpdate
from screener.core.responses import AuthError, ValidationError
from screener.core.user_models import UserCreate, UserLogin, UserStore
from screener.infrastructure.persistence.feedback_store import FeedbackStore
from screener.services.auth_service import AuthService
from screener.services.control_center_service import ControlCenterService, ControlCenterStore
from screener.services.preferences_service import PreferencesService


class ControlCenterSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.users = UserStore(root / "users.db")
        self.outbox = root / "outbox.jsonl"
        self.auth = AuthService(self.users)
        self.control = ControlCenterService(
            users=self.users,
            feedback=FeedbackStore(root / "feedback.db"),
            store=ControlCenterStore(root / "control.db"),
        )

    def tearDown(self):
        self.temp.cleanup()

    def register(self, email: str = "owner@example.com"):
        with patch.dict(os.environ, {"SCREENER_AUTH_EMAIL_OUTBOX": str(self.outbox)}):
            return self.auth.register(UserCreate(
                email=email,
                password="long-password",
                password_confirmation="long-password",
                display_name="Owner",
            ))

    def outbox_token(self) -> str:
        url = json.loads(self.outbox.read_text(encoding="utf-8").splitlines()[-1])["url"]
        return url.rsplit("token=", 1)[1]

    def test_registration_creates_normal_user_and_single_use_verification(self):
        result = self.register()
        self.assertEqual(result.user.role, "user")
        token = self.outbox_token()
        self.assertIsNotNone(self.auth.verify_email(token).email_verified_at)
        with self.assertRaises(AuthError):
            self.auth.verify_email(token)

    def test_password_reset_is_enumeration_safe_and_revokes_existing_token(self):
        original = self.register()
        with patch.dict(os.environ, {"SCREENER_AUTH_EMAIL_OUTBOX": str(self.outbox)}):
            known = self.auth.request_password_reset("owner@example.com")
            unknown = self.auth.request_password_reset("missing@example.com")
        self.assertEqual(known, unknown)
        self.auth.reset_password(self.outbox_token(), "new-password", "new-password")
        with self.assertRaises(AuthError):
            self.auth.get_user_from_token(original.token)
        self.assertEqual(
            self.auth.login(UserLogin(email="owner@example.com", password="new-password")).user.email,
            "owner@example.com",
        )

    def test_suspension_revokes_token_and_reactivation_issues_valid_version(self):
        result = self.register()
        self.control.set_user_status(result.user.user_id, "suspended", "actor", "policy review")
        with self.assertRaises(AuthError):
            self.auth.get_user_from_token(result.token)
        with self.assertRaises(AuthError):
            self.auth.login(UserLogin(email="owner@example.com", password="long-password"))
        self.control.set_user_status(result.user.user_id, "active", "actor", "review complete")
        fresh = self.auth.login(UserLogin(email="owner@example.com", password="long-password"))
        self.assertEqual(self.auth.get_user_from_token(fresh.token).user_id, result.user.user_id)

    def test_status_change_is_audited_without_secret_fields(self):
        result = self.register()
        self.control.set_user_status(result.user.user_id, "suspended", "owner-id", "abuse report")
        event = self.control.audit_events()[0]
        self.assertEqual(event["actor_id"], "owner-id")
        self.assertEqual(event["reason"], "abuse report")
        self.assertNotIn("password", json.dumps(event))

    def test_product_owner_cannot_be_suspended(self):
        result = self.register()
        self.users.update_account(result.user.user_id, role="product_owner")
        with self.assertRaises(ValidationError):
            self.control.set_user_status(result.user.user_id, "suspended", "owner-id", "unsafe action")

    def test_admin_password_reset_is_audited(self):
        result = self.register()
        with patch.dict(os.environ, {"SCREENER_AUTH_EMAIL_OUTBOX": str(self.outbox)}):
            response = self.control.send_password_reset(
                result.user.user_id, "owner-id", "user requested help", self.auth
            )
        self.assertIn("eligible", response["message"])
        event = self.control.audit_events()[0]
        self.assertEqual("user.password_reset_requested", event["action"])
        self.assertEqual("user requested help", event["reason"])

    def test_audit_pagination_and_filters(self):
        result = self.register()
        self.control.set_user_status(result.user.user_id, "suspended", "owner-id", "first action")
        self.control.set_user_status(result.user.user_id, "active", "owner-id", "second action")
        page = self.control.audit_event_page(action="user.active", page=1, page_size=1)
        self.assertEqual(1, page["total"])
        self.assertEqual("user.active", page["items"][0]["action"])

    def test_feedback_filters_history_and_resolution_timestamp(self):
        feedback = FeedbackRecord(
            feedback_id="feedback-1", user_id="u1", username="reporter", category="bug",
            title="Broken scanner", document={"type": "doc", "content": []},
            plain_text="The scanner fails consistently", created_at=datetime.utcnow(),
        )
        self.control._feedback.create(feedback)
        filtered = self.control.list_feedback(search="scanner", priority="medium", category="bug")
        self.assertEqual(1, filtered["total"])
        resolved = self.control.update_feedback(
            feedback.feedback_id,
            FeedbackWorkflowUpdate(status="resolved", internal_note="Fixed", reason="verified fix"),
            "owner-id",
        )
        self.assertIsNotNone(resolved["resolved_at"])
        reopened = self.control.update_feedback(
            feedback.feedback_id,
            FeedbackWorkflowUpdate(status="triaged", reason="regression observed"),
            "owner-id",
        )
        self.assertIsNone(reopened["resolved_at"])
        self.assertEqual(2, len(self.control.feedback_detail(feedback.feedback_id)["events"]))

    def test_dashboard_reports_breakdowns_recency_and_drill_down_filters(self):
        recent = self.register("recent@example.com").user
        older = self.register("older@example.com").user
        now = datetime.now(timezone.utc)
        self.users.update_account(recent.user_id, email_verified_at=now)
        with self.users._connection() as conn:
            conn.execute(
                "UPDATE users SET created_at = ? WHERE user_id = ?",
                ((now - timedelta(days=20)).isoformat(), older.user_id),
            )

        current = FeedbackRecord(
            feedback_id="recent-feedback", user_id="guest", username="Guest", category="idea",
            title="Recent idea", document={"type": "doc", "content": []},
            plain_text="A recent product suggestion", created_at=now - timedelta(days=1),
            priority="critical",
        )
        overdue = FeedbackRecord(
            feedback_id="overdue-feedback", user_id=older.user_id, username="Older", category="bug",
            title="Overdue bug", document={"type": "doc", "content": []},
            plain_text="An unresolved old product bug", created_at=now - timedelta(days=10),
            status="triaged",
        )
        resolved = FeedbackRecord(
            feedback_id="resolved-feedback", user_id=recent.user_id, username="Recent", category="concern",
            title="Resolved concern", document={"type": "doc", "content": []},
            plain_text="An old but resolved concern", created_at=now - timedelta(days=40),
            status="resolved",
        )
        for item in (overdue, resolved, current):
            self.control._feedback.create(item)

        values = config.editable_snapshot()
        publication = self.control.publish_config(values, {}, "owner-id", "dashboard publication")
        dashboard = self.control.dashboard()

        self.assertEqual(2, dashboard["users"]["total"])
        self.assertEqual(1, dashboard["users"]["new_7d"])
        self.assertEqual(2, dashboard["users"]["new_30d"])
        self.assertEqual({"verified": 1, "pending": 1}, dashboard["users"]["by_verification"])
        self.assertEqual(2, dashboard["feedback"]["open"])
        self.assertEqual(1, dashboard["feedback"]["overdue"])
        self.assertEqual(1, dashboard["feedback"]["guest"])
        self.assertEqual(1, dashboard["feedback"]["by_age"]["over_30d"])
        self.assertEqual("recent-feedback", dashboard["recent_feedback"][0]["feedback_id"])
        self.assertEqual(publication["version"], dashboard["recent_config_publications"][0]["version"])

        self.assertEqual(1, self.control.list_users(verified=True)["total"])
        self.assertEqual(2, self.control.list_users(registered_within_days=30)["total"])
        self.assertEqual(2, self.control.list_feedback(status="open")["total"])
        self.assertEqual(1, self.control.list_feedback(age="overdue")["total"])
        self.assertEqual(1, self.control.list_feedback(user_id="guest")["total"])

    def test_config_diff_history_and_optimistic_concurrency(self):
        values = config.editable_snapshot()
        values["risk"]["atr_multiplier"] = 2.75
        diff = self.control.config_diff(values)
        self.assertTrue(any(item["key"] == "risk.atr_multiplier" for item in diff["changes"]))
        published = self.control.publish_config(values, {}, "owner-id", "adjust risk", expected_version=0)
        self.assertEqual(1, published["version"])
        self.assertEqual(1, len(self.control.config_history()))
        with self.assertRaises(ValidationError):
            self.control.publish_config(values, {}, "owner-id", "stale draft", expected_version=0)

    def test_locked_config_paths_ignore_existing_overrides_and_reject_new_ones(self):
        result = self.register("prefs@example.com")
        user_id = result.user.user_id
        self.users.update_preferences(user_id, {"risk": {"atr_multiplier": 9.0}})
        values = config.editable_snapshot()
        values["risk"]["atr_multiplier"] = 2.5
        self.control.publish_config(
            values,
            {"risk.atr_multiplier": "locked"},
            "owner-id",
            "lock risk setting",
        )

        preferences = PreferencesService(self.users, self.control._store)
        self.assertEqual(2.5, preferences.get_merged_config(user_id)["risk"]["atr_multiplier"])
        with self.assertRaises(ValidationError):
            preferences.update_preferences(user_id, {"risk": {"atr_multiplier": 4.0}})

    def test_bootstrap_requires_verified_owner_and_revokes_pre_promotion_token(self):
        result = self.register()
        with patch.dict(os.environ, {"SCREENER_PRODUCT_OWNER_EMAIL": "owner@example.com"}, clear=True):
            with self.assertRaises(RuntimeError):
                self.control.bootstrap_product_owner()

            self.users.update_account(result.user.user_id, email_verified_at=datetime.utcnow())
            self.control.bootstrap_product_owner()

        self.assertEqual("product_owner", self.users.get_by_id(result.user.user_id).role)
        with self.assertRaises(AuthError):
            self.auth.get_user_from_token(result.token)

    def test_feedback_migration_preserves_legacy_records(self):
        legacy_path = Path(self.temp.name) / "legacy-feedback.db"
        conn = sqlite3.connect(legacy_path)
        try:
            conn.execute("""CREATE TABLE feedback (
                feedback_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, username TEXT NOT NULL,
                category TEXT NOT NULL, title TEXT NOT NULL, document TEXT NOT NULL,
                plain_text TEXT NOT NULL, created_at TEXT NOT NULL)""")
            conn.execute(
                "INSERT INTO feedback VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("legacy", "u1", "old-user", "bug", "Legacy report", "{}",
                 "Legacy searchable feedback", datetime.utcnow().isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

        record = FeedbackStore(legacy_path).get("legacy")
        self.assertIsNotNone(record)
        self.assertEqual("new", record.status)
        self.assertEqual("medium", record.priority)


if __name__ == "__main__":
    unittest.main()