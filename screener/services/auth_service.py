"""Authentication Service — register, login, logout, token validation."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from screener.core.responses import AuthError, ErrorCodes, ValidationError
from screener.core.user_models import (
    AuthToken,
    UserCreate,
    UserLogin,
    UserProfile,
    UserRecord,
    UserStore,
    create_token,
    hash_password,
    user_store,
    validate_token,
    verify_password,
)


class AuthService:
    """Handles user registration, login, and token management."""

    def __init__(self, store: UserStore | None = None):
        self._store = store or user_store

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #

    def register(self, body: UserCreate) -> AuthToken:
        """Create a new user account.

        Raises ValidationError on bad input, AuthError(USER_EXISTS) on duplicate.
        """
        email = str(body.email).strip().lower()
        username = (body.username or email.split("@", 1)[0]).strip().lower()
        if not username:
            raise ValidationError("Username cannot be empty")

        # Check for existing user
        existing = self._store.get_by_email(email) or self._store.get_by_username(username)
        if existing is not None:
            raise AuthError(ErrorCodes.USER_EXISTS, f"Username '{username}' is already taken")

        # Hash password
        pw_hash, pw_salt = hash_password(body.password)

        # Build record
        user_id = str(uuid.uuid4())
        record = UserRecord(
            user_id=user_id,
            username=username,
            email=str(body.email).strip(),
            normalized_email=email,
            display_name=body.display_name or username,
            password_hash=pw_hash,
            password_salt=pw_salt,
            preferences={},
        )

        created = self._store.create_user(record)
        if created is None:
            raise AuthError(ErrorCodes.USER_EXISTS, f"Username '{username}' is already taken")

        self.send_verification(created)
        return self._make_token(created)

    # ------------------------------------------------------------------ #
    # Login
    # ------------------------------------------------------------------ #

    def login(self, body: UserLogin) -> AuthToken:
        """Authenticate a user. Returns a token.

        Raises AuthError on invalid credentials.
        """
        identifier = (body.email or body.username or "").strip().lower()
        user = self._store.get_by_email(identifier) or self._store.get_by_username(identifier)
        if user is None:
            raise AuthError(ErrorCodes.AUTH_INVALID, "Invalid email or password")

        if not verify_password(body.password, user.password_hash, user.password_salt):
            raise AuthError(ErrorCodes.AUTH_INVALID, "Invalid email or password")

        if user.status != "active":
            raise AuthError(ErrorCodes.AUTH_INVALID, "Invalid email or password")

        user = self._store.update_account(user.user_id, last_login_at=datetime.utcnow()) or user

        return self._make_token(user)

    def send_verification(self, user: UserRecord) -> None:
        if not user.email or user.email_verified_at:
            return
        token = self._store.create_auth_token(user.user_id, "verify_email", 24 * 60)
        self._capture_email(user.email, "verify_email", token)

    def resend_verification(self, user_id: str) -> dict[str, str]:
        user = self._store.get_by_id(user_id)
        if user:
            self.send_verification(user)
        return {"message": "If verification is required, a new link has been sent."}

    def verify_email(self, token: str) -> UserProfile:
        user = self._store.consume_auth_token(token, "verify_email")
        if not user:
            raise AuthError(ErrorCodes.AUTH_INVALID, "Verification link is invalid or expired")
        updated = self._store.update_account(user.user_id, email_verified_at=datetime.utcnow()) or user
        return self._profile(updated)

    def request_password_reset(self, email: str) -> dict[str, str]:
        user = self._store.get_by_email(email.strip().lower())
        if user and user.email and user.status == "active":
            token = self._store.create_auth_token(user.user_id, "reset_password", 30)
            self._capture_email(user.email, "reset_password", token)
        return {"message": "If an account exists, a password reset link has been sent."}

    def reset_password(self, token: str, password: str, confirmation: str) -> dict[str, str]:
        if password != confirmation:
            raise ValidationError("Passwords do not match")
        if len(password) < 8 or len(password) > 128:
            raise ValidationError("Password must be between 8 and 128 characters")
        user = self._store.consume_auth_token(token, "reset_password")
        if not user or user.status != "active":
            raise AuthError(ErrorCodes.AUTH_INVALID, "Password reset link is invalid or expired")
        password_hash, password_salt = hash_password(password)
        self._store.update_account(
            user.user_id,
            password_hash=password_hash,
            password_salt=password_salt,
            token_version=user.token_version + 1,
        )
        return {"message": "Password reset successfully. Sign in with your new password."}

    def logout_all(self, user_id: str) -> dict[str, str]:
        user = self._store.get_by_id(user_id)
        if user:
            self._store.update_account(user_id, token_version=user.token_version + 1)
        return {"message": "All sessions have been signed out."}

    @staticmethod
    def _capture_email(email: str, purpose: str, token: str) -> None:
        """Development delivery adapter; production can ship the JSONL to its provider."""
        path = Path(os.getenv("SCREENER_AUTH_EMAIL_OUTBOX", "data/auth_email_outbox.jsonl"))
        path.parent.mkdir(parents=True, exist_ok=True)
        base_url = os.getenv("SCREENER_PUBLIC_URL", "http://localhost:8000").rstrip("/")
        route = "verify-email" if purpose == "verify_email" else "reset-password"
        record = {
            "to": email,
            "purpose": purpose,
            "url": f"{base_url}/#/{'auth/' + route}?token={token}",
            "created_at": datetime.utcnow().isoformat(),
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

    # ------------------------------------------------------------------ #
    # Token validation
    # ------------------------------------------------------------------ #

    def get_user_from_token(self, token: str) -> UserProfile:
        """Validate a token and return the user profile.

        Raises AuthError on invalid/expired token.
        """
        payload = validate_token(token)
        if payload is None:
            raise AuthError(ErrorCodes.AUTH_EXPIRED, "Token is invalid or expired")

        user = self._store.get_by_id(payload["uid"])
        if user is None:
            raise AuthError(ErrorCodes.USER_NOT_FOUND, "User no longer exists")
        if user.status != "active" or int(payload.get("ver", 0)) != user.token_version:
            raise AuthError(ErrorCodes.AUTH_EXPIRED, "Token is invalid or expired")

        return self._profile(user)

    @staticmethod
    def _profile(user: UserRecord) -> UserProfile:
        return UserProfile(
            user_id=user.user_id,
            username=user.username,
            email=user.email,
            display_name=user.display_name,
            email_verified_at=user.email_verified_at,
            role=user.role,
            status=user.status,
            tier=user.tier,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
            preferences=user.preferences,
        )

    # ------------------------------------------------------------------ #
    # Guest mode (for backward compatibility)
    # ------------------------------------------------------------------ #

    def ensure_guest_user(self) -> UserProfile:
        """Create or return the built-in guest user for CLI / unauthenticated access."""
        existing = self._store.get_by_username("guest")
        if existing is not None:
            return UserProfile(
                user_id=existing.user_id,
                username=existing.username,
                email=existing.email,
                display_name=existing.display_name,
                role=existing.role,
                status=existing.status,
                created_at=existing.created_at,
                preferences=existing.preferences,
            )

        pw_hash, pw_salt = hash_password("guest")
        record = UserRecord(
            user_id="guest",
            username="guest",
            display_name="Guest",
            password_hash=pw_hash,
            password_salt=pw_salt,
            preferences={},
        )
        self._store.create_user(record)
        return UserProfile(
            user_id="guest",
            username="guest",
            display_name="Guest",
            created_at=record.created_at,
            preferences={},
        )

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    @staticmethod
    def _make_token(user: UserRecord) -> AuthToken:
        token = create_token(user.user_id, user.username, user.token_version)
        expires = datetime.utcnow() + timedelta(days=7)
        return AuthToken(
            token=token,
            user=AuthService._profile(user),
            expires_at=expires,
        )
