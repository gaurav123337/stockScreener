"""Pre-defined and custom filters for screening.

A filter is a named predicate over the per-stock scan row. Custom filters use a
safe mini expression language, e.g.:
    rsi < 30 and pe > 0 and roe > 0.15
Available fields: score, price, rsi, pe, peg, roe, debt_to_equity, sma50,
sma200, atr, above_sma50, above_sma200, golden_cross, near_52w_high, near_52w_low
"""
from __future__ import annotations

import ast
import operator as op
from typing import Callable

# ----- safe expression evaluation ------------------------------------------
_OPS = {
    ast.Lt: op.lt, ast.LtE: op.le, ast.Gt: op.gt, ast.GtE: op.ge,
    ast.Eq: op.eq, ast.NotEq: op.ne,
}
_BOOL = {ast.And: all, ast.Or: any}


def _eval(node, row: dict):
    if isinstance(node, ast.BoolOp):
        return _BOOL[type(node.op)](_eval(v, row) for v in node.values)
    if isinstance(node, ast.Compare):
        left = _eval(node.left, row)
        for oper, comp in zip(node.ops, node.comparators):
            right = _eval(comp, row)
            if type(oper) not in _OPS:
                raise ValueError("operator not allowed")
            if left is None or right is None:
                return False
            if not _OPS[type(oper)](left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.Name):
        if node.id not in row:
            raise ValueError(f"unknown field '{node.id}'")
        return row[node.id]
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, bool)):
            return node.value
        raise ValueError("only numeric constants allowed")
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval(node.operand, row)
    raise ValueError(f"expression element not allowed: {type(node).__name__}")


def compile_custom(expression: str) -> Callable[[dict], bool]:
    tree = ast.parse(expression, mode="eval")

    def predicate(row: dict) -> bool:
        try:
            return bool(_eval(tree.body, row))
        except Exception:
            return False
    return predicate


# ----- pre-defined filters ---------------------------------------------------
# Each takes the scan row dict -> bool
PREDEFINED: dict[str, tuple[str, Callable[[dict], bool]]] = {
    "oversold": (
        "RSI < 30 - possibly oversold bounce candidates",
        lambda r: r.get("rsi") is not None and r["rsi"] < 30,
    ),
    "uptrend": (
        "Price above 50 & 200 DMA with golden cross - strong uptrend",
        lambda r: bool(r.get("above_sma50")) and bool(r.get("above_sma200")) and bool(r.get("golden_cross")),
    ),
    "value": (
        "PEG < 1 (or low P/E vs growth) - undervalued vs growth",
        lambda r: (r.get("peg") is not None and r["peg"] < 1),
    ),
    "quality": (
        "ROE > 15% and Debt/Equity < 1 - quality businesses",
        lambda r: (r.get("roe") is not None and r["roe"] > 0.15)
        and (r.get("debt_to_equity") is None or r["debt_to_equity"] < 100),
    ),
    "momentum": (
        "Score >= 30 and RSI 55-70 - strong momentum buys",
        lambda r: r.get("score") is not None and r["score"] >= 30
        and r.get("rsi") is not None and 55 <= r["rsi"] < 70,
    ),
    "near_52w_high": (
        "Within 5% of 52-week high - breakout watch",
        lambda r: bool(r.get("near_52w_high")),
    ),
    "near_52w_low": (
        "Within 5% of 52-week low - deep value / knife catch",
        lambda r: bool(r.get("near_52w_low")),
    ),
    "buy_signals": (
        "Current action == BUY",
        lambda r: r.get("action") == "BUY",
    ),
    "sell_signals": (
        "Current action == SELL",
        lambda r: r.get("action") == "SELL",
    ),
}


def list_predefined() -> list[tuple[str, str]]:
    return [(name, desc) for name, (desc, _) in PREDEFINED.items()]


def get_predefined(name: str) -> Callable[[dict], bool]:
    return PREDEFINED[name][1]
