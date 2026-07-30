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

from pydantic import BaseModel, Field, field_validator, model_validator

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


def create_token(user_id: str, username: str, token_version: int = 0) -> str:
    """Create a signed token for a user. Returns a compact token string."""
    payload = json.dumps({
        "uid": user_id,
        "uname": username,
        "ver": token_version,
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
    email: str = Field(..., min_length=5, max_length=254)
    username: str | None = Field(None, min_length=2, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    password_confirmation: str | None = None
    display_name: str | None = None

    @model_validator(mode="after")
    def passwords_match(self):
        if self.email.count("@") != 1 or "." not in self.email.rsplit("@", 1)[-1]:
            raise ValueError("Enter a valid email address")
        if self.password_confirmation is not None and self.password != self.password_confirmation:
            raise ValueError("Passwords do not match")
        return self


class UserLogin(BaseModel):
    """Login payload."""
    email: str | None = None
    username: str | None = None
    password: str

    @model_validator(mode="after")
    def has_identifier(self):
        if not (self.email or self.username):
            raise ValueError("Email is required")
        return self


class UserProfile(BaseModel):
    """Public user profile (no secrets)."""
    user_id: str
    username: str
    email: str | None = None
    display_name: str | None = None
    email_verified_at: datetime | None = None
    role: str = "user"
    status: str = "active"
    created_at: datetime
    last_login_at: datetime | None = None
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
    email: str | None = None
    normalized_email: str | None = None
    display_name: str | None = None
    password_hash: str
    password_salt: str
    created_at: datetime = Field(default_factory=datetime.now)
    email_verified_at: datetime | None = None
    role: str = "user"
    status: str = "active"
    last_login_at: datetime | None = None
    token_version: int = 0
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
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
            additions = {
                "email": "TEXT",
                "normalized_email": "TEXT",
                "email_verified_at": "TEXT",
                "role": "TEXT NOT NULL DEFAULT 'user'",
                "status": "TEXT NOT NULL DEFAULT 'active'",
                "last_login_at": "TEXT",
                "token_version": "INTEGER NOT NULL DEFAULT 0",
            }
            for name, declaration in additions.items():
                if name not in columns:
                    conn.execute(f"ALTER TABLE users ADD COLUMN {name} {declaration}")
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_normalized_email "
                "ON users(normalized_email) WHERE normalized_email IS NOT NULL"
            )
            conn.execute("""
                CREATE TABLE IF NOT EXISTS auth_tokens (
                    token_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    token_hash TEXT UNIQUE NOT NULL,
                    expires_at TEXT NOT NULL,
                    used_at TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_auth_tokens_user_purpose "
                "ON auth_tokens(user_id, purpose, created_at DESC)"
            )
            conn.execute("PRAGMA user_version = 2")

    def create_user(self, record: UserRecord) -> UserRecord | None:
        """Insert a new user. Returns the record, or None if username exists."""
        try:
            with self._connection() as conn:
                conn.execute(
                    """INSERT INTO users
                       (user_id, username, email, normalized_email, display_name,
                        password_hash, password_salt, created_at, preferences,
                        email_verified_at, role, status, last_login_at, token_version)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record.user_id,
                        record.username,
                        record.email,
                        record.normalized_email,
                        record.display_name,
                        record.password_hash,
                        record.password_salt,
                        record.created_at.isoformat(),
                        json.dumps(record.preferences),
                        record.email_verified_at.isoformat() if record.email_verified_at else None,
                        record.role,
                        record.status,
                        record.last_login_at.isoformat() if record.last_login_at else None,
                        record.token_version,
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

    def get_by_email(self, email: str) -> UserRecord | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE normalized_email = ?", (email.strip().lower(),)
            ).fetchone()
        return self._row_to_record(row) if row else None

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

    def update_account(self, user_id: str, **changes: Any) -> UserRecord | None:
        allowed = {"email", "normalized_email", "email_verified_at", "role", "status", "last_login_at", "token_version", "password_hash", "password_salt"}
        values = {key: value for key, value in changes.items() if key in allowed}
        if not values:
            return self.get_by_id(user_id)
        for key in ("email_verified_at", "last_login_at"):
            if isinstance(values.get(key), datetime):
                values[key] = values[key].isoformat()
        assignments = ", ".join(f"{key} = ?" for key in values)
        with self._connection() as conn:
            conn.execute(
                f"UPDATE users SET {assignments} WHERE user_id = ?",
                (*values.values(), user_id),
            )
        return self.get_by_id(user_id)

    def create_auth_token(self, user_id: str, purpose: str, ttl_minutes: int) -> str:
        """Persist only a digest and return the one-time plaintext token."""
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        now = datetime.utcnow()
        with self._connection() as conn:
            conn.execute(
                "UPDATE auth_tokens SET used_at = ? WHERE user_id = ? AND purpose = ? AND used_at IS NULL",
                (now.isoformat(), user_id, purpose),
            )
            conn.execute(
                "INSERT INTO auth_tokens VALUES (?, ?, ?, ?, ?, NULL, ?)",
                (
                    secrets.token_hex(16),
                    user_id,
                    purpose,
                    token_hash,
                    (now + timedelta(minutes=ttl_minutes)).isoformat(),
                    now.isoformat(),
                ),
            )
        return token

    def consume_auth_token(self, token: str, purpose: str) -> UserRecord | None:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        now = datetime.utcnow()
        with self._connection() as conn:
            row = conn.execute(
                "SELECT token_id, user_id, expires_at, used_at FROM auth_tokens "
                "WHERE token_hash = ? AND purpose = ?",
                (token_hash, purpose),
            ).fetchone()
            if not row or row["used_at"] or datetime.fromisoformat(row["expires_at"]) <= now:
                return None
            updated = conn.execute(
                "UPDATE auth_tokens SET used_at = ? WHERE token_id = ? AND used_at IS NULL",
                (now.isoformat(), row["token_id"]),
            )
            if updated.rowcount != 1:
                return None
            user_id = row["user_id"]
        return self.get_by_id(user_id)

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
            email=row["email"] if "email" in row.keys() else None,
            normalized_email=row["normalized_email"] if "normalized_email" in row.keys() else None,
            display_name=row["display_name"],
            password_hash=row["password_hash"],
            password_salt=row["password_salt"],
            created_at=datetime.fromisoformat(row["created_at"]),
            email_verified_at=datetime.fromisoformat(row["email_verified_at"]) if "email_verified_at" in row.keys() and row["email_verified_at"] else None,
            role=row["role"] if "role" in row.keys() else "user",
            status=row["status"] if "status" in row.keys() else "active",
            last_login_at=datetime.fromisoformat(row["last_login_at"]) if "last_login_at" in row.keys() and row["last_login_at"] else None,
            token_version=int(row["token_version"]) if "token_version" in row.keys() else 0,
            preferences=json.loads(row["preferences"]) if row["preferences"] else {},
        )


# Global user store instance
user_store = UserStore()
