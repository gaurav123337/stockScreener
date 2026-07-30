"""User & Auth domain models — Pydantic for validation and serialization."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import string
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Token management (self-contained, no external JWT library needed)
# --------------------------------------------------------------------------- #

_ALPHABET = string.ascii_letters + string.digits
_TOKEN_EXPIRY_DAYS = 7


def _get_secret() -> bytes:
    """Get or create the server secret key for token signing."""
    secret_file = Path(__file__).resolve().parent.parent.parent / "data" / ".secret_key"
    if secret_file.exists():
        return secret_file.read_bytes()
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_bytes(32)
    secret_file.write_bytes(key)
    return key


_SECRET = _get_secret()


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Hash a password with PBKDF2-HMAC-SHA256. Returns (hash_hex, salt_hex)."""
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000)
    return dk.hex(), salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """Check a password against its hash."""
    computed, _ = hash_password(password, salt)
    return hmac.compare_digest(computed, password_hash)


def create_token(user_id: str, username: str) -> str:
    """Create a signed token for a user. Returns a compact token string."""
    payload = json.dumps({
        "uid": user_id,
        "uname": username,
        "exp": (datetime.utcnow() + timedelta(days=_TOKEN_EXPIRY_DAYS)).isoformat(),
        "iat": datetime.utcnow().isoformat(),
    })
    sig = hmac.new(_SECRET, payload.encode(), hashlib.sha256).hexdigest()
    # Compact: base64-like encoding
    raw = payload.encode() + b"." + sig.encode()
    return raw.hex()


def validate_token(token: str) -> dict[str, Any] | None:
    """Validate a token and return the payload, or None if invalid/expired."""
    try:
        raw = bytes.fromhex(token)
        # Split on last dot (sig separator)
        last_dot = raw.rfind(b".")
        if last_dot == -1:
            return None
        payload_bytes = raw[:last_dot]
        sig_hex = raw[last_dot + 1:].decode()
        expected_sig = hmac.new(_SECRET, payload_bytes, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig_hex, expected_sig):
            return None
        payload = json.loads(payload_bytes.decode())
        # Check expiry
        exp = datetime.fromisoformat(payload["exp"])
        if datetime.utcnow() > exp:
            return None
        return payload
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Pydantic models
# --------------------------------------------------------------------------- #

class UserCreate(BaseModel):
    """Registration payload."""
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=4, max_length=128)
    display_name: str | None = None


class UserLogin(BaseModel):
    """Login payload."""
    username: str
    password: str


class UserProfile(BaseModel):
    """Public user profile (no secrets)."""
    user_id: str
    username: str
    display_name: str | None = None
    created_at: datetime
    preferences: dict[str, Any] = Field(default_factory=dict)


class AuthToken(BaseModel):
    """Token response."""
    token: str
    user: UserProfile
    expires_at: datetime


class UserRecord(BaseModel):
    """Internal user record (stored in DB)."""
    user_id: str
    username: str
    display_name: str | None = None
    password_hash: str
    password_salt: str
    created_at: datetime = Field(default_factory=datetime.now)
    preferences: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# SQLite-backed user store
# --------------------------------------------------------------------------- #

class UserStore:
    """SQLite-backed persistence for users."""

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
        """Yield a connection and always close it, including on Windows."""
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
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    display_name TEXT,
                    password_hash TEXT NOT NULL,
                    password_salt TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    preferences TEXT DEFAULT '{}'
                )
            """)

    def create_user(self, record: UserRecord) -> UserRecord | None:
        """Insert a new user. Returns the record, or None if username exists."""
        try:
            with self._connection() as conn:
                conn.execute(
                    """INSERT INTO users
                       (user_id, username, display_name, password_hash, password_salt, created_at, preferences)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record.user_id,
                        record.username,
                        record.display_name,
                        record.password_hash,
                        record.password_salt,
                        record.created_at.isoformat(),
                        json.dumps(record.preferences),
                    ),
                )
            return record
        except sqlite3.IntegrityError:
            return None

    def get_by_username(self, username: str) -> UserRecord | None:
        """Look up a user by username."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def get_by_id(self, user_id: str) -> UserRecord | None:
        """Look up a user by ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def update_preferences(self, user_id: str, prefs: dict[str, Any]) -> bool:
        """Update a user's preferences."""
        with self._connection() as conn:
            conn.execute(
                "UPDATE users SET preferences = ? WHERE user_id = ?",
                (json.dumps(prefs), user_id),
            )
        return True

    def get_preferences(self, user_id: str) -> dict[str, Any]:
        """Get a user's preferences."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT preferences FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
        if row is None:
            return {}
        try:
            return json.loads(row["preferences"])
        except Exception:
            return {}

    def list_users(self) -> list[UserRecord]:
        """List all users (admin use)."""
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()
        return [self._row_to_record(r) for r in rows]

    def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        with self._connection() as conn:
            conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        return True

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> UserRecord:
        return UserRecord(
            user_id=row["user_id"],
            username=row["username"],
            display_name=row["display_name"],
            password_hash=row["password_hash"],
            password_salt=row["password_salt"],
            created_at=datetime.fromisoformat(row["created_at"]),
            preferences=json.loads(row["preferences"]) if row["preferences"] else {},
        )


# Global user store instance
user_store = UserStore()
