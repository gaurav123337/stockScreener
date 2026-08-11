"""Alert Service — Chartink-style alerts for the retention loop (Phase 5).

Three rule types, all server-owned and persisted in SQLite:
  * price     — a symbol's live price crosses a level
  * screen_hit— a saved screen gains new matches (the Phase-4 engine)
  * mf_nav    — a mutual-fund scheme NAV crosses a level

Evaluation is bounded (watchlist-first, capped universe) and notification is
best-effort through an outbox, mirroring the sandbox billing gateway: a real
push/email adapter can be swapped in later without touching the callers.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from screener.core.container import container
from screener.core.responses import ValidationError
from screener.core.subscription_models import (
    AlertRule,
    AlertRuleType,
    SubscriptionStore,
    subscription_store,
)
from screener.core.user_models import UserProfile


class AlertService:
    """CRUD + evaluation for user alert rules."""

    def __init__(self, store: SubscriptionStore | None = None):
        self._store = store or subscription_store

    # ------------------------------------------------------------------- CRUD

    def create_rule(self, user: UserProfile, payload: dict[str, Any]) -> AlertRule:
        rule_type = AlertRuleType(payload["rule_type"])
        if rule_type == AlertRuleType.SCREEN_HIT and not payload.get("screen_id"):
            raise ValidationError("screen_hit alerts require a screen_id")
        if rule_type == AlertRuleType.PRICE and not payload.get("symbol"):
            raise ValidationError("price alerts require a symbol")
        if rule_type == AlertRuleType.MF_NAV and not payload.get("scheme_code"):
            raise ValidationError("mf_nav alerts require a scheme_code")
        if payload.get("direction") not in ("above", "below"):
            raise ValidationError("direction must be 'above' or 'below'")

        rule = AlertRule(
            alert_id=f"alr_{uuid4().hex[:12]}",
            user_id=user.user_id,
            rule_type=rule_type,
            name=payload.get("name") or self._default_name(payload),
            symbol=payload.get("symbol"),
            scheme_code=payload.get("scheme_code"),
            direction=payload.get("direction", "above"),
            trigger_value=float(payload["trigger_value"]),
            screen_id=payload.get("screen_id"),
            enabled=payload.get("enabled", True),
        )
        self._store.upsert_alert(rule)
        return rule

    def list_rules(self, user: UserProfile) -> list[AlertRule]:
        return self._store.list_alerts(user.user_id)

    def delete_rule(self, user: UserProfile, alert_id: str) -> bool:
        return self._store.delete_alert(alert_id, user.user_id)

    def reset_rule(self, user: UserProfile, alert_id: str) -> bool:
        return self._store.reset_alert(alert_id, user.user_id)

    @staticmethod
    def _default_name(payload: dict[str, Any]) -> str:
        target = payload.get("symbol") or payload.get("scheme_code") or "item"
        return f"{target} {payload.get('direction', 'above')} {payload.get('trigger_value')}"

    # ---------------------------------------------------------------- evaluate

    def evaluate_user_alerts(self, user: UserProfile, symbols: list[str] | None = None) -> list[dict[str, Any]]:
        """Run all of a user's enabled rules and report fired notifications.

        ``symbols`` bounds the universe (watchlist-first, capped). Each fired
        rule is a one-shot: it re-arms only when the user resets it, so the
        user is not spammed on every evaluation cycle.
        """
        fired: list[dict[str, Any]] = []
        rules = [r for r in self._store.list_alerts(user.user_id) if r.enabled]
        for rule in rules:
            event = self._evaluate_one(user, rule, symbols)
            if event:
                fired.append(event)
        return fired

    def _evaluate_one(
        self, user: UserProfile, rule: AlertRule, symbols: list[str] | None
    ) -> dict[str, Any] | None:
        try:
            if rule.rule_type == AlertRuleType.PRICE:
                value = self._fetch_price(rule.symbol or "")
                fired = rule.fired(value)
                event_kind = "price"
            elif rule.rule_type == AlertRuleType.MF_NAV:
                value = self._fetch_nav(rule.scheme_code or "")
                fired = rule.fired(value)
                event_kind = "mf_nav"
            elif rule.rule_type == AlertRuleType.SCREEN_HIT:
                value = float(self._screen_new_matches(user, rule))
                fired = rule.fired(value)
                event_kind = "screen_hit"
            else:
                return None
        except Exception:
            return None

        if not fired:
            return None

        self._store.mark_alert_fired(rule.alert_id, value)
        self._dispatch(user, rule, event_kind, value)
        return {
            "alert_id": rule.alert_id,
            "rule_type": rule.rule_type.value,
            "name": rule.name,
            "symbol": rule.symbol,
            "scheme_code": rule.scheme_code,
            "value": value,
            "trigger_value": rule.trigger_value,
            "direction": rule.direction,
            "fired_at": datetime.utcnow().isoformat(),
        }

    # --------------------------------------------------------------- sourcing

    def _fetch_price(self, symbol: str) -> float:
        from screener.core.interfaces import MarketDataProvider
        from screener.services.evaluation import asof_close

        provider = container.resolve(MarketDataProvider)
        frame = provider.fetch_history(symbol, period="5d")
        price = asof_close(frame)
        if price is None or price <= 0:
            raise ValueError(f"no live price for {symbol}")
        return float(price)

    def _fetch_nav(self, scheme_code: str) -> float:
        from screener.core.interfaces import MarketDataProvider
        from screener.services.evaluation import asof_close

        provider = container.resolve(MarketDataProvider)
        frame = provider.fetch_history(scheme_code, period="5d")
        price = asof_close(frame)
        if price is None or price <= 0:
            # NAV schemes are not index symbols; fall back to a stored lookup.
            nav = self._lookup_nav(scheme_code)
            if nav is None:
                raise ValueError(f"no NAV for {scheme_code}")
            return float(nav)
        return float(price)

    def _lookup_nav(self, scheme_code: str) -> float | None:
        from screener.services.mutual_fund_service import MutualFundService

        try:
            service = container.resolve(MutualFundService)
            detail = service.detail(int(scheme_code))
            nav = detail.scheme.nav
            if nav is None and detail.history:
                nav = detail.history[-1].get("nav")
            return float(nav) if nav else None
        except Exception:
            return None

    def _screen_new_matches(self, user: UserProfile, rule: AlertRule) -> int:
        """Re-run the saved screen and return the number of fresh matches."""
        from screener.services.subscription_service import SubscriptionService

        if not rule.screen_id:
            return 0
        service = container.resolve(SubscriptionService)
        evaluation = service.evaluate_screen(user, rule.screen_id)
        return int(evaluation.get("new_matches", 0))

    # ---------------------------------------------------------------- dispatch

    def _dispatch(self, user: UserProfile, rule: AlertRule, kind: str, value: float) -> None:
        """Best-effort notification through the outbox (no live push in preview).

        A real provider (web-push or email) can replace this later; the outbox
        record is the contract the delivery layer consumes.
        """
        try:
            path = Path(os.getenv("SCREENER_ALERTS_OUTBOX", "data/alert_outbox.jsonl"))
            path.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "user_id": user.user_id,
                "purpose": "alert",
                "rule_type": kind,
                "alert_id": rule.alert_id,
                "name": rule.name,
                "symbol": rule.symbol,
                "scheme_code": rule.scheme_code,
                "value": value,
                "trigger_value": rule.trigger_value,
                "created_at": datetime.utcnow().isoformat(),
            }
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record) + "\n")
        except Exception:
            pass


# Global instance
alert_service = AlertService()
