"""Yahoo-based adapter for the Indian market research workspace.

This adapter demonstrates the provider-adapter pattern: it implements the same
``IndianMarketGateway`` contract as ``IndianApiClient`` and normalises Yahoo's
data onto the same common keys, so switching providers is purely a
configuration change — the front end and application services are untouched.

Yahoo cannot serve every research endpoint (``trending``, ``commodities``,
``stock_forecasts``, ...); those degrade to empty results rather than breaking
the contract. Mutual-fund search is intentionally empty until the Phase 3
mutual-fund universe lands.
"""
from __future__ import annotations

import threading
from typing import Any

import pandas as pd

from screener.core.indian_market import (
    HistoricalSeries,
    HistoricalStats,
    IndianApiTelemetry,
    IndianMarketGateway,
    MarketSnapshot,
    StockSearchResult,
    StockSummary,
)
from screener.core.interfaces import MarketDataProvider
from screener.infrastructure.data.nse_master import NseMasterStore

_PERIOD_ALIASES = {
    "1D": "1d",
    "1W": "5d",
    "1M": "1mo",
    "3M": "3mo",
    "6M": "6mo",
    "1Y": "1y",
    "2Y": "2y",
    "5Y": "5y",
    "10Y": "10y",
}

_STATS_KEYS = (
    "marketCap", "trailingPE", "forwardPE", "pegRatio", "priceToBook",
    "returnOnEquity", "debtToEquity", "profitMargins", "revenueGrowth",
    "earningsGrowth", "dividendYield", "beta",
    "fiftyTwoWeekHigh", "fiftyTwoWeekLow", "currentPrice",
)

_ANALYSIS_ENDPOINTS = {"stock_target_price", "stock_forecasts", "mutual_funds"}


class YahooIndianProvider(IndianMarketGateway):
    """Adapts Yahoo Finance data to the Indian market gateway contract."""

    def __init__(
        self,
        data_provider: MarketDataProvider,
        nse_master: NseMasterStore | None = None,
    ):
        self._data = data_provider
        self._nse = nse_master or NseMasterStore()
        self._telemetry = IndianApiTelemetry()
        self._telemetry_lock = threading.Lock()

    @property
    def provider_name(self) -> str:
        return "yahoo"

    def _record(self, **changes: Any) -> None:
        with self._telemetry_lock:
            current = self._telemetry.model_dump()
            for key, value in changes.items():
                current[key] = current[key] + value if key in {"requests", "successes", "errors"} else value
            self._telemetry = IndianApiTelemetry(**current)

    def telemetry(self) -> IndianApiTelemetry:
        with self._telemetry_lock:
            return self._telemetry.model_copy(deep=True)

    @staticmethod
    def _bare(symbol: str) -> str:
        if symbol.endswith((".NS", ".BO")):
            return symbol[:-3]
        return symbol

    # ------------------------------------------------------------------ #
    # Contract implementation
    # ------------------------------------------------------------------ #
    def stock(self, name: str) -> StockSummary:
        raw = name.strip().upper().replace("%26", "&")
        sym = self._data.normalize_symbol(raw)
        info = self._data.fetch_info(sym)
        row = self._nse.lookup(raw)

        history = self._data.fetch_history(sym, period="1y")
        last = prev = None
        if history is not None and not history.empty:
            last = float(history["Close"].iloc[-1])
            if len(history) > 1:
                prev = float(history["Close"].iloc[-2])
        percent_change = None
        if last is not None and prev:
            percent_change = round((last - prev) / prev * 100, 2)

        return StockSummary(
            ticker_id=self._bare(sym),
            company_name=info.get("longName") or (row["name"] if row else None),
            industry=info.get("industry") or (row["industry"] if row else None),
            current_price={"NSE": last} if last is not None else {},
            percent_change=percent_change,
            year_high=info.get("fiftyTwoWeekHigh"),
            year_low=info.get("fiftyTwoWeekLow"),
            raw={"source": "yahoo", "name": name},
        )

    def search(self, endpoint: str, query: str) -> list[dict[str, Any]]:
        endpoint = endpoint.strip()
        needle = query.strip().upper()
        if endpoint == "industry_search":
            if not needle:
                return []
            results: list[dict[str, Any]] = []
            for symbol in self._nse.symbols():
                row = self._nse.lookup(symbol)
                name = (row["name"] or "").upper()
                industry = (row["industry"] or "").upper()
                if needle in symbol or needle in name or needle in industry:
                    results.append(StockSearchResult(
                        ticker_id=symbol,
                        company_name=row["name"] or None,
                        industry=row["industry"] or None,
                        exchange="NSE",
                    ).model_dump())
                    if len(results) >= 20:
                        break
            return results
        if endpoint == "mutual_fund_search":
            return []  # MF universe arrives in Phase 3
        raise ValueError(f"unsupported Indian market endpoint: {endpoint}")

    def snapshot(self, endpoint: str) -> MarketSnapshot:
        # Yahoo has no trending / most-active / commodities feeds. Degrade
        # gracefully instead of breaking the FE overview contract.
        return MarketSnapshot(category=endpoint, items=[])

    def history(self, stock_id: str, **params: str) -> HistoricalSeries:
        sym = self._data.normalize_symbol(stock_id)
        period = _PERIOD_ALIASES.get(str(params.get("period") or "1Y").upper(), "1y")
        df = self._data.fetch_history(sym, period=period)
        if df is None or df.empty:
            return HistoricalSeries(stock_id=stock_id, points=[])
        points: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            ts = row.name
            points.append({
                "date": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                "open": round(float(row["Open"]), 2) if pd.notna(row["Open"]) else None,
                "high": round(float(row["High"]), 2) if pd.notna(row["High"]) else None,
                "low": round(float(row["Low"]), 2) if pd.notna(row["Low"]) else None,
                "close": round(float(row["Close"]), 2) if pd.notna(row["Close"]) else None,
                "volume": int(row["Volume"]) if pd.notna(row["Volume"]) else None,
            })
        return HistoricalSeries(stock_id=stock_id, points=points)

    def historical_stats(self, stock_id: str, **params: str) -> HistoricalStats:
        sym = self._data.normalize_symbol(stock_id)
        info = self._data.fetch_info(sym)
        stats = {key: info.get(key) for key in _STATS_KEYS if info.get(key) is not None}
        return HistoricalStats(stock_id=stock_id, stats=stats)

    def analysis(self, endpoint: str, stock_id: str, **params: str) -> Any:
        if endpoint not in _ANALYSIS_ENDPOINTS:
            raise ValueError(f"unsupported analytical endpoint: {endpoint}")
        sym = self._data.normalize_symbol(stock_id)
        if endpoint == "stock_target_price":
            info = self._data.fetch_info(sym)
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            if price is None:
                history = self._data.fetch_history(sym, period="1y")
                if history is not None and not history.empty:
                    price = float(history["Close"].iloc[-1])
            if price is None:
                return {}
            high52 = info.get("fiftyTwoWeekHigh")
            target = high52 if high52 and high52 > price else price * 1.05
            return {"target_price": round(float(target), 2), "current_price": round(float(price), 2)}
        return {}  # stock_forecasts / mutual_funds are not available from Yahoo
