"""Product-owner operations with redacted responses and immutable audit events."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from screener.core.config import AppConfig, config
from screener.core.feedback_models import FeedbackWorkflowUpdate
from screener.core.responses import NotFoundError, ValidationError
from screener.core.user_models import UserRecord, UserStore, user_store
from screener.infrastructure.persistence.feedback_store import FeedbackStore


class ControlCenterStore:
    def __init__(self, db_path: Path | None = None):
        path = db_path or config.data_dir / "control_center.db"
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = str(path)
        self._init_db()

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY, actor_id TEXT NOT NULL, action TEXT NOT NULL,
                    target_type TEXT NOT NULL, target_id TEXT NOT NULL, reason TEXT NOT NULL,
                    changes TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS global_config_versions (
                    version INTEGER PRIMARY KEY AUTOINCREMENT, values_json TEXT NOT NULL,
                    policies_json TEXT NOT NULL, actor_id TEXT NOT NULL, reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS global_config_state (
                    singleton INTEGER PRIMARY KEY CHECK(singleton = 1), active_version INTEGER
                );
                INSERT OR IGNORE INTO global_config_state(singleton, active_version) VALUES (1, NULL);
                CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_events(created_at DESC);
            """)
            conn.execute("PRAGMA user_version = 1")

    def audit(self, actor_id: str, action: str, target_type: str, target_id: str, reason: str, changes: dict[str, Any]) -> None:
        with self._connection() as conn:
            conn.execute(
                "INSERT INTO audit_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (str(uuid4()), actor_id, action, target_type, target_id, reason,
                 json.dumps(changes), datetime.now(timezone.utc).isoformat()),
            )

    def list_audit(self, action: str | None = None, target_type: str | None = None,
                   page: int = 1, page_size: int = 25) -> dict[str, Any]:
        with self._connection() as conn:
            clauses: list[str] = []
            params: list[Any] = []
            if action:
                clauses.append("action = ?")
                params.append(action)
            if target_type:
                clauses.append("target_type = ?")
                params.append(target_type)
            where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
            total = int(conn.execute(f"SELECT COUNT(*) FROM audit_events{where}", params).fetchone()[0])
            rows = conn.execute(
                f"SELECT * FROM audit_events{where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (*params, page_size, (page - 1) * page_size),
            ).fetchall()
        return {"items": [{**dict(row), "changes": json.loads(row["changes"])} for row in rows],
                "total": total, "page": page, "page_size": page_size}

    def current_config(self) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute("""SELECT v.* FROM global_config_versions v
                JOIN global_config_state s ON s.active_version = v.version WHERE s.singleton = 1""").fetchone()
        if not row:
            return None
        return {**dict(row), "values": json.loads(row["values_json"]), "policies": json.loads(row["policies_json"])}

    def config_history(self) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM global_config_versions ORDER BY version DESC").fetchall()
        return [{**dict(row), "values": json.loads(row["values_json"]), "policies": json.loads(row["policies_json"])} for row in rows]

    def config_version(self, version: int) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM global_config_versions WHERE version = ?", (version,)).fetchone()
        return ({**dict(row), "values": json.loads(row["values_json"]),
                 "policies": json.loads(row["policies_json"])}) if row else None

    def publish_config(self, values: dict[str, Any], policies: dict[str, str], actor_id: str, reason: str) -> dict[str, Any]:
        with self._connection() as conn:
            cursor = conn.execute(
                "INSERT INTO global_config_versions(values_json, policies_json, actor_id, reason, created_at) VALUES (?, ?, ?, ?, ?)",
                (json.dumps(values), json.dumps(policies), actor_id, reason, datetime.now(timezone.utc).isoformat()),
            )
            version = int(cursor.lastrowid)
            conn.execute("UPDATE global_config_state SET active_version = ? WHERE singleton = 1", (version,))
        return self.current_config() or {}


