"""Authentication Service — register, login, logout, token validation."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

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
        username = body.username.strip().lower()
        if not username:
            raise ValidationError("Username cannot be empty")

        # Check for existing user
        existing = self._store.get_by_username(username)
        if existing is not None:
            raise AuthError(ErrorCodes.USER_EXISTS, f"Username '{username}' is already taken")

        # Hash password
        pw_hash, pw_salt = hash_password(body.password)

        # Build record
        user_id = str(uuid.uuid4())
        record = UserRecord(
            user_id=user_id,
            username=username,
            display_name=body.display_name or username,
            password_hash=pw_hash,
            password_salt=pw_salt,
            preferences={},
        )

        created = self._store.create_user(record)
        if created is None:
            raise AuthError(ErrorCodes.USER_EXISTS, f"Username '{username}' is already taken")

        return self._make_token(created)

    # ------------------------------------------------------------------ #
    # Login
    # ------------------------------------------------------------------ #

    def login(self, body: UserLogin) -> AuthToken:
        """Authenticate a user. Returns a token.

        Raises AuthError on invalid credentials.
        """
        username = body.username.strip().lower()
        user = self._store.get_by_username(username)
        if user is None:
            raise AuthError(ErrorCodes.AUTH_INVALID, "Invalid username or password")

        if not verify_password(body.password, user.password_hash, user.password_salt):
            raise AuthError(ErrorCodes.AUTH_INVALID, "Invalid username or password")

        return self._make_token(user)

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

        return UserProfile(
            user_id=user.user_id,
            username=user.username,
            display_name=user.display_name,
            created_at=user.created_at,
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
                display_name=existing.display_name,
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
        token = create_token(user.user_id, user.username)
        expires = datetime.utcnow() + timedelta(days=7)
        return AuthToken(
            token=token,
            user=UserProfile(
                user_id=user.user_id,
                username=user.username,
                display_name=user.display_name,
                created_at=user.created_at,
                preferences=user.preferences,
            ),
            expires_at=expires,
        )
