"""Freemium / Pro subscription domain models + SQLite store.

Phase 4 adds a churn-safe free tier and a Pro subscription. Entitlements are
computed server-side from a persisted subscription record — the client never
decides what a user can see. A dedicated ``subscriptions`` table holds the
billing state; the users table carries a denormalized ``tier`` column so auth
lookups stay cheap.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Tier / plan / subscription models
# --------------------------------------------------------------------------- #


class Tier(str, Enum):
    FREE = "free"
    PRO = "pro"


class SubscriptionStatus(str, Enum):
    NONE = "none"
    TRIAL = "trial"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    EXPIRED = "expired"


class BillingPlan(BaseModel):
    """A purchasable Pro plan. Prices are INR-anchored (screener.in Premium
    / Tickertape Pro reference) with a USD equivalent for international users."""

    id: str
    name: str = "Pro"
    interval: str = "month"          # "month" | "year"
    price_inr: float
    price_usd: float
    currency: str = "INR"
    description: str = ""
    features: list[str] = Field(default_factory=list)
    highlighted: bool = False
    trial_days: int = 0

    @property
    def price(self) -> float:
        return self.price_inr


class Subscription(BaseModel):
    """The persisted billing state for one user."""

    user_id: str
    plan_id: str | None = None
    status: SubscriptionStatus = SubscriptionStatus.NONE
    started_at: datetime | None = None
    renews_at: datetime | None = None
    canceled_at: datetime | None = None
    payment_gateway: str | None = None
    last_payment_id: str | None = None
    updated_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        """True while the subscription grants Pro access right now."""
        if self.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL):
            if self.renews_at is None:
                return True
            return datetime.utcnow() < self.renews_at
        return False


class Entitlements(BaseModel):
    """What the current tier unlocks. Always derived server-side."""

    tier: Tier = Tier.FREE
    is_pro: bool = False
    plan_id: str | None = None
    status: SubscriptionStatus = SubscriptionStatus.NONE
    renews_at: datetime | None = None
    features: dict[str, bool] = Field(default_factory=dict)
    limits: dict[str, int] = Field(default_factory=dict)

    def allows(self, feature: str) -> bool:
        return bool(self.features.get(feature))


class CheckoutSession(BaseModel):
    """A payment-gateway-agnostic checkout result."""

    session_id: str
    plan_id: str
    status: str = "created"          # created | paid | failed | expired
    gateway: str
    amount_inr: float | None = None
    confirm_url: str | None = None   # sandbox gateway: direct confirm link
    expires_at: datetime | None = None


# --------------------------------------------------------------------------- #
# Saved screens + alert rules (Pro)
# --------------------------------------------------------------------------- #


class SavedScreen(BaseModel):
    """A persisted custom filter + optional email alert rule."""

    screen_id: str
    user_id: str
    name: str
    filter_expr: str = ""            # the `where` expression from /api/scan
    sort_by: str = "score"
    sort_dir: str = "desc"
    limit: int = 50
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    alert_enabled: bool = False
    alert_email: str | None = None
    last_alert_at: datetime | None = None
    last_match_count: int = 0


class AlertEvaluation(BaseModel):
    """Result of running a saved screen against the live universe."""

    screen: SavedScreen
    matched: list[dict[str, Any]] = Field(default_factory=list)
    new_matches: int = 0
    email_sent: bool = False
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)


# --------------------------------------------------------------------------- #
# SQLite subscription store
# --------------------------------------------------------------------------- #


class SubscriptionStore:
    """SQLite persistence for subscriptions and saved screens."""

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            db_path = Path(__file__).resolve().parent.parent.parent / "data" / "users.db"
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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    user_id TEXT PRIMARY KEY,
                    plan_id TEXT,
                    status TEXT NOT NULL DEFAULT 'none',
                    started_at TEXT,
                    renews_at TEXT,
                    canceled_at TEXT,
                    payment_gateway TEXT,
                    last_payment_id TEXT,
                    updated_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS saved_screens (
                    screen_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    filter_expr TEXT DEFAULT '',
                    sort_by TEXT DEFAULT 'score',
                    sort_dir TEXT DEFAULT 'desc',
                    "limit" INTEGER DEFAULT 50,
                    created_at TEXT,
                    updated_at TEXT,
                    alert_enabled INTEGER DEFAULT 0,
                    alert_email TEXT,
                    last_alert_at TEXT,
                    last_match_count INTEGER DEFAULT 0
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_screens_user ON saved_screens(user_id, created_at)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS checkout_sessions ("
                " session_id TEXT PRIMARY KEY,"
                " user_id TEXT NOT NULL,"
                " plan_id TEXT NOT NULL,"
                " status TEXT NOT NULL,"
                " gateway TEXT,"
                " amount_inr REAL,"
                " created_at TEXT,"
                " paid_at TEXT"
                ")"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_checkout_user ON checkout_sessions(user_id, created_at)"
            )

    # ------------------------------------------------------------- subscription

    def get_subscription(self, user_id: str) -> Subscription | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM subscriptions WHERE user_id = ?", (user_id,)
            ).fetchone()
        return self._row_to_subscription(row) if row else None

    def upsert_subscription(self, sub: Subscription) -> Subscription:
        with self._connection() as conn:
            conn.execute(
                """INSERT INTO subscriptions
                   (user_id, plan_id, status, started_at, renews_at, canceled_at,
                    payment_gateway, last_payment_id, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                     plan_id=excluded.plan_id,
                     status=excluded.status,
                     started_at=excluded.started_at,
                     renews_at=excluded.renews_at,
                     canceled_at=excluded.canceled_at,
                     payment_gateway=excluded.payment_gateway,
                     last_payment_id=excluded.last_payment_id,
                     updated_at=excluded.updated_at""",
                (
                    sub.user_id,
                    sub.plan_id,
                    sub.status.value,
                    sub.started_at.isoformat() if sub.started_at else None,
                    sub.renews_at.isoformat() if sub.renews_at else None,
                    sub.canceled_at.isoformat() if sub.canceled_at else None,
                    sub.payment_gateway,
                    sub.last_payment_id,
                    datetime.utcnow().isoformat(),
                ),
            )
        return self.get_subscription(sub.user_id) or sub

    # ------------------------------------------------------------- saved screens

    def save_screen(self, screen: SavedScreen) -> SavedScreen:
        with self._connection() as conn:
            conn.execute(
                """INSERT INTO saved_screens
                   (screen_id, user_id, name, filter_expr, sort_by, sort_dir,
                    "limit", created_at, updated_at, alert_enabled, alert_email,
                    last_alert_at, last_match_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(screen_id) DO UPDATE SET
                     name=excluded.name,
                     filter_expr=excluded.filter_expr,
                     sort_by=excluded.sort_by,
                     sort_dir=excluded.sort_dir,
                     "limit"=excluded."limit",
                     updated_at=excluded.updated_at,
                     alert_enabled=excluded.alert_enabled,
                     alert_email=excluded.alert_email,
                     last_alert_at=excluded.last_alert_at,
                     last_match_count=excluded.last_match_count""",
                (
                    screen.screen_id,
                    screen.user_id,
                    screen.name,
                    screen.filter_expr,
                    screen.sort_by,
                    screen.sort_dir,
                    screen.limit,
                    screen.created_at.isoformat(),
                    screen.updated_at.isoformat(),
                    1 if screen.alert_enabled else 0,
                    screen.alert_email,
                    screen.last_alert_at.isoformat() if screen.last_alert_at else None,
                    screen.last_match_count,
                ),
            )
        return self.get_screen(screen.screen_id) or screen

    def get_screen(self, screen_id: str) -> SavedScreen | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM saved_screens WHERE screen_id = ?", (screen_id,)
            ).fetchone()
        return self._row_to_screen(row) if row else None

    def list_screens(self, user_id: str) -> list[SavedScreen]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM saved_screens WHERE user_id = ? ORDER BY created_at",
                (user_id,),
            ).fetchall()
        return [self._row_to_screen(r) for r in rows]

    def count_screens(self, user_id: str) -> int:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM saved_screens WHERE user_id = ?", (user_id,)
            ).fetchone()
        return int(row["n"]) if row else 0

    def delete_screen(self, screen_id: str, user_id: str) -> bool:
        with self._connection() as conn:
            cur = conn.execute(
                "DELETE FROM saved_screens WHERE screen_id = ? AND user_id = ?",
                (screen_id, user_id),
            )
            return cur.rowcount > 0

    def touch_screen_alert(self, screen_id: str, match_count: int, email_sent: bool) -> None:
        with self._connection() as conn:
            conn.execute(
                "UPDATE saved_screens SET last_alert_at = ?, last_match_count = ?, "
                "updated_at = ? WHERE screen_id = ?",
                (
                    datetime.utcnow().isoformat(),
                    match_count,
                    datetime.utcnow().isoformat(),
                    screen_id,
                ),
            )

    # ------------------------------------------------------------- checkouts

    def create_checkout(self, session_id: str, user_id: str, plan_id: str,
                        gateway: str, amount_inr: float | None) -> None:
        with self._connection() as conn:
            conn.execute(
                "INSERT INTO checkout_sessions "
                "(session_id, user_id, plan_id, status, gateway, amount_inr, created_at) "
                "VALUES (?, ?, ?, 'created', ?, ?, ?)",
                (
                    session_id, user_id, plan_id, gateway, amount_inr,
                    datetime.utcnow().isoformat(),
                ),
            )

    def get_checkout(self, session_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM checkout_sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        return dict(row) if row else None

    def mark_checkout_paid(self, session_id: str, paid_at: str | None = None) -> bool:
        with self._connection() as conn:
            cur = conn.execute(
                "UPDATE checkout_sessions SET status = 'paid', paid_at = ? "
                "WHERE session_id = ? AND status = 'created'",
                (paid_at or datetime.utcnow().isoformat(), session_id),
            )
            return cur.rowcount > 0

    # ------------------------------------------------------------- row helpers

    @staticmethod
    def _row_to_subscription(row: sqlite3.Row) -> Subscription:
        def _dt(value: str | None) -> datetime | None:
            try:
                return datetime.fromisoformat(value) if value else None
            except Exception:
                return None

        return Subscription(
            user_id=row["user_id"],
            plan_id=row["plan_id"],
            status=SubscriptionStatus(row["status"] or "none"),
            started_at=_dt(row["started_at"]),
            renews_at=_dt(row["renews_at"]),
            canceled_at=_dt(row["canceled_at"]),
            payment_gateway=row["payment_gateway"],
            last_payment_id=row["last_payment_id"],
            updated_at=_dt(row["updated_at"]),
        )

    @staticmethod
    def _row_to_screen(row: sqlite3.Row) -> SavedScreen:
        def _dt(value: str | None) -> datetime | None:
            try:
                return datetime.fromisoformat(value) if value else None
            except Exception:
                return None

        return SavedScreen(
            screen_id=row["screen_id"],
            user_id=row["user_id"],
            name=row["name"],
            filter_expr=row["filter_expr"] or "",
            sort_by=row["sort_by"] or "score",
            sort_dir=row["sort_dir"] or "desc",
            limit=int(row["limit"] or 50),
            created_at=_dt(row["created_at"]) or datetime.utcnow(),
            updated_at=_dt(row["updated_at"]) or datetime.utcnow(),
            alert_enabled=bool(row["alert_enabled"]),
            alert_email=row["alert_email"],
            last_alert_at=_dt(row["last_alert_at"]),
            last_match_count=int(row["last_match_count"] or 0),
        )


# Global store instance
subscription_store = SubscriptionStore()
