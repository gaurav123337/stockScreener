"""AMFI mutual-fund data client — free NAV feed (mirrored by mfapi.in).

The official AMFI NAV file (https://www.amfiindia.com/spages/NAVAll.txt)
publishes the full scheme master + daily NAVs once a day, but the AMFI host
is frequently unreachable from datacenter IPs. This client therefore reads
the AMFI data through the free mfapi.in mirror:

  GET /mf            -> scheme master  [{schemeCode, schemeName, isinGrowth, ...}]
  GET /mf/{code}     -> scheme detail  {meta: {scheme_category, scheme_name, ...},
                                        data: [{date, nav}, ...]}  (historical NAVs)

Every payload is cached to disk and reused within a TTL (default 24h — AMFI
publishes daily). When the network fails, the last cached copy is served and
flagged stale, so the screener keeps working offline. Refresh timestamps are
kept on every payload and surfaced in the API (visible data-as-of stamps).
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

import requests

from screener.core.config import config


class AmfiClient:
    """HTTP + disk cache for the AMFI NAV feed."""

    source = "amfi (via mfapi.in)"

    def __init__(
        self,
        base_url: str | None = None,
        cache_dir=None,
        session: requests.Session | None = None,
    ):
        self.base_url = (base_url or config.mutual_fund.base_url).rstrip("/")
        self.cache_dir = cache_dir or config.mf_dir
        self.timeout = config.mutual_fund.timeout_seconds
        self.ttl = config.mutual_fund.cache_ttl_seconds
        self.session = session or requests.Session()

    # ------------------------------------------------------------------ #
    # Public
    # ------------------------------------------------------------------ #

    def fetch_master(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Scheme master list. Returns (items, freshness metadata)."""
        payload, meta = self._get(
            "/mf",
            config.mf_master_file,
            default=[],
        )
        if isinstance(payload, list):  # mfapi.in serves a bare array
            items = payload
        elif isinstance(payload, dict):
            items = payload.get("items") or payload.get("data") or []
        else:
            items = []
        return list(items or []), meta

    def fetch_scheme(self, scheme_code: int) -> tuple[dict[str, Any], dict[str, Any]]:
        """Scheme detail (meta + historical NAV series). Returns (payload, meta)."""
        payload, meta = self._get(
            f"/mf/{int(scheme_code)}",
            config.mf_scheme_file(int(scheme_code)),
            default={},
        )
        return payload, meta

    # ------------------------------------------------------------------ #
    # Internal — HTTP + disk cache
    # ------------------------------------------------------------------ #

    def _get(
        self,
        path: str,
        cache_path,
        default: Any,
    ) -> tuple[Any, dict[str, Any]]:
        """Fetch ``path``, serving the disk cache within TTL / on failure.

        Returns (payload, meta) where meta carries fetched_at / stale flags.
        """
        fresh_meta: dict[str, Any] = {"fetched_at": None, "stale": False}

        try:
            response = self.session.get(
                f"{self.base_url}{path}",
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            fetched_at = datetime.now(timezone.utc).isoformat()
            fresh_meta = {"fetched_at": fetched_at, "stale": False}
            self._write_cache(cache_path, payload, fetched_at)
            return payload, fresh_meta
        except Exception:
            cached = self._read_cache(cache_path)
            if cached is not None:
                payload, stored_at = cached
                return payload, {"fetched_at": stored_at, "stale": True}
            return default, {"fetched_at": None, "stale": True, "error": "fetch failed"}

    def _read_cache(self, cache_path) -> tuple[Any, str] | None:
        """Return (payload, fetched_at) if the cache exists and is fresh."""
        try:
            if not cache_path.exists():
                return None
            raw = json.loads(cache_path.read_text(encoding="utf-8"))
            fetched_at = raw.get("fetched_at") or self._file_mtime(cache_path)
            payload = raw.get("payload", raw)
            if self._is_fresh(fetched_at):
                return payload, fetched_at
            return None
        except Exception:
            return None

    def _write_cache(self, cache_path, payload: Any, fetched_at: str) -> None:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps({"fetched_at": fetched_at, "payload": payload}),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _is_fresh(self, fetched_at: str) -> bool:
        if not fetched_at:
            return False
        try:
            ts = datetime.fromisoformat(fetched_at)
            age = time.time() - ts.timestamp()
            return age <= self.ttl
        except Exception:
            return False

    @staticmethod
    def _file_mtime(cache_path) -> str:
        try:
            ts = cache_path.stat().st_mtime
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        except Exception:
            return ""

    # ------------------------------------------------------------------ #
    # Freshness helpers
    # ------------------------------------------------------------------ #

    def data_as_of(self) -> str | None:
        """ISO timestamp of the cached master payload (or None when absent)."""
        try:
            raw = json.loads(config.mf_master_file.read_text(encoding="utf-8"))
            return raw.get("fetched_at")
        except Exception:
            return None
