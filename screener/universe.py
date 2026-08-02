"""Default symbol universes (NSE). Kept as data, not code, so they are easy
to edit or extend. Symbols are Yahoo-suffixed at fetch time.

- ``NIFTY50``  : the classic 50-stock default (also the fallback universe).
- ``NIFTY500`` : the full screening universe, loaded from the vendored NSE
  index-constituents file ``screener/data/ind_nifty500list.csv``.
"""

from __future__ import annotations

import csv
from pathlib import Path

NIFTY50 = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJAJFINSV", "BAJFINANCE", "BEL", "BHARTIARTL",
    "BPCL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY",
    "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE",
    "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "INDUSINDBK",
    "INFY", "ITC", "JSWSTEEL", "KOTAKBANK", "LT",
    "M&M", "MARUTI", "NESTLEIND", "NTPC", "ONGC",
    "POWERGRID", "RELIANCE", "SBILIFE", "SBIN", "SHRIRAMFIN",
    "SUNPHARMA", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TCS",
    "TECHM", "TITAN", "TRENT", "ULTRACEMCO", "WIPRO",
]

_NIFTY500_CSV = Path(__file__).resolve().parent / "data" / "ind_nifty500list.csv"


def nifty500_symbols() -> list[str]:
    """Load the Nifty-500 symbol list from the vendored NSE CSV.

    Falls back to ``NIFTY50`` if the file is missing or unreadable so the
    application still boots in restricted/partial deployments.
    """
    if not _NIFTY500_CSV.exists():
        return list(NIFTY50)
    try:
        with _NIFTY500_CSV.open("r", encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
    except (OSError, csv.Error):
        return list(NIFTY50)
    symbols = [str(row.get("Symbol") or "").strip().upper() for row in rows]
    symbols = [s for s in symbols if s]
    return symbols or list(NIFTY50)


def default_universe() -> list[str]:
    """The default screening universe: Nifty 500, else Nifty 50."""
    return nifty500_symbols()
