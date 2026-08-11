"""SQLite persistence for product analytics events + derived metrics.

Kept deliberately light: a single event table, with metrics (DAU/WAU, funnel
counts, retention) computed at query time. There are no pre-aggregated counter
tables to keep in sync — the event log is the source of truth and every
metric is a small SQL aggregate over it. MRR is not derived here; it reads
the billing store (paid checkout sessions) because revenue is a billing fact,
not a product event.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from screener.core.analytics_models import (
    AnalyticsEvent,
    AnalyticsOverview,
    FunnelStep,
    RetentionPoint,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


class AnalyticsStore:
    """Persist and query product events from SQLite."""

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            db_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "analytics.db"
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
                CREATE TABLE IF NOT EXISTS analytics_events (
                    event_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    event_name TEXT NOT NULL,
                    properties TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_analytics_user_created "
                "ON analytics_events(user_id, created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_analytics_name_created "
                "ON analytics_events(event_name, created_at)"
            )

    # ------------------------------------------------------------------ track

    def track(self, event: AnalyticsEvent) -> AnalyticsEvent:
        with self._connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO analytics_events "
                "(event_id, user_id, event_name, properties, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    event.event_id,
                    event.user_id,
                    event.event_name,
                    __import__("json").dumps(event.properties, ensure_ascii=False),
                    _iso(event.created_at),
                ),
            )
        return event

    def list_events(
        self,
        event_name: str | None = None,
        since: datetime | None = None,
        limit: int = 500,
    ) -> list[AnalyticsEvent]:
        query = "SELECT * FROM analytics_events"
        clauses: list[str] = []
        params: list[object] = []
        if event_name:
            clauses.append("event_name = ?")
            params.append(event_name)
        if since:
            clauses.append("created_at >= ?")
            params.append(_iso(since))
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_event(row) for row in rows]

    # ---------------------------------------------------------------- metrics

    def count_events(self, event_name: str, since: datetime | None = None) -> int:
        query = "SELECT COUNT(*) AS n FROM analytics_events WHERE event_name = ?"
        params: list[object] = [event_name]
        if since:
            query += " AND created_at >= ?"
            params.append(_iso(since))
        with self._connection() as conn:
            row = conn.execute(query, params).fetchone()
        return int(row["n"]) if row else 0

    def distinct_users(self, event_name: str | None = None,
                       since: datetime | None = None) -> int:
        query = "SELECT COUNT(DISTINCT user_id) AS n FROM analytics_events"
        clauses: list[str] = []
        params: list[object] = []
        if event_name:
            clauses.append("event_name = ?")
            params.append(event_name)
        if since:
            clauses.append("created_at >= ?")
            params.append(_iso(since))
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        with self._connection() as conn:
            row = conn.execute(query, params).fetchone()
        return int(row["n"]) if row else 0

    def daily_active_users(self, day: datetime | None = None) -> int:
        """Distinct users with any event on the UTC day of ``day``."""
        day = day or _utcnow()
        start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return self._users_in_range(start, end)

    def _users_in_range(self, start: datetime, end: datetime) -> int:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT COUNT(DISTINCT user_id) AS n FROM analytics_events "
                "WHERE created_at >= ? AND created_at < ?",
                (_iso(start), _iso(end)),
            ).fetchone()
        return int(row["n"]) if row else 0

    def weekly_active_users(self, end: datetime | None = None) -> int:
        """Distinct users active in the trailing 7 days ending ``end``."""
        end = end or _utcnow()
        start = end - timedelta(days=7)
        with self._connection() as conn:
            row = conn.execute(
                "SELECT COUNT(DISTINCT user_id) AS n FROM analytics_events "
                "WHERE created_at >= ? AND created_at <= ?",
                (_iso(start), _iso(end)),
            ).fetchone()
        return int(row["n"]) if row else 0

    def funnel(self, steps: list[str], since: datetime | None = None) -> list[FunnelStep]:
        """Distinct users who reached each funnel step, in order."""
        result: list[FunnelStep] = []
        for step in steps:
            query = "SELECT COUNT(DISTINCT user_id) AS n FROM analytics_events WHERE event_name = ?"
            params: list[object] = [step]
            if since:
                query += " AND created_at >= ?"
                params.append(_iso(since))
            with self._connection() as conn:
                row = conn.execute(query, params).fetchone()
            result.append(FunnelStep(step=step, users=int(row["n"]) if row else 0))
        return result

    def conversion(self, from_event: str, to_event: str,
                   since: datetime | None = None) -> float:
        """Share of ``from_event`` users who later recorded ``to_event``."""
        base = self.distinct_users(from_event, since)
        if base == 0:
            return 0.0
        with self._connection() as conn:
            row = conn.execute(
                "SELECT COUNT(DISTINCT a.user_id) AS n "
                "FROM analytics_events a "
                "JOIN analytics_events b ON a.user_id = b.user_id "
                "WHERE a.event_name = ? AND b.event_name = ? "
                "AND a.created_at <= b.created_at",
                (from_event, to_event),
            ).fetchone()
        converted = int(row["n"]) if row else 0
        return round(converted / base, 4)

    def retention(self, cohort_window_days: int = 1, lookback_days: int = 30,
                  return_window_days: int = 90,
                  now: datetime | None = None) -> RetentionPoint:
        """Share of users active in a recent cohort who returned later.

        Cohort = users active between ``now-lookback_days-cohort_window`` and
        ``now-lookback_days``; return window is the following
        ``return_window_days``. Used for the 90-day retention KPI.
        """
        now = now or _utcnow()
        cohort_end = now - timedelta(days=lookback_days)
        cohort_start = cohort_end - timedelta(days=cohort_window_days)
        return_end = min(now, cohort_end + timedelta(days=return_window_days))

        with self._connection() as conn:
            cohort = conn.execute(
                "SELECT DISTINCT user_id FROM analytics_events "
                "WHERE created_at >= ? AND created_at < ?",
                (_iso(cohort_start), _iso(cohort_end)),
            ).fetchall()
        cohort_ids = {r["user_id"] for r in cohort}
        if not cohort_ids:
            return RetentionPoint(
                window_start=cohort_start, window_end=cohort_end,
                cohort_users=0, returned_users=0, retention_rate=0.0,
            )
        returned = 0
        with self._connection() as conn:
            for user_id in cohort_ids:
                row = conn.execute(
                    "SELECT 1 FROM analytics_events "
                    "WHERE user_id = ? AND created_at >= ? AND created_at <= ? "
                    "LIMIT 1",
                    (user_id, _iso(cohort_end), _iso(return_end)),
                ).fetchone()
                if row:
                    returned += 1
        return RetentionPoint(
            window_start=cohort_start,
            window_end=cohort_end,
            cohort_users=len(cohort_ids),
            returned_users=returned,
            retention_rate=round(returned / len(cohort_ids), 4),
        )

    def overview(
        self,
        funnel_steps: list[str],
        billing_provider=None,
        now: datetime | None = None,
    ) -> AnalyticsOverview:
        """Assemble the product-owner analytics snapshot.

        ``billing_provider`` is an optional object exposing ``paid_mrr()`` and
        ``trial_to_paid_conversion()`` and ``push_opt_in_rate()`` (the
        SubscriptionService-backed metrics); when absent those return zeros so
        the overview stays computable offline.
        """
        now = now or _utcnow()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_users = self._users_in_range(day_start, day_start + timedelta(days=1))
        week_users = self.weekly_active_users(end=now)
        total_users = self.distinct_users()
        funnel = self.funnel(funnel_steps, since=now - timedelta(days=30))

        mrr = 0.0
        trial_to_paid = 0.0
        push_rate = 0.0
        if billing_provider is not None:
            try:
                mrr = float(billing_provider.paid_mrr() or 0.0)
            except Exception:
                mrr = 0.0
            try:
                trial_to_paid = float(billing_provider.trial_to_paid_conversion() or 0.0)
            except Exception:
                trial_to_paid = 0.0
            try:
                push_rate = float(billing_provider.push_opt_in_rate() or 0.0)
            except Exception:
                push_rate = 0.0

        return AnalyticsOverview(
            generated_at=now,
            dau=day_users,
            wau=week_users,
            total_users=total_users,
            funnel=funnel,
            free_to_pro_conversion=self.conversion(
                "checkout_created", "checkout_paid", since=now - timedelta(days=90)
            ),
            trial_to_paid_conversion=trial_to_paid,
            retention_90d=self.retention(
                cohort_window_days=1, lookback_days=30, return_window_days=90, now=now
            ).retention_rate,
            mrr_inr=mrr,
            push_opt_in_rate=push_rate,
        )

    # -------------------------------------------------------------- row helper

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> AnalyticsEvent:
        return AnalyticsEvent(
            event_id=row["event_id"],
            user_id=row["user_id"],
            event_name=row["event_name"],
            properties=__import__("json").loads(row["properties"] or "{}"),
            created_at=datetime.fromisoformat(row["created_at"]),
        )


# Global store instance
analytics_store = AnalyticsStore()
