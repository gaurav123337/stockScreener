"""Offline tests for token signing / validation robustness.

Covers:
- ``_get_secret`` honours ``SCREENER_TOKEN_SECRET`` (stable across restarts)
- ``validate_token`` accepts both the current and the legacy dot-separated
  token formats (so already-deployed clients keep working after an upgrade)
- invalid signatures / expired tokens are rejected
- ``bootstrap_product_owner`` recreates the configured account with a stable
  ``SCREENER_PRODUCT_OWNER_USER_ID`` after the DB is wiped
"""
from __future__ import annotations

import hmac
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from screener.core import user_models as um


@pytest.fixture(autouse=True)
def _fixed_secret(monkeypatch):
    secret = bytes.fromhex("ab" * 32)
    monkeypatch.setattr(um, "_SECRET", secret)
    return secret


def _payload(**overrides) -> dict:
    base = {
        "uid": str(uuid.uuid4()),
        "uname": "tester",
        "ver": 0,
        "exp": (datetime.utcnow() + timedelta(days=7)).isoformat(),
        "iat": datetime.utcnow().isoformat(),
    }
    base.update(overrides)
    return base


def _sign(payload_bytes: bytes, secret: bytes) -> str:
    return hmac.new(secret, payload_bytes, hashlib.sha256).hexdigest()


def test_secret_env_override(monkeypatch, tmp_path, _fixed_secret):
    monkeypatch.setenv("SCREENER_TOKEN_SECRET", "c0ffee" * 8)
    secret = um._get_secret()
    assert secret == bytes.fromhex("c0ffee" * 8)

    # Raw (non-hex) values are used as-is.
    monkeypatch.setenv("SCREENER_TOKEN_SECRET", "raw-secret-value")
    assert um._get_secret() == b"raw-secret-value"


def test_secret_falls_back_to_file(tmp_path, monkeypatch, _fixed_secret):
    monkeypatch.delenv("SCREENER_TOKEN_SECRET", raising=False)
    key_file = tmp_path / "data" / ".secret_key"
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.write_bytes(b"file-secret")
    monkeypatch.setattr(um, "_secret_file", lambda: key_file)
    assert um._get_secret() == b"file-secret"


def test_token_round_trip_current_format(_fixed_secret):
    token = um.create_token("uid-1", "alice", token_version=0)
    payload = um.validate_token(token)
    assert payload is not None
    assert payload["uid"] == "uid-1"
    assert payload["uname"] == "alice"


def test_validate_accepts_legacy_dot_separated_format(_fixed_secret):
    payload_bytes = json.dumps(_payload()).encode()
    sig = _sign(payload_bytes, _fixed_secret)
    legacy = f"{payload_bytes.hex()}.{sig}"
    payload = um.validate_token(legacy)
    assert payload is not None
    assert payload["uname"] == "tester"


def test_invalid_signature_rejected(_fixed_secret):
    payload_bytes = json.dumps(_payload()).encode()
    bad = f"{payload_bytes.hex()}.{'00' * 32}"
    assert um.validate_token(bad) is None


def test_expired_token_rejected(_fixed_secret):
    payload_bytes = json.dumps(_payload(exp=(datetime.utcnow() - timedelta(days=1)).isoformat())).encode()
    sig = _sign(payload_bytes, _fixed_secret)
    token = f"{payload_bytes.hex()}.{sig}"
    assert um.validate_token(token) is None


def test_garbage_token_rejected():
    assert um.validate_token("not-a-token") is None
    assert um.validate_token("") is None


# --------------------------------------------------------------------------- #
# Product-owner bootstrap resilience
# --------------------------------------------------------------------------- #
class FakeUserStore:
    def __init__(self):
        self.users = {}
        self.creates = []

    def get_by_id(self, user_id):
        return self.users.get(user_id)

    def get_by_email(self, email):
        for u in self.users.values():
            if u.email == email or u.normalized_email == email:
                return u
        return None

    def get_by_username(self, username):
        for u in self.users.values():
            if u.username == username:
                return u
        return None

    def create_user(self, record):
        self.users[record.user_id] = record
        self.creates.append(record)
        return record

    def update_account(self, user_id, **changes):
        user = self.users.get(user_id)
        if user is None:
            return None
        for key, value in changes.items():
            setattr(user, key, value)
        return user


def test_bootstrap_recreates_owner_with_stable_user_id(monkeypatch, tmp_path):
    from screener.services.control_center_service import ControlCenterService

    stable_id = "00000000-0000-4000-8000-000000000001"
    store = FakeUserStore()
    monkeypatch.setenv("SCREENER_PRODUCT_OWNER_USER_ID", stable_id)
    monkeypatch.setenv("SCREENER_PRODUCT_OWNER_EMAIL", "owner@example.com")
    monkeypatch.setenv("SCREENER_PRODUCT_OWNER_INITIAL_PASSWORD", "long-password-123")

    svc = ControlCenterService.__new__(ControlCenterService)
    monkeypatch.setattr(svc, "_users", store, raising=False)

    # First boot creates the account; simulate a DB wipe + reboot and confirm
    # the same user_id is reused so previously-issued tokens keep validating.
    svc.bootstrap_product_owner()
    assert stable_id in store.users

    store.users.clear()
    svc.bootstrap_product_owner()
    assert stable_id in store.users
    assert store.users[stable_id].email == "owner@example.com"
    assert store.users[stable_id].role == "product_owner"
