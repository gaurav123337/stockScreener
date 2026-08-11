"""Persistent OHLCV history cache — the rate-limit layer.

Price history is re-downloaded on every scan today, which hammers the price
provider and makes scans slow. Prices change slowly enough that caching a
day's worth of 1d OHLCV to disk for a TTL cuts provider calls dramatically:
the first scan of a universe warms the cache, later scans read it.

Thread-safe and best-effort: any I/O failure degrades to a cache miss and is
never allowed to break a scan. DataFrames are serialised with
``df.to_json(orient="split")`` so NaN/NA round-trips cleanly.
"""
from __future__ import annotations

import io
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_TS_KEY = "_ts"
_DATA_KEY = "data"


class HistoryCache:
    """Disk-backed JSON cache keyed by ``symbol:period:interval`` with a TTL."""

    def __init__(self, path: Path | None = None, ttl_seconds: float = 3600):
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

    @staticmethod
    def _key(symbol: str, period: str, interval: str) -> str:
        bare = symbol.strip().upper()
        if bare.endswith(".NS") or bare.endswith(".BO"):
            bare = bare[:-3]
        return f"{bare}:{period}:{interval}"

    def get(self, symbol: str, period: str, interval: str) -> pd.DataFrame | None:
        key = self._key(symbol, period, interval)
        with self._lock:
            entry = self._data.get(key)
            if not isinstance(entry, dict):
                return None
            fetched_at = entry.get(_TS_KEY, 0)
            if not isinstance(fetched_at, (int, float)) or time.time() - fetched_at >= self._ttl:
                return None
            payload = entry.get(_DATA_KEY)
            if not payload:
                return None
        try:
            return pd.read_json(io.StringIO(payload), orient="split")
        except Exception:
            return None

    def set(self, symbol: str, period: str, interval: str, df: pd.DataFrame) -> None:
        if df is None or df.empty:
            return
        key = self._key(symbol, period, interval)
        try:
            payload = df.to_json(orient="split", date_format="iso")
        except Exception:
            return
        entry = {_TS_KEY: time.time(), _DATA_KEY: payload}
        with self._lock:
            self._data[key] = entry
        self._save()

    def last_fetched_at(self) -> datetime | None:
        """UTC timestamp of the freshest entry (None when the cache is empty).

        Used to report "data as of …" and to flag stale scans.
        """
        latest = 0.0
        with self._lock:
            for entry in self._data.values():
                ts = entry.get(_TS_KEY, 0)
                if isinstance(ts, (int, float)) and ts > latest:
                    latest = ts
        if not latest:
            return None
        return datetime.fromtimestamp(latest, tz=timezone.utc)

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