class ControlCenterService:
    def __init__(self, users: UserStore | None = None, feedback: FeedbackStore | None = None, store: ControlCenterStore | None = None):
        self._users = users or user_store
        self._feedback = feedback or FeedbackStore()
        self._store = store or ControlCenterStore()

    @staticmethod
    def _user_dto(user: UserRecord) -> dict[str, Any]:
        return {
            "user_id": user.user_id, "username": user.username, "email": user.email,
            "display_name": user.display_name, "role": user.role, "status": user.status,
            "email_verified_at": user.email_verified_at.isoformat() if user.email_verified_at else None,
            "created_at": user.created_at.isoformat(),
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            "preferences": user.preferences,
        }

    def bootstrap_product_owner(self) -> None:
        user_id = os.getenv("SCREENER_PRODUCT_OWNER_USER_ID", "").strip()
        email = os.getenv("SCREENER_PRODUCT_OWNER_EMAIL", "").strip().lower()
        if not (user_id or email):
            return
        user = self._users.get_by_id(user_id) if user_id else self._users.get_by_email(email)
        if not user:
            raise RuntimeError("Configured product-owner account was not found")
        if not user.email_verified_at:
            raise RuntimeError("Configured product-owner account must have a verified email")
        if user and user.role != "product_owner":
            self._users.update_account(
                user.user_id,
                role="product_owner",
                token_version=user.token_version + 1,
            )

    def load_active_config(self) -> None:
        current = self._store.current_config()
        if current:
            config._apply(current["values"])
            config._persist(current["values"])

    def dashboard(self) -> dict[str, Any]:
        users = [user for user in self._users.list_users() if user.user_id != "guest"]
        feedback = self._feedback.list_all()
        now = datetime.now(timezone.utc)
        cutoff_7d = now - timedelta(days=7)
        cutoff_30d = now - timedelta(days=30)

        def utc(timestamp: datetime) -> datetime:
            return timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)

        def age_days(created_at: datetime) -> float:
            return max(0, (now - utc(created_at)).total_seconds() / 86400)

        statuses = ("new", "triaged", "planned", "in_progress", "resolved", "closed")
        categories = ("bug", "concern", "idea", "other")
        priorities = ("low", "medium", "high", "critical")
        ages = {"under_7d": 0, "7_to_30d": 0, "over_30d": 0}
        for item in feedback:
            age = age_days(item.created_at)
            ages["under_7d" if age < 7 else "7_to_30d" if age < 30 else "over_30d"] += 1
        return {
            "users": {"total": len(users), "verified": sum(user.email_verified_at is not None for user in users),
                      "active": sum(user.status == "active" for user in users),
                       "new_7d": sum(utc(user.created_at) >= cutoff_7d for user in users),
                       "new_30d": sum(utc(user.created_at) >= cutoff_30d for user in users),
                       "by_status": {status: sum(user.status == status for user in users) for status in ("active", "suspended")},
                       "by_verification": {"verified": sum(user.email_verified_at is not None for user in users),
                                           "pending": sum(user.email_verified_at is None for user in users)}},
            "feedback": {"total": len(feedback), "guest": sum(item.user_id == "guest" for item in feedback),
                         "open": sum(item.status not in {"resolved", "closed"} for item in feedback),
                         "critical": sum(item.priority == "critical" for item in feedback),
                         "overdue": sum(item.status not in {"resolved", "closed"} and age_days(item.created_at) >= 7 for item in feedback),
                         "by_status": {status: sum(item.status == status for item in feedback) for status in statuses},
                         "by_category": {category: sum(item.category == category for item in feedback) for category in categories},
                         "by_priority": {priority: sum(item.priority == priority for item in feedback) for priority in priorities},
                         "by_age": ages},
            "recent_users": [self._user_dto(user) for user in sorted(
                users, key=lambda item: utc(item.created_at), reverse=True
            )[:5]],
            "recent_feedback": [item.model_dump(mode="json") for item in sorted(
                feedback, key=lambda item: utc(item.created_at), reverse=True
            )[:5]],
            "recent_config_publications": self._store.config_history()[:5],
        }

    def list_users(self, search: str = "", role: str | None = None, status: str | None = None,
                   verified: bool | None = None, registered_within_days: int | None = None,
                   page: int = 1, page_size: int = 25) -> dict[str, Any]:
        needle = search.strip().lower()
        items = [user for user in self._users.list_users() if user.user_id != "guest"]
        if needle:
            items = [user for user in items if needle in " ".join(filter(None, [user.email, user.username, user.display_name])).lower()]
        if role:
            items = [user for user in items if user.role == role]
        if status:
            items = [user for user in items if user.status == status]
        if verified is not None:
            items = [user for user in items if (user.email_verified_at is not None) == verified]
        if registered_within_days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=registered_within_days)
            items = [user for user in items if (user.created_at if user.created_at.tzinfo else user.created_at.replace(tzinfo=timezone.utc)) >= cutoff]
        start = (page - 1) * page_size
        return {"items": [self._user_dto(user) for user in items[start:start + page_size]], "total": len(items), "page": page, "page_size": page_size}

    def user_detail(self, user_id: str) -> dict[str, Any]:
        user = self._users.get_by_id(user_id)
        if not user or user.user_id == "guest":
            raise NotFoundError("User not found")
        return self._user_dto(user)

    def set_user_status(self, user_id: str, status: str, actor_id: str, reason: str) -> dict[str, Any]:
        if status not in {"active", "suspended"}:
            raise ValidationError("Account status must be active or suspended")
        user = self._users.get_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")
        if user.role == "product_owner" and status == "suspended":
            raise ValidationError("Product-owner accounts cannot be suspended from the control center")
        updated = self._users.update_account(user_id, status=status, token_version=user.token_version + 1)
        self._store.audit(actor_id, f"user.{status}", "user", user_id, reason, {"status": [user.status, status]})
        return self._user_dto(updated or user)

    def send_password_reset(self, user_id: str, actor_id: str, reason: str, auth_service: Any) -> dict[str, str]:
        user = self._users.get_by_id(user_id)
        if not user or user.user_id == "guest":
            raise NotFoundError("User not found")
        if user.email and user.status == "active":
            auth_service.request_password_reset(user.email)
        self._store.audit(actor_id, "user.password_reset_requested", "user", user_id, reason, {})
        return {"message": "If the account is eligible, a password reset link has been sent."}

    def list_feedback(self, search: str = "", status: str | None = None, priority: str | None = None,
                      category: str | None = None, user_id: str | None = None,
                      assignee_id: str | None = None, age: str | None = None,
                      page: int = 1, page_size: int = 25) -> dict[str, Any]:
        needle = search.strip().lower()
        items = self._feedback.list_all()
        if needle:
            items = [item for item in items if needle in f"{item.title} {item.plain_text} {item.username}".lower()]
        if status == "open":
            items = [item for item in items if item.status not in {"resolved", "closed"}]
        elif status:
            items = [item for item in items if item.status == status]
        if priority:
            items = [item for item in items if item.priority == priority]
        if category:
            items = [item for item in items if item.category == category]
        if user_id:
            items = [item for item in items if item.user_id == user_id]
        if assignee_id:
            items = [item for item in items if item.assignee_id == assignee_id]
        if age:
            now = datetime.now(timezone.utc)
            def days_old(item: Any) -> float:
                created_at = item.created_at if item.created_at.tzinfo else item.created_at.replace(tzinfo=timezone.utc)
                return max(0, (now - created_at).total_seconds() / 86400)
            if age == "under_7d":
                items = [item for item in items if days_old(item) < 7]
            elif age == "7_to_30d":
                items = [item for item in items if 7 <= days_old(item) < 30]
            elif age == "over_30d":
                items = [item for item in items if days_old(item) >= 30]
            elif age == "overdue":
                items = [item for item in items if item.status not in {"resolved", "closed"} and days_old(item) >= 7]
        start = (page - 1) * page_size
        return {"items": [item.model_dump(mode="json") for item in items[start:start + page_size]], "total": len(items), "page": page, "page_size": page_size}

    def feedback_detail(self, feedback_id: str) -> dict[str, Any]:
        item = self._feedback.get(feedback_id)
        if not item:
            raise NotFoundError("Feedback not found")
        return {"feedback": item.model_dump(mode="json"), "events": self._feedback.list_events(feedback_id)}

    def update_feedback(self, feedback_id: str, body: FeedbackWorkflowUpdate, actor_id: str) -> dict[str, Any]:
        current = self._feedback.get(feedback_id)
        if not current:
            raise NotFoundError("Feedback not found")
        now = datetime.now(timezone.utc).isoformat()
        changes: dict[str, Any] = {"updated_at": now}
        event_changes: dict[str, Any] = {}
        for key in ("status", "priority", "assignee_id"):
            value = getattr(body, key)
            if value is not None and value != getattr(current, key):
                changes[key] = value
                event_changes[key] = [getattr(current, key), value]
        if body.status == "resolved":
            changes["resolved_at"] = now
        elif body.status is not None and current.resolved_at is not None:
            changes["resolved_at"] = None
        event = {"event_id": str(uuid4()), "actor_id": actor_id, "event_type": "workflow_updated",
                 "changes": event_changes, "note": body.internal_note, "reason": body.reason, "created_at": now}
        updated = self._feedback.update_workflow(feedback_id, changes, event)
        self._store.audit(actor_id, "feedback.updated", "feedback", feedback_id, body.reason, event_changes)
        return updated.model_dump(mode="json") if updated else {}

    @staticmethod
    def registry() -> list[dict[str, Any]]:
        snapshot = config.editable_snapshot()
        result: list[dict[str, Any]] = []
        for section, values in snapshot.items():
            if isinstance(values, dict):
                for key, value in values.items():
                    result.append({"key": f"{section}.{key}", "section": section, "label": key.replace("_", " ").title(),
                                   "type": type(value).__name__, "default": value, "sensitive": False, "user_overridable": True})
            else:
                result.append({"key": section, "section": "universe", "label": "Default Universe", "type": "list",
                               "default": values, "sensitive": False, "user_overridable": True})
        return result

    def current_config(self) -> dict[str, Any]:
        current = self._store.current_config()
        return current or {"version": 0, "values": config.editable_snapshot(), "policies": {}}

    def config_history(self) -> list[dict[str, Any]]:
        return self._store.config_history()

    @staticmethod
    def _diff_values(before: Any, after: Any, prefix: str = "") -> list[dict[str, Any]]:
        if isinstance(before, dict) and isinstance(after, dict):
            changes: list[dict[str, Any]] = []
            for key in sorted(set(before) | set(after)):
                path = f"{prefix}.{key}" if prefix else key
                changes.extend(ControlCenterService._diff_values(before.get(key), after.get(key), path))
            return changes
        return [] if before == after else [{"key": prefix, "before": before, "after": after}]

    def config_diff(self, patch: dict[str, Any]) -> dict[str, Any]:
        current = self.current_config()
        validated = self.validate_config(patch)["values"]
        return {"from_version": current["version"], "changes": self._diff_values(current["values"], validated),
                "values": validated}

    def validate_config(self, patch: dict[str, Any]) -> dict[str, Any]:
        candidate = AppConfig()
        allowed = candidate.editable_snapshot()
        unknown = [key for key in patch if key not in allowed]
        if unknown:
            raise ValidationError(f"Unknown setting(s): {', '.join(sorted(unknown))}")
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(allowed.get(key), dict):
                bad = [field for field in value if field not in allowed[key]]
                if bad:
                    raise ValidationError(f"Unknown {key} field(s): {', '.join(sorted(bad))}")
                allowed[key].update(value)
            else:
                allowed[key] = value
        candidate._apply(allowed)
        return {"valid": True, "values": candidate.editable_snapshot()}

    @classmethod
    def validate_policies(cls, policies: dict[str, str]) -> dict[str, str]:
        registry_keys = {item["key"] for item in cls.registry()}
        unknown = [key for key in policies if key not in registry_keys]
        if unknown:
            raise ValidationError(f"Unknown policy setting(s): {', '.join(sorted(unknown))}")
        invalid = {key: value for key, value in policies.items() if value not in {"user_overridable", "locked"}}
        if invalid:
            raise ValidationError("Policies must be 'user_overridable' or 'locked'")
        return {key: policies.get(key, "user_overridable") for key in sorted(registry_keys)}

    def publish_config(self, patch: dict[str, Any], policies: dict[str, str], actor_id: str,
                       reason: str, expected_version: int | None = None) -> dict[str, Any]:
        current = self.current_config()
        if expected_version is not None and current["version"] != expected_version:
            raise ValidationError("Configuration changed since this draft was loaded; refresh and review the diff")
        validated = self.validate_config(patch)["values"]
        validated_policies = self.validate_policies(policies)
        previous = config.editable_snapshot()
        try:
            config._apply(validated)
            config._persist(validated)
            publication = self._store.publish_config(validated, validated_policies, actor_id, reason)
        except Exception:
            config._apply(previous)
            config._persist(previous)
            raise
        self._store.audit(actor_id, "config.published", "global_config", str(publication["version"]), reason, {"values": patch})
        return publication

    def rollback_config(self, version: int, actor_id: str, reason: str) -> dict[str, Any]:
        source = next((item for item in self._store.config_history() if item["version"] == version), None)
        if not source:
            raise NotFoundError("Configuration version not found")
        return self.publish_config(source["values"], source["policies"], actor_id, reason)

    def audit_event_page(self, action: str | None = None, target_type: str | None = None,
                         page: int = 1, page_size: int = 25) -> dict[str, Any]:
        return self._store.list_audit(action, target_type, page, page_size)

    def audit_events(self) -> list[dict[str, Any]]:
        """Backward-compatible service API for callers that need the recent event list."""
        return self.audit_event_page(page_size=200)["items"]