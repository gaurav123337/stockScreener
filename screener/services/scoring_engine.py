"""Scoring Engine — pluggable scoring strategies.

Instead of monolithic _score_* functions, each aspect is a strategy.
New strategies can be registered without modifying existing code.
"""
from __future__ import annotations

import pandas as pd

from screener.core.config import config
from screener.core.interfaces import ScoringStrategy
from screener.core.plugins import registry


class TrendScorer(ScoringStrategy):
    """Scores trend vs moving averages."""

    @property
    def name(self) -> str:
        return "trend"

    def score(self, last: pd.Series, prev: pd.Series | None, info: dict) -> tuple[float, list[str]]:
        score = 0.0
        reasons: list[str] = []
        price = last["Close"]
        sma50, sma200 = last.get("SMA50"), last.get("SMA200")

        if pd.notna(sma50):
            if price > sma50:
                score += config.scoring.trend_weight_sma50
                reasons.append(f"Price above 50-DMA ({sma50:.1f}) — short-term uptrend")
            else:
                score -= config.scoring.trend_weight_sma50
                reasons.append(f"Price below 50-DMA ({sma50:.1f}) — short-term weakness")

        if pd.notna(sma200):
            if price > sma200:
                score += config.scoring.trend_weight_sma200
                reasons.append(f"Price above 200-DMA ({sma200:.1f}) — long-term uptrend")
            else:
                score -= config.scoring.trend_weight_sma200
                reasons.append(f"Price below 200-DMA ({sma200:.1f}) — long-term downtrend")

        if pd.notna(sma50) and pd.notna(sma200):
            if sma50 > sma200:
                score += config.scoring.trend_weight_cross
                reasons.append("Golden-cross alignment (50-DMA > 200-DMA)")
            else:
                score -= config.scoring.trend_weight_cross
                reasons.append("Death-cross alignment (50-DMA < 200-DMA)")

        return score, reasons


class MomentumScorer(ScoringStrategy):
    """Scores RSI and MACD momentum."""

    @property
    def name(self) -> str:
        return "momentum"

    def score(self, last: pd.Series, prev: pd.Series | None, info: dict) -> tuple[float, list[str]]:
        score = 0.0
        reasons: list[str] = []
        r = last.get("RSI14")

        if pd.notna(r):
            if r >= 70:
                score -= config.scoring.momentum_weight_rsi
                reasons.append(f"RSI {r:.0f} — overbought, pullback risk")
            elif r >= 55:
                score += config.scoring.momentum_weight_rsi
                reasons.append(f"RSI {r:.0f} — healthy bullish momentum")
            elif r >= 45:
                reasons.append(f"RSI {r:.0f} — neutral")
            elif r >= 30:
                score -= 5
                reasons.append(f"RSI {r:.0f} — weak momentum")
            else:
                score += 5
                reasons.append(f"RSI {r:.0f} — oversold, possible bounce")

        macd, sig = last.get("MACD"), last.get("MACDsig")
        p_macd = prev.get("MACD") if prev is not None else None
        p_sig = prev.get("MACDsig") if prev is not None else None

        if pd.notna(macd) and pd.notna(sig):
            if macd > sig:
                score += config.scoring.momentum_weight_macd
                reasons.append("MACD above signal — bullish momentum")
                if pd.notna(p_macd) and pd.notna(p_sig) and p_macd <= p_sig:
                    score += config.scoring.momentum_weight_crossover
                    reasons.append("Fresh MACD bullish crossover")
            else:
                score -= config.scoring.momentum_weight_macd
                reasons.append("MACD below signal — bearish momentum")
                if pd.notna(p_macd) and pd.notna(p_sig) and p_macd >= p_sig:
                    score -= config.scoring.momentum_weight_crossover
                    reasons.append("Fresh MACD bearish crossover")

        return score, reasons


class VolumeScorer(ScoringStrategy):
    """Scores volume participation."""

    @property
    def name(self) -> str:
        return "volume"

    def score(self, last: pd.Series, prev: pd.Series | None, info: dict) -> tuple[float, list[str]]:
        v, va = last.get("Volume"), last.get("VolAvg20")
        if pd.notna(v) and pd.notna(va) and va > 0:
            ratio = v / va
            if ratio >= 1.5:
                return config.scoring.volume_weight, [
                    f"Volume {ratio:.1f}x 20-day avg — strong participation"
                ]
        return 0.0, []


class FundamentalScorer(ScoringStrategy):
    """Scores PEG, ROE, and debt levels."""

    @property
    def name(self) -> str:
        return "fundamentals"

    def score(self, last: pd.Series, prev: pd.Series | None, info: dict) -> tuple[float, list[str]]:
        if not info:
            return 0.0, []

        score = 0.0
        reasons: list[str] = []
        peg = info.get("pegRatio")
        pe = info.get("trailingPE")
        roe = info.get("returnOnEquity")
        de = info.get("debtToEquity")
        eg = info.get("earningsGrowth")

        if peg is not None:
            if peg < 1:
                score += config.scoring.fundamental_peg_weight
                reasons.append(f"PEG {peg:.2f} < 1 — undervalued vs growth")
            elif peg > 2:
                score -= config.scoring.fundamental_peg_weight
                reasons.append(f"PEG {peg:.2f} > 2 — expensive vs growth")
        elif pe is not None and eg is not None and eg > 0:
            implied = pe / (eg * 100)
            if implied < 1:
                score += 8
                reasons.append(f"P/E {pe:.1f} low vs earnings growth {eg*100:.0f}%")
            elif implied > 2:
                score -= 8
                reasons.append(f"P/E {pe:.1f} high vs earnings growth {eg*100:.0f}%")

        if roe is not None:
            if roe >= 0.15:
                score += config.scoring.fundamental_roe_weight
                reasons.append(f"ROE {roe*100:.0f}% — quality business")
            elif roe < 0.08:
                score -= 6
                reasons.append(f"ROE {roe*100:.0f}% — weak returns")

        if de is not None:
            if de <= 100:
                score += config.scoring.fundamental_debt_weight
                reasons.append(f"Debt/Equity {de/100:.2f} — manageable")
            else:
                score -= 8
                reasons.append(f"Debt/Equity {de/100:.2f} — high leverage")

        return score, reasons


class ScoringEngine:
    """Orchestrates all registered scorers."""

    def __init__(self, use_registry: bool = True):
        self._use_registry = use_registry
        self._default_scorers: list[ScoringStrategy] = [
            TrendScorer(),
            MomentumScorer(),
            VolumeScorer(),
            FundamentalScorer(),
        ]

    def total_score(
        self, last: pd.Series, prev: pd.Series | None, info: dict
    ) -> tuple[float, list[str]]:
        """Sum scores from all active scorers."""
        scorers = (
            registry.get_all_scorers()
            if self._use_registry and registry.get_all_scorers()
            else self._default_scorers
        )
        total = 0.0
        all_reasons: list[str] = []
        for scorer in scorers:
            s, r = scorer.score(last, prev, info)
            total += s
            all_reasons.extend(r)
        return total, all_reasons


# Auto-register defaults so plugins can override
for _scorer in [TrendScorer(), MomentumScorer(), VolumeScorer(), FundamentalScorer()]:
    registry.register_scorer(_scorer)
