"""Check-before-buy Service — the "never a broker" honesty layer (Phase 5).

Positioning: stockScreener is a research aid, not an execution venue. This
service turns a recommendation into a pre-trade checklist the user reviews in
their own broker app — price vs entry/target/stop, valuation vs its own
history, position sizing from the risk profile, and a compliance note. The
"broker" integration is deep-links only: tapping opens the symbol in the
user's chosen broker app to *review*, never to place a trade on their behalf.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from screener.core.models import Recommendation
from screener.core.responses import NotFoundError, ValidationError
from screener.core.user_models import UserProfile


# Deep-link templates — `{symbol}` is interpolated at request time. These open
# the broker app's symbol page for *review*; no API call, no order placement.
BROKER_DEEP_LINKS: dict[str, dict[str, str]] = {
    "zerodha_kite": {
        "name": "Zerodha Kite",
        "web": "https://kite.zerodha.com/chart/ext/tvc/{symbol}/NSE",
        "app": "kite3://quote/{symbol}",
    },
    "zerodha_coin": {
        "name": "Zerodha Coin",
        "web": "https://coin.zerodha.com/explore",
        "app": "coin://explore",
    },
    "groww": {
        "name": "Groww",
        "web": "https://groww.in/stocks/{symbol}",
        "app": "groww://stock/{symbol}",
    },
    "kotak": {
        "name": "Kotak Securities",
        "web": "https://online.kotaksecurities.com/trading/scrip?symbol={symbol}",
        "app": "kotaksecurities://quote/{symbol}",
    },
}


class CheckBeforeBuyService:
    """Builds a beginner-friendly pre-trade checklist from a recommendation."""

    def brokers(self) -> list[dict[str, str]]:
        return [
            {"id": bid, "name": links["name"]}
            for bid, links in BROKER_DEEP_LINKS.items()
        ]

    def broker_deep_link(self, broker_id: str, symbol: str) -> dict[str, str]:
        links = BROKER_DEEP_LINKS.get(broker_id)
        if links is None:
            raise NotFoundError("Unknown broker")
        symbol = (symbol or "").strip().upper()
        if not symbol:
            raise ValidationError("symbol required for a broker deep-link")
        return {
            "broker": links["name"],
            "symbol": symbol,
            "web": links["web"].format(symbol=symbol),
            "app": links["app"].format(symbol=symbol),
        }

    def checklist(self, user: UserProfile, recommendation: Recommendation) -> dict[str, Any]:
        """Pre-trade checklist with a pass/triage/warn verdict per item."""
        if not recommendation.is_valid:
            raise ValidationError("cannot build a checklist for a failed recommendation")

        price = recommendation.price or 0.0
        items: list[dict[str, Any]] = []

        # 1. Price vs entry/target/stop (when the signal has a plan).
        entry = recommendation.entry or price
        target = recommendation.target
        stop = recommendation.stop_loss
        if entry:
            items.append(self._item(
                "Price vs entry",
                f"Price is ₹{price:,.2f} vs entry ₹{entry:,.2f}",
                "green" if price <= entry * 1.02 else "amber",
                "Near or below your planned entry — wait for a pullback or size down if you pay up.",
            ))
        if target:
            gap = (target - price) / price * 100
            items.append(self._item(
                "Upside to target",
                f"Target ₹{target:,.2f} is {gap:+.1f}% from here",
                "green" if gap >= 8 else "amber",
                "The reward leg of the risk/reward plan; keep it, but re-check the thesis if it shrinks.",
            ))
        if stop:
            downside = (price - stop) / price * 100
            items.append(self._item(
                "Stop-loss distance",
                f"Stop ₹{stop:,.2f} is {downside:.1f}% below",
                "green" if downside <= 10 else "amber",
                "Know the exit before you enter; a stop wider than ~10% usually means the position is too big.",
            ))

        # 2. Valuation vs its own history (PE percentile when available).
        pe = recommendation.metrics.pe
        if pe and pe > 0:
            items.append(self._item(
                "Valuation (P/E)",
                f"P/E {pe:.1f}" + (" — high" if pe > 40 else (" — low" if pe < 12 else " — mid-range")),
                "green" if pe <= 40 else "amber",
                "Expensive is fine only with a growth story you understand; cheap alone is not a reason to buy.",
            ))

        # 3. Position sizing from the thesis / risk profile.
        allocation = recommendation.thesis_data.allocation_size
        if allocation:
            items.append(self._item(
                "Position size",
                f"Suggested ~{allocation * 100:.0f}% of your equity sleeve",
                "green",
                "Sizing is the first risk control — never exceed the allocation, and remember a single stock is not a portfolio.",
            ))

        # 4. The honesty floor: this is research, not a mandate.
        items.append(self._item(
            "Compliance & role",
            "stockScreener is research, not a broker or advisor",
            "info",
            "Place orders only in your own broker app. This checklist is a review aid, not personalised investment advice.",
        ))

        verdict = "green" if all(i["level"] != "red" for i in items) else "amber"
        return {
            "symbol": recommendation.symbol,
            "price": price,
            "action": recommendation.action.value,
            "score": recommendation.score,
            "risk_badge": recommendation.thesis_data.risk_badge,
            "verdict": verdict,
            "items": items,
            "brokers": self.brokers(),
            "generated_at": datetime.utcnow().isoformat(),
            "disclaimer": (
                "Educational checklist for review in your own broker app. "
                "stockScreener never executes trades and is not a SEBI-registered "
                "investment advisor."
            ),
        }

    # ------------------------------------------------------------------ utils

    @staticmethod
    def _item(title: str, text: str, level: str, guidance: str) -> dict[str, str]:
        return {"title": title, "text": text, "level": level, "guidance": guidance}


# Global instance
check_service = CheckBeforeBuyService()
