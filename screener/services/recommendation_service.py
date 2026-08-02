"""Recommendation engine — ranks a universe of assets into top picks.

Stocks are ranked today; mutual funds are the Phase 3 asset class. The engine
is deliberately universe-driven (a list of symbols in), so plugging in an MF
universe later means supplying different symbols — not changing this code.

Every pick reuses ``AnalysisService`` (entry/target/stop + metrics contract),
so rows come back in the same shape the rest of the app already renders.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from screener.core.config import AppConfig, config
from screener.core.container import container
from screener.core.interfaces import MarketDataProvider
from screener.services.analysis_service import AnalysisService


class RecommendationService:
    """Orchestrates scoring across a universe and ranks the top results."""

    def __init__(
        self,
        analysis: AnalysisService | None = None,
        data_provider: MarketDataProvider | None = None,
    ):
        self._analysis = analysis or container.resolve(AnalysisService)
        self._data = data_provider or container.resolve(MarketDataProvider)

    def recommend_stocks(
        self,
        universe: list[str] | None = None,
        limit: int = 10,
        action: str | None = None,
        app_config: AppConfig | None = None,
        max_workers: int | None = None,
    ) -> dict[str, Any]:
        """Score ``universe`` (default: configured default universe) and return
        the top ``limit`` rows by score, highest first.

        Symbols that fail to analyse are collected in ``failed`` with a reason
        so one bad ticker never sinks the whole recommendation run.
        """
        symbols = list(universe) if universe else list(config.default_universe)
        workers = max_workers or config.data.max_workers

        def _analyze(symbol: str) -> tuple[str, Any]:
            try:
                return symbol, self._analysis.analyze(symbol, app_config)
            except Exception as exc:  # pragma: no cover - defensive
                return symbol, exc

        results: list[Any] = []
        failed: list[dict[str, str]] = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_analyze, s): s for s in symbols}
            for future in as_completed(futures):
                symbol, outcome = future.result()
                if isinstance(outcome, Exception):
                    failed.append({"symbol": symbol, "error": str(outcome)})
                    continue
                if outcome.error is not None:
                    failed.append({"symbol": symbol, "error": outcome.error})
                    continue
                if action and outcome.action.value != action:
                    continue
                results.append(outcome)

        results.sort(key=lambda rec: rec.score, reverse=True)
        top = results[: limit]

        return {
            "count": len(top),
            "total_scanned": len(symbols),
            "failed": failed,
            "results": [rec.to_scan_row() for rec in top],
        }
