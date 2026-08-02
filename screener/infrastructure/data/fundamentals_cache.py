"""Persistent fundamentals cache.

Yahoo's ``info`` scrape is slow and aggressively rate-limited. Fundamentals
change slowly, so caching them to disk for a TTL means scans do not re-fetch
them on every run — the first scan warms the cache, later scans read it.

Thread-safe and best-effort: any I/O failure degrades to a cache miss and is
never allowed to break a scan.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

_TS_KEY = "_ts"


class FundamentalsCache:
    """Disk-backed JSON cache keyed by symbol with a TTL."""

    def __init__(self, path: Path | None = None, ttl_seconds: float = 24 * 3600):
        self._path = path
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self._path or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self._data = raw if isinstance(raw, dict) else {}
        except Exception:
            self._data = {}

    def get(self, symbol: str) -> dict | None:
        key = symbol.strip().upper()
        with self._lock:
            entry = self._data.get(key)
            if not isinstance(entry, dict):
                return None
            fetched_at = entry.get(_TS_KEY, 0)
            if not isinstance(fetched_at, (int, float)) or time.time() - fetched_at >= self._ttl:
                return None
            return {k: v for k, v in entry.items() if k != _TS_KEY} or None

    def set(self, symbol: str, payload: dict) -> None:
        if not payload:
            return
        key = symbol.strip().upper()
        entry = dict(payload)
        entry[_TS_KEY] = time.time()
        with self._lock:
            self._data[key] = entry
        self._save()

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
        if self._path:
            try:
                self._path.unlink(missing_ok=True)
            except Exception:
                pass

    def _save(self) -> None:
        if not self._path:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(self._path.suffix + ".tmp")
            tmp.write_text(json.dumps(self._data, indent=1), encoding="utf-8")
            tmp.replace(self._path)
        except Exception:
            pass
