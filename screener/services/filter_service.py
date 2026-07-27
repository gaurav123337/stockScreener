"""Filter Service — plugin-based filter registry with safe custom expressions."""
from __future__ import annotations

import ast
import operator as op
from typing import Callable

from screener.core.interfaces import FilterStrategy
from screener.core.plugins import registry


class PredefinedFilter(FilterStrategy):
    """A named filter with a description and predicate."""

    def __init__(self, name: str, description: str, predicate: Callable[[dict], bool]):
        self._name = name
        self._description = description
        self._predicate = predicate

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    def matches(self, row: dict) -> bool:
        return self._predicate(row)


class ExpressionFilter(FilterStrategy):
    """Safe custom expression filter using AST parsing."""

    _OPS = {
        ast.Lt: op.lt, ast.LtE: op.le, ast.Gt: op.gt, ast.GtE: op.ge,
        ast.Eq: op.eq, ast.NotEq: op.ne,
    }
    _BOOL = {ast.And: all, ast.Or: any}

    def __init__(self, expression: str):
        self._expression = expression
        self._tree = ast.parse(expression, mode="eval")

    @property
    def name(self) -> str:
        return f"custom:{self._expression}"

    @property
    def description(self) -> str:
        return f"Custom expression: {self._expression}"

    def matches(self, row: dict) -> bool:
        try:
            return bool(self._eval(self._tree.body, row))
        except Exception:
            return False

    def _eval(self, node, row: dict):
        if isinstance(node, ast.BoolOp):
            return self._BOOL[type(node.op)](self._eval(v, row) for v in node.values)
        if isinstance(node, ast.Compare):
            left = self._eval(node.left, row)
            for oper, comp in zip(node.ops, node.comparators):
                right = self._eval(comp, row)
                if type(oper) not in self._OPS:
                    raise ValueError("operator not allowed")
                if left is None or right is None:
                    return False
                if not self._OPS[type(oper)](left, right):
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
            return -self._eval(node.operand, row)
        raise ValueError(f"expression element not allowed: {type(node).__name__}")


class FilterService:
    """Manages predefined and custom filters."""

    def __init__(self):
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register built-in filters."""
        defaults = [
            ("oversold", "RSI < 30 - possibly oversold bounce candidates",
             lambda r: r.get("rsi") is not None and r["rsi"] < 30),
            ("uptrend", "Price above 50 & 200 DMA with golden cross - strong uptrend",
             lambda r: bool(r.get("above_sma50")) and bool(r.get("above_sma200")) and bool(r.get("golden_cross"))),
            ("value", "PEG < 1 (or low P/E vs growth) - undervalued vs growth",
             lambda r: (r.get("peg") is not None and r["peg"] < 1)),
            ("quality", "ROE > 15% and Debt/Equity < 1 - quality businesses",
             lambda r: (r.get("roe") is not None and r["roe"] > 0.15)
             and (r.get("debt_to_equity") is None or r["debt_to_equity"] < 100)),
            ("momentum", "Score >= 30 and RSI 55-70 - strong momentum buys",
             lambda r: r.get("score") is not None and r["score"] >= 30
             and r.get("rsi") is not None and 55 <= r["rsi"] < 70),
            ("near_52w_high", "Within 5% of 52-week high - breakout watch",
             lambda r: bool(r.get("near_52w_high"))),
            ("near_52w_low", "Within 5% of 52-week low - deep value / knife catch",
             lambda r: bool(r.get("near_52w_low"))),
            ("buy_signals", "Current action == BUY",
             lambda r: r.get("action") == "BUY"),
            ("sell_signals", "Current action == SELL",
             lambda r: r.get("action") == "SELL"),
        ]
        for name, desc, predicate in defaults:
            registry.register_filter(PredefinedFilter(name, desc, predicate))

    def get_filter(self, name: str) -> FilterStrategy | None:
        return registry.get_filter(name)

    def compile_custom(self, expression: str) -> FilterStrategy:
        return ExpressionFilter(expression)

    def list_filters(self) -> list[dict[str, str]]:
        return registry.list_filters()

    def get_filter_fields(self) -> list[str]:
        """Fields available for custom expressions."""
        return [
            "score", "price", "rsi", "pe", "peg", "roe", "debt_to_equity",
            "sma50", "sma200", "above_sma50", "above_sma200",
            "golden_cross", "near_52w_high", "near_52w_low",
        ]
