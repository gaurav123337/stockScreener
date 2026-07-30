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

    def create(self, record: FeedbackRecord) -> FeedbackRecord:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO feedback
                    (feedback_id, user_id, username, category, title, document, plain_text, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.feedback_id,
                    record.user_id,
                    record.username,
                    record.category,
                    record.title,
                    json.dumps(record.document, ensure_ascii=False),
                    record.plain_text,
                    record.created_at.isoformat(),
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
            created_at=datetime.fromisoformat(row["created_at"]),
        )
