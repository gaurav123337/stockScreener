"""Offline NSE master metadata — company names, industries, and the
Nifty-500 symbol list vendored from NSE's public index constituents CSV.

This gives scan results a human-readable label (name + industry) even when the
price provider's own metadata call fails or is rate-limited. The file lives at
``screener/data/ind_nifty500list.csv`` and is refreshed from:
https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv
"""
from __future__ import annotations

import csv
from pathlib import Path

_NSE_MASTER_CSV = Path(__file__).resolve().parent.parent.parent / "data" / "ind_nifty500list.csv"


class NseMasterStore:
    """Loads the vendored NSE master file once and serves lookups.

    Providers:
    - ``symbols()``: the Nifty-500 symbol list (bare NSE codes).
    - ``name(symbol)`` / ``industry(symbol)``: company metadata lookups that
      tolerate Yahoo suffixes (``.NS`` / ``.BO``) and common separators.
    """

    def __init__(self, csv_path: Path | None = None):
        self._csv_path = csv_path or _NSE_MASTER_CSV
        self._rows: list[dict[str, str]] = []
        self._by_symbol: dict[str, dict[str, str]] = {}
        self._load()

    def _load(self) -> None:
        path = self._csv_path
        if not path.exists():
            return
        try:
            with path.open("r", encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
        except (OSError, csv.Error):
            return
        by_symbol: dict[str, dict[str, str]] = {}
        for row in rows:
            symbol = str(row.get("Symbol") or "").strip().upper()
            if not symbol:
                continue
            by_symbol[symbol] = {
                "symbol": symbol,
                "name": str(row.get("Company Name") or "").strip(),
                "industry": str(row.get("Industry") or "").strip(),
            }
        self._rows = rows
        self._by_symbol = by_symbol

    @property
    def available(self) -> bool:
        return bool(self._rows)

    def symbols(self) -> list[str]:
        return list(self._by_symbol.keys())

    @staticmethod
    def _normalize(symbol: str) -> str:
        s = symbol.strip().upper().replace("%26", "&")
        s = " ".join(s.split())
        for suffix in (".NS", ".BO"):
            if s.endswith(suffix):
                return s[: -len(suffix)]
        return s

    def lookup(self, symbol: str) -> dict[str, str] | None:
        return self._by_symbol.get(self._normalize(symbol))

    def name(self, symbol: str) -> str | None:
        row = self.lookup(symbol)
        return row["name"] if row else None

    def industry(self, symbol: str) -> str | None:
        row = self.lookup(symbol)
        return row["industry"] if row else None
