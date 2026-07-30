"""SQLite persistence for tester feedback."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from screener.core.feedback_models import FeedbackRecord


class FeedbackStore:
    """Persist and retrieve feedback records from SQLite."""

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            db_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "feedback.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = str(db_path)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    @contextmanager
    def _connection(self):
        conn = self._get_conn()
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    feedback_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    document TEXT NOT NULL,
                    plain_text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_feedback_user_created "
                "ON feedback(user_id, created_at DESC)"
            )
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(feedback)")}
            additions = {
                "status": "TEXT NOT NULL DEFAULT 'new'",
                "priority": "TEXT NOT NULL DEFAULT 'medium'",
                "assignee_id": "TEXT",
                "updated_at": "TEXT",
                "resolved_at": "TEXT",
            }
            for name, declaration in additions.items():
                if name not in columns:
                    conn.execute(f"ALTER TABLE feedback ADD COLUMN {name} {declaration}")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback_events (
                    event_id TEXT PRIMARY KEY,
                    feedback_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    changes TEXT NOT NULL,
                    note TEXT,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            for column in ("created_at", "status", "priority", "assignee_id", "category", "user_id"):
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_feedback_{column} ON feedback({column})")
            conn.execute("PRAGMA user_version = 1")

    def create(self, record: FeedbackRecord) -> FeedbackRecord:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO feedback
                    (feedback_id, user_id, username, category, title, document, plain_text,
                     status, priority, assignee_id, created_at, updated_at, resolved_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.feedback_id,
                    record.user_id,
                    record.username,
                    record.category,
                    record.title,
                    json.dumps(record.document, ensure_ascii=False),
                    record.plain_text,
                    record.status,
                    record.priority,
                    record.assignee_id,
                    record.created_at.isoformat(),
                    record.updated_at.isoformat() if record.updated_at else None,
                    record.resolved_at.isoformat() if record.resolved_at else None,
                ),
            )
        return record

    def list_by_user(self, user_id: str) -> list[FeedbackRecord]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM feedback WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def list_all(self) -> list[FeedbackRecord]:
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM feedback ORDER BY created_at DESC").fetchall()
        return [self._row_to_record(row) for row in rows]

    def get(self, feedback_id: str) -> FeedbackRecord | None:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM feedback WHERE feedback_id = ?", (feedback_id,)).fetchone()
        return self._row_to_record(row) if row else None

    def update_workflow(self, feedback_id: str, changes: dict, event: dict) -> FeedbackRecord | None:
        with self._connection() as conn:
            if changes:
                assignments = ", ".join(f"{key} = ?" for key in changes)
                conn.execute(
                    f"UPDATE feedback SET {assignments} WHERE feedback_id = ?",
                    (*changes.values(), feedback_id),
                )
            conn.execute(
                """INSERT INTO feedback_events
                   (event_id, feedback_id, actor_id, event_type, changes, note, reason, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event["event_id"], feedback_id, event["actor_id"], event["event_type"],
                    json.dumps(event["changes"]), event.get("note"), event["reason"], event["created_at"],
                ),
            )
        return self.get(feedback_id)

    def list_events(self, feedback_id: str) -> list[dict]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM feedback_events WHERE feedback_id = ? ORDER BY created_at DESC",
                (feedback_id,),
            ).fetchall()
        return [{**dict(row), "changes": json.loads(row["changes"])} for row in rows]

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> FeedbackRecord:
        return FeedbackRecord(
            feedback_id=row["feedback_id"],
            user_id=row["user_id"],
            username=row["username"],
            category=row["category"],
            title=row["title"],
            document=json.loads(row["document"]),
            plain_text=row["plain_text"],
            status=row["status"] if "status" in row.keys() else "new",
            priority=row["priority"] if "priority" in row.keys() else "medium",
            assignee_id=row["assignee_id"] if "assignee_id" in row.keys() else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]) if "updated_at" in row.keys() and row["updated_at"] else None,
            resolved_at=datetime.fromisoformat(row["resolved_at"]) if "resolved_at" in row.keys() and row["resolved_at"] else None,
        )
