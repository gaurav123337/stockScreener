"""Backward-compatible shim — indicators moved to screener.core.indicators.

This module re-exports everything so existing imports don't break.
Prefer importing from screener.core.indicators directly.
"""
from screener.core.indicators import *  # noqa: F401,F403
from screener.core.indicators import add_all, atr, ema, macd, rsi, sma  # noqa: F401
