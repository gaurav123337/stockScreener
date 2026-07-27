"""Recommendation engine.

Combines Trend + Momentum + Valuation + Quality into a score, then maps the
score to BUY / SELL / HOLD with an entry, target and stop-loss and a list of
human-readable reasons. Rules follow knowledge_graph/market_knowledge.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from .indicators import add_all


@dataclass
class Recommendation:
    symbol: str
    action: str                    # BUY / SELL / HOLD
    score: float                   # -100 .. +100
    price: float
    entry: Optional[float]
    target: Optional[float]
    stop_loss: Optional[float]
    risk_reward: Optional[float]
    reasons: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    error: Optional[str] = None


# ---- scoring helpers -------------------------------------------------------

def _score_trend(last: pd.Series, reasons: list) -> float:
    score = 0.0
    price = last["Close"]
    sma50, sma200 = last.get("SMA50"), last.get("SMA200")
    if pd.notna(sma50):
        if price > sma50:
            score += 15; reasons.append(f"Price above 50-DMA ({sma50:.1f}) — short-term uptrend")
        else:
            score -= 15; reasons.append(f"Price below 50-DMA ({sma50:.1f}) — short-term weakness")
    if pd.notna(sma200):
        if price > sma200:
            score += 20; reasons.append(f"Price above 200-DMA ({sma200:.1f}) — long-term uptrend")
        else:
            score -= 20; reasons.append(f"Price below 200-DMA ({sma200:.1f}) — long-term downtrend")
    if pd.notna(sma50) and pd.notna(sma200):
        if sma50 > sma200:
            score += 10; reasons.append("Golden-cross alignment (50-DMA > 200-DMA)")
        else:
            score -= 10; reasons.append("Death-cross alignment (50-DMA < 200-DMA)")
    return score


def _score_momentum(last: pd.Series, prev: pd.Series, reasons: list) -> float:
    score = 0.0
    r = last.get("RSI14")
    if pd.notna(r):
        if r >= 70:
            score -= 10; reasons.append(f"RSI {r:.0f} — overbought, pullback risk")
        elif r >= 55:
            score += 10; reasons.append(f"RSI {r:.0f} — healthy bullish momentum")
        elif r >= 45:
            reasons.append(f"RSI {r:.0f} — neutral")
        elif r >= 30:
            score -= 5; reasons.append(f"RSI {r:.0f} — weak momentum")
        else:
            score += 5; reasons.append(f"RSI {r:.0f} — oversold, possible bounce")
    macd, sig = last.get("MACD"), last.get("MACDsig")
    p_macd, p_sig = prev.get("MACD"), prev.get("MACDsig")
    if pd.notna(macd) and pd.notna(sig):
        if macd > sig:
            score += 10; reasons.append("MACD above signal — bullish momentum")
            if pd.notna(p_macd) and pd.notna(p_sig) and p_macd <= p_sig:
                score += 5; reasons.append("Fresh MACD bullish crossover")
        else:
            score -= 10; reasons.append("MACD below signal — bearish momentum")
            if pd.notna(p_macd) and pd.notna(p_sig) and p_macd >= p_sig:
                score -= 5; reasons.append("Fresh MACD bearish crossover")
    return score


def _score_volume(last: pd.Series, reasons: list) -> float:
    v, va = last.get("Volume"), last.get("VolAvg20")
    if pd.notna(v) and pd.notna(va) and va > 0:
        ratio = v / va
        if ratio >= 1.5:
            reasons.append(f"Volume {ratio:.1f}x 20-day avg — strong participation")
            return 5
    return 0.0


def _score_fundamentals(info: dict, reasons: list) -> float:
    if not info:
        return 0.0
    score = 0.0
    peg = info.get("pegRatio")
    pe = info.get("trailingPE")
    roe = info.get("returnOnEquity")
    de = info.get("debtToEquity")
    eg = info.get("earningsGrowth")
    if peg is not None:
        if peg < 1:
            score += 12; reasons.append(f"PEG {peg:.2f} < 1 — undervalued vs growth")
        elif peg > 2:
            score -= 12; reasons.append(f"PEG {peg:.2f} > 2 — expensive vs growth")
    elif pe is not None and eg is not None and eg > 0:
        implied = pe / (eg * 100)
        if implied < 1:
            score += 8; reasons.append(f"P/E {pe:.1f} low vs earnings growth {eg*100:.0f}%")
        elif implied > 2:
            score -= 8; reasons.append(f"P/E {pe:.1f} high vs earnings growth {eg*100:.0f}%")
    if roe is not None:
        if roe >= 0.15:
            score += 8; reasons.append(f"ROE {roe*100:.0f}% — quality business")
        elif roe < 0.08:
            score -= 6; reasons.append(f"ROE {roe*100:.0f}% — weak returns")
    if de is not None:
        if de <= 100:  # yfinance reports D/E as %
            score += 4; reasons.append(f"Debt/Equity {de/100:.2f} — manageable")
        else:
            score -= 8; reasons.append(f"Debt/Equity {de/100:.2f} — high leverage")
    return score


# ---- main entry ------------------------------------------------------------

def analyze(symbol: str, history: pd.DataFrame, info: dict | None = None) -> Recommendation:
    if history is None or history.empty or len(history) < 60:
        return Recommendation(symbol, "HOLD", 0, np.nan, None, None, None, None,
                              [], {}, error="insufficient price history")
    info = info or {}
    df = add_all(history)
    last, prev = df.iloc[-1], df.iloc[-2]
    price = float(last["Close"])

    reasons: list = []
    score = 0.0
    score += _score_trend(last, reasons)
    score += _score_momentum(last, prev, reasons)
    score += _score_volume(last, reasons)
    score += _score_fundamentals(info, reasons)
    score = float(max(-100, min(100, score)))

    if score >= 30:
        action = "BUY"
    elif score <= -30:
        action = "SELL"
    else:
        action = "HOLD"

    # Entry / target / stop-loss using ATR + 52w structure
    atr = float(last["ATR14"]) if pd.notna(last.get("ATR14")) else price * 0.03
    sma50 = float(last["SMA50"]) if pd.notna(last.get("SMA50")) else None
    high52 = float(last["High52"]) if pd.notna(last.get("High52")) else None
    low52 = float(last["Low52"]) if pd.notna(last.get("Low52")) else None

    entry = target = stop = None
    rr = None
    if action == "BUY":
        entry = round(price, 2)
        # stop below 50-DMA or 1.5*ATR, whichever is nearer but sensible
        candidates = [price - 1.5 * atr]
        if sma50:
            candidates.append(sma50 * 0.98)
        stop = round(max(candidates), 2)
        risk = price - stop
        tgt_candidates = [price + 2 * risk]
        if high52 and high52 > price:
            tgt_candidates.append(high52)
        target = round(min(tgt_candidates), 2)
        rr = round((target - price) / risk, 2) if risk > 0 else None
    elif action == "SELL":
        entry = round(price, 2)
        stop = round(price + 1.5 * atr, 2)
        tgt_candidates = [price - 2 * (stop - price)]
        if low52 and low52 < price:
            tgt_candidates.append(low52)
        target = round(max(tgt_candidates), 2)
        rr = round((price - target) / (stop - price), 2) if stop > price else None

    metrics = {
        "rsi": round(float(last["RSI14"]), 1) if pd.notna(last.get("RSI14")) else None,
        "sma50": round(sma50, 2) if sma50 else None,
        "sma200": round(float(last["SMA200"]), 2) if pd.notna(last.get("SMA200")) else None,
        "atr": round(atr, 2),
        "pe": info.get("trailingPE"),
        "peg": info.get("pegRatio"),
        "roe": info.get("returnOnEquity"),
        "debt_to_equity": info.get("debtToEquity"),
        "sector": info.get("sector"),
        "name": info.get("longName"),
    }
    return Recommendation(symbol, action, score, round(price, 2),
                          entry, target, stop, rr, reasons, metrics)
