"""Analysis Service — central business logic for stock analysis.

This is the SINGLE place where recommendations are built. Both CLI and API
use this service, eliminating the previous duplication.
"""
from __future__ import annotations

import pandas as pd

from screener.core.config import AppConfig, config
from screener.core.container import container
from screener.core.indicators import add_all
from screener.core.interfaces import MarketDataProvider
from screener.core.models import Action, Recommendation, StockMetrics
from screener.services.scoring_engine import ScoringEngine


class AnalysisService:
    """Orchestrates data fetching, scoring, and recommendation building."""

    def __init__(
        self,
        data_provider: MarketDataProvider | None = None,
        scoring_engine: ScoringEngine | None = None,
    ):
        self._data = data_provider or container.resolve(MarketDataProvider)
        self._scorer = scoring_engine or ScoringEngine()

    def analyze(self, symbol: str, app_config: AppConfig | None = None) -> Recommendation:
        """Produce a full recommendation for a symbol.

        Resolves the symbol first so that names without an exchange suffix
        work on both NSE and BSE, and the returned symbol is the real ticker.
        """
        effective_config = app_config or config
        resolved = symbol
        resolver = getattr(self._data, "resolve_symbol", None)
        if callable(resolver):
            resolved = resolver(symbol) or symbol

        history = self._data.fetch_history(resolved)
        if history is None or history.empty or len(history) < 60:
            return Recommendation(
                symbol=symbol.upper(),
                action=Action.HOLD,
                score=0.0,
                price=0.0,
                error="insufficient price history",
            )

        # Clean: drop rows where Close is NaN (Yahoo placeholder rows)
        history = history.dropna(subset=["Close"])
        if len(history) < 60:
            return Recommendation(
                symbol=symbol.upper(),
                action=Action.HOLD,
                score=0.0,
                price=0.0,
                error="insufficient price history after cleaning",
            )

        info = self._data.fetch_info(resolved)
        df = add_all(history)
        last, prev = df.iloc[-1], df.iloc[-2]
        price = float(last["Close"])

        # Score via pluggable engine
        scorer = self._scorer
        if app_config is not None:
            scorer = ScoringEngine(
                use_registry=False,
                scoring_config=effective_config.scoring,
            )
        score, reasons = scorer.total_score(last, prev, info)
        score = float(max(-100, min(100, score)))

        # Map to action
        if score >= effective_config.scoring.buy_threshold:
            action = Action.BUY
        elif score <= effective_config.scoring.sell_threshold:
            action = Action.SELL
        else:
            action = Action.HOLD

        # Build trade levels
        entry, target, stop, rr = self._build_levels(
            action, price, last, effective_config
        )

        # Assemble metrics
        metrics = self._build_metrics(price, last, info)

        return Recommendation(
            symbol=self._data.normalize_symbol(resolved),
            action=action,
            score=score,
            price=round(price, 2),
            entry=entry,
            target=target,
            stop_loss=stop,
            risk_reward=rr,
            reasons=reasons,
            metrics=metrics,
        )

    def _build_levels(
        self,
        action: Action,
        price: float,
        last: pd.Series,
        app_config: AppConfig = config,
    ) -> tuple[float | None, float | None, float | None, float | None]:
        """Calculate entry, target, stop-loss, and R:R."""
        atr = float(last["ATR14"]) if pd.notna(last.get("ATR14")) else price * 0.03
        sma50 = float(last["SMA50"]) if pd.notna(last.get("SMA50")) else None
        high52 = float(last["High52"]) if pd.notna(last.get("High52")) else None
        low52 = float(last["Low52"]) if pd.notna(last.get("Low52")) else None

        entry = target = stop = rr = None

        if action == Action.BUY:
            entry = round(price, 2)
            atr_stop = price - app_config.risk.atr_multiplier * atr
            candidates = [atr_stop]
            if sma50:
                candidates.append(sma50 * app_config.risk.sma50_stop_discount)
            valid = [c for c in candidates if c < price]
            stop = round(max(valid), 2) if valid else round(atr_stop, 2)

            risk = price - stop
            tgt_candidates = [price + app_config.risk.risk_reward_target * risk]
            if high52 and high52 > price:
                tgt_candidates.append(high52)
            target = round(min(tgt_candidates), 2)
            rr = round((target - price) / risk, 2) if risk > 0 else None

        elif action == Action.SELL:
            entry = round(price, 2)
            stop = round(price + app_config.risk.atr_multiplier * atr, 2)
            risk = stop - price
            tgt_candidates = [price - app_config.risk.risk_reward_target * risk]
            if low52 and low52 < price:
                tgt_candidates.append(low52)
            target = round(max(tgt_candidates), 2)
            rr = round((price - target) / risk, 2) if risk > 0 else None

        return entry, target, stop, rr

    def _build_metrics(self, price: float, last: pd.Series, info: dict) -> StockMetrics:
        """Build the metrics object with derived flags."""
        sma50 = float(last["SMA50"]) if pd.notna(last.get("SMA50")) else None
        sma200 = float(last["SMA200"]) if pd.notna(last.get("SMA200")) else None
        high52 = float(last["High52"]) if pd.notna(last.get("High52")) else None
        low52 = float(last["Low52"]) if pd.notna(last.get("Low52")) else None

        return StockMetrics(
            pe=info.get("trailingPE"),
            peg=info.get("pegRatio"),
            roe=info.get("returnOnEquity"),
            debt_to_equity=info.get("debtToEquity"),
            sector=info.get("sector"),
            name=info.get("longName"),
            rsi=round(float(last["RSI14"]), 1) if pd.notna(last.get("RSI14")) else None,
            sma50=round(sma50, 2) if sma50 else None,
            sma200=round(sma200, 2) if sma200 else None,
            atr=round(float(last["ATR14"]), 2) if pd.notna(last.get("ATR14")) else None,
            macd=float(last["MACD"]) if pd.notna(last.get("MACD")) else None,
            macd_signal=float(last["MACDsig"]) if pd.notna(last.get("MACDsig")) else None,
            volume=float(last["Volume"]) if pd.notna(last.get("Volume")) else None,
            volume_avg_20=float(last["VolAvg20"]) if pd.notna(last.get("VolAvg20")) else None,
            high_52w=high52,
            low_52w=low52,
            above_sma50=bool(sma50 and price > sma50),
            above_sma200=bool(sma200 and price > sma200),
            golden_cross=bool(sma50 and sma200 and sma50 > sma200),
            near_52w_high=bool(high52 and price >= 0.95 * high52),
            near_52w_low=bool(low52 and price <= 1.05 * low52),
        )
