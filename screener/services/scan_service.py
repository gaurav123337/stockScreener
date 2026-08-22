"""Scan Service — unified scanning logic for CLI and API.

Eliminates the duplication between main.py:_scan_row and api.py:_rec_to_dict.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from screener.core.config import AppConfig, config
from screener.core.models import Action, Recommendation, ScanResult
from screener.services.analysis_service import AnalysisService


class ScanService:
    """Orchestrates scanning a universe of stocks with optional filtering."""

    def __init__(
        self,
        analysis_service: AnalysisService | None = None,
    ):
        self._analysis = analysis_service or AnalysisService()

    def scan(
        self,
        symbols: list[str] | None = None,
        predicate: Callable[[dict], bool] | None = None,
        top: int | None = None,
        max_workers: int | None = None,
        app_config: AppConfig | None = None,
    ) -> ScanResult:
        """Scan symbols and return matched recommendations."""
        effective_config = app_config or config
        symbols = symbols or effective_config.default_universe
        workers = max_workers or effective_config.data.max_workers

        recommendations_by_symbol: dict[str, Recommendation] = {}
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {
                ex.submit(self._analysis.analyze, symbol, effective_config): symbol
                for symbol in symbols
            }
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    recommendations_by_symbol[symbol] = future.result()
                except Exception as error:
                    recommendations_by_symbol[symbol] = Recommendation(
                        symbol=symbol.upper(),
                        action=Action.NEUTRAL,
                        score=0.0,
                        price=0.0,
                        error=str(error) or "analysis failed",
                    )

        recommendations = [recommendations_by_symbol[symbol] for symbol in symbols]

        # Prediction logging happens at the API/CLI layer so the authenticated
        # user_id can be attached (see api.py / main.py).
        matched = [r for r in recommendations if r.error is None]
        failed = [
            {"symbol": r.symbol, "error": r.error or "unknown"}
            for r in recommendations
            if r.error is not None
        ]

        # Apply filter
        if predicate:
            matched = [r for r in matched if predicate(r.to_scan_row())]

        # Sort by score descending
        matched.sort(key=lambda r: r.score, reverse=True)

        if top:
            matched = matched[:top]

        return ScanResult(
            matched=matched,
            failed=failed,
            total_scanned=len(symbols),
            filter_applied=getattr(predicate, "__name__", None) if predicate else None,
        )

    def scan_with_rows(
        self,
        symbols: list[str] | None = None,
        predicate: Callable[[dict], bool] | None = None,
        top: int | None = None,
    ) -> tuple[list[dict], list[dict]]:
        """Legacy-compatible scan returning dict rows (for backward compat)."""
        result = self.scan(symbols, predicate, top)
        rows = [r.to_scan_row() for r in result.matched]
        return rows, result.failed
