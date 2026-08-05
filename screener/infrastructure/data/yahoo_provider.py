"""Yahoo Finance implementation of MarketDataProvider."""
from __future__ import annotations

import time
from typing import Any

import pandas as pd

from screener.core.config import config
from screener.core.interfaces import MarketDataProvider
from screener.infrastructure.data.fundamentals_cache import FundamentalsCache
from screener.infrastructure.data.history_cache import HistoryCache
from screener.infrastructure.data.nse_master import NseMasterStore

try:
    import yfinance as yf
except ImportError:  # pragma: no cover
    yf = None


class YahooDataProvider(MarketDataProvider):
    """Fetches OHLCV and fundamentals from Yahoo Finance.

    Symbols are normalised leniently (case / whitespace / separators) and,
    when no exchange suffix is given, NSE (`.NS`) is tried first with an
    automatic fallback to BSE (`.BO`) — this is what lets users search any
    specific stock, not just Nifty-50 names.

    Fundamentals (``fetch_info``) are cached to disk for a configurable TTL
    because Yahoo's ``info`` scrape is slow and rate-limited, and they fall
    back to the offline NSE master so every scan row still carries a company
    name and industry even when the scrape fails.
    """

    def __init__(
        self,
        fundamentals_cache: FundamentalsCache | None = None,
        nse_master: NseMasterStore | None = None,
        history_cache: HistoryCache | None = None,
    ):
        self._fundamentals = fundamentals_cache or FundamentalsCache(
            config.data_dir / "fundamentals_cache.json",
            ttl_seconds=config.data.fundamentals_cache_ttl_seconds,
        )
        self._history = history_cache or HistoryCache(
            config.data_dir / "history_cache.json",
            ttl_seconds=config.data.history_cache_ttl_seconds,
        )
        self._nse = nse_master or NseMasterStore()

    def normalize_symbol(self, symbol: str, exchange: str = "NS") -> str:
        """Convert 'RELIANCE' -> 'RELIANCE.NS'. Pass-through if already suffixed.

        Handles messy user input: lowercase, extra spaces, and common
        separators (``M&M`` / ``M%26M`` / ``L&T`` etc.).
        """
        s = symbol.strip().upper().replace("%26", "&")
        # collapse inner whitespace to a single dash-friendly form
        s = " ".join(s.split())
        if s.endswith(".NS") or s.endswith(".BO"):
            return s
        return f"{s}.{exchange}"

    # ------------------------------------------------------------------ #
    # Symbol resolution helpers
    # ------------------------------------------------------------------ #
    def resolve_symbol(self, symbol: str) -> str | None:
        """Return the Yahoo ticker that actually has data, or None.

        Tries the ticker as given, then NSE, then BSE. Fast-fails using a
        tiny download so we don't burn the full retry budget per candidate.
        """
        if yf is None:
            return None
        raw = symbol.strip().upper().replace("%26", "&")
        raw = " ".join(raw.split())
        candidates: list[str] = []
        if raw.endswith(".NS") or raw.endswith(".BO"):
            candidates.append(raw)
        else:
            candidates = [f"{raw}.NS", f"{raw}.BO"]
        for cand in candidates:
            try:
                df = yf.download(
                    cand, period="5d", interval="1d",
                    progress=False, auto_adjust=True,
                )
                if df is not None and not df.empty:
                    return cand
            except Exception:
                continue
        return None

    def search(self, query: str, limit: int = 8) -> list[dict[str, str]]:
        """Search Yahoo for matching symbols / company names (NSE & BSE)."""
        if yf is None or not query.strip():
            return []
        try:
            res = yf.Search(query.strip(), max_results=limit * 2, news_count=0)
            quotes = getattr(res, "quotes", None) or []
        except Exception:
            return []
        out: list[dict[str, str]] = []
        for q in quotes:
            sym = (q.get("symbol") or "").upper()
            if not (sym.endswith(".NS") or sym.endswith(".BO")):
                continue
            # Keep only real stocks (skip mutual funds / ETFs / indices noise).
            qtype = (q.get("quoteType") or "").upper()
            if qtype and qtype not in ("EQUITY",):
                continue
            out.append({
                "symbol": sym,
                "name": q.get("shortname") or q.get("longname") or sym,
                "exchange": "NSE" if sym.endswith(".NS") else "BSE",
                "type": qtype,
            })
        # Prefer NSE listings first (more liquid), then BSE.
        out.sort(key=lambda x: 0 if x["exchange"] == "NSE" else 1)
        return out[:limit]

    # ------------------------------------------------------------------ #
    # MarketDataProvider API
    # ------------------------------------------------------------------ #
    def fetch_history(
        self,
        symbol: str,
        period: str | None = None,
        interval: str | None = None,
    ) -> pd.DataFrame | None:
        """Fetch OHLCV history with a disk cache + retries + NSE->BSE fallback.

        A successful download is cached for ``history_cache_ttl_seconds``, so
        repeated scans read from disk instead of hammering the provider. The
        cache is best-effort: any I/O failure just means one re-fetch.
        """
        if yf is None:
            return None

        period = period or config.data.default_period
        interval = interval or config.data.default_interval

        raw = symbol.strip().upper().replace("%26", "&")
        raw = " ".join(raw.split())

        # Try the disk cache first (per symbol, period and interval).
        cached = self._history.get(raw, period, interval)
        if cached is not None and not cached.empty:
            return cached

        candidates = (
            [raw] if (raw.endswith(".NS") or raw.endswith(".BO"))
            else [f"{raw}.NS", f"{raw}.BO"]
        )

        for sym in candidates:
            df = self._download(sym, period, interval)
            if df is not None:
                self._history.set(raw, period, interval, df)
                return df
        return None

    def history_updated_at(self):
        """UTC timestamp of the freshest cached history (None when empty).

        Surfaces "data as of …" for the compliance/freshness envelope.
        """
        return self._history.last_fetched_at()

    def _download(
        self, sym: str, period: str, interval: str
    ) -> pd.DataFrame | None:
        """One symbol, retried per config. Returns None on failure."""
        for attempt in range(config.data.retry_attempts + 1):
            try:
                df = yf.download(
                    sym,
                    period=period,
                    interval=interval,
                    progress=False,
                    auto_adjust=True,
                )
                if df is not None and not df.empty:
                    # Flatten possible MultiIndex columns from newer yfinance
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    return df
            except Exception:
                pass
            if attempt < config.data.retry_attempts:
                time.sleep(config.data.retry_pause_seconds)
        return None

    def fetch_info(self, symbol: str) -> dict[str, Any]:
        """Fetch a fundamentals snapshot, cached, with NSE metadata fallback.

        Returns ``{}`` on failure (non-fatal). Yahoo's ``info`` scrape is slow
        and rate-limited, so successful results are cached to disk for a TTL
        (keyed on the bare NSE/BSE symbol). Company name / industry fall back
        to the offline NSE master so rows always carry a label.
        """
        sym = self.normalize_symbol(symbol)
        bare = self._bare_symbol(sym)

        cached = self._fundamentals.get(bare)
        if cached:
            return cached

        info = self._scrape_info(sym)

        # Merge offline NSE metadata (name + industry) as a label fallback.
        row = self._nse.lookup(bare)
        if row:
            info.setdefault("longName", row["name"] or None)
            info.setdefault("sector", row["industry"] or None)
            info.setdefault("industry", row["industry"] or None)

        if info:
            self._fundamentals.set(bare, info)
        return info

    def _scrape_info(self, sym: str) -> dict[str, Any]:
        """One Yahoo fundamentals scrape, retried per config. {} on failure."""
        if yf is None:
            return {}
        for attempt in range(config.data.retry_attempts + 1):
            try:
                ticker = yf.Ticker(sym)
                # ``get_info()`` was deprecated in favour of ``info``; guard so
                # this keeps working across yfinance versions.
                info = ticker.get_info() if hasattr(ticker, "get_info") else ticker.info
                info = info or {}
                keys = [
                    "longName", "sector", "industry", "marketCap", "currency",
                    "trailingPE", "forwardPE", "pegRatio", "priceToBook",
                    "returnOnEquity", "debtToEquity", "profitMargins",
                    "revenueGrowth", "earningsGrowth", "currentPrice",
                    "fiftyTwoWeekHigh", "fiftyTwoWeekLow", "fiftyDayAverage",
                    "twoHundredDayAverage", "dividendYield", "beta",
                ]
                return {k: info.get(k) for k in keys if info.get(k) is not None}
            except Exception:
                pass
            if attempt < config.data.retry_attempts:
                time.sleep(config.data.retry_pause_seconds)
        return {}

    @staticmethod
    def _bare_symbol(sym: str) -> str:
        """Strip the Yahoo exchange suffix for cross-provider cache keys."""
        if sym.endswith(".NS") or sym.endswith(".BO"):
            return sym[:-3]
        return sym
