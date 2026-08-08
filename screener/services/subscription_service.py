"""Subscription Service — plans, checkout, entitlements, admin grant/revoke.

Phase 4 freemium model. Entitlements are always computed server-side from the
user's persisted tier + subscription record; the frontend only renders what the
server says. A churn-safe free tier keeps every core screen working; Pro unlocks
gated features behind the ``require_pro`` API dependency.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from screener.core.config import config
from screener.core.container import container
from screener.core.responses import (
    ErrorCodes,
    NotFoundError,
    PaymentError,
    ProRequiredError,
    ValidationError,
)
from screener.core.subscription_models import (
    AlertEvaluation,
    BillingPlan,
    CheckoutSession,
    Entitlements,
    SavedScreen,
    Subscription,
    SubscriptionStatus,
    Tier,
    subscription_store,
)
from screener.core.user_models import UserProfile, UserStore, user_store
from screener.infrastructure.payments import build_payment_gateway

# Feature keys used by entitlements.features and the API gate.
FEATURE_SAVED_SCREENS = "saved_screens"
FEATURE_EMAIL_ALERTS = "email_alerts"
FEATURE_PORTFOLIO_ANALYTICS = "portfolio_analytics"
FEATURE_STRATEGY_BACKTESTS = "strategy_backtests"
FEATURE_PLAN_REVIEW = "plan_review"

FREE_FEATURES: dict[str, bool] = {
    FEATURE_SAVED_SCREENS: True,  # free tier gets 1 saved screen (churn-safe)
    FEATURE_EMAIL_ALERTS: False,
    FEATURE_PORTFOLIO_ANALYTICS: False,
    FEATURE_STRATEGY_BACKTESTS: False,
    FEATURE_PLAN_REVIEW: False,
}

# Upper bound on symbols evaluated per alert run (watchlist is preferred).
ALERT_UNIVERSE_CAP = 50

PRO_FEATURES: dict[str, bool] = {key: True for key in FREE_FEATURES}


class SubscriptionService:
    """Billing + entitlement operations for the freemium model."""

    def __init__(
        self,
        store: SubscriptionStore | None = None,
        user_db: UserStore | None = None,
        gateway: Any = None,
    ):
        from screener.core.subscription_models import subscription_store as default_store

        self._store = store or default_store
        self._user_db = user_db or user_store
        self._gateway = gateway or build_payment_gateway(config.billing.gateway)

    # ------------------------------------------------------------------ #
    # Plans & pricing
    # ------------------------------------------------------------------ #

    def plans(self) -> list[dict[str, Any]]:
        """The purchasable plans (Pro monthly / Pro yearly)."""
        return [
            {
                "id": "pro_monthly",
                "name": "Pro",
                "interval": "month",
                "price_inr": config.billing.pro_monthly_inr,
                "price_usd": config.billing.pro_monthly_usd,
                "currency": "INR",
                "description": "Everything in Free, plus deep research tools.",
                "features": [
                    "Advanced per-strategy backtests",
                    "Saved screens with email alerts",
                    "Portfolio & watchlist analytics",
                    "Rebalancing alerts + quarterly review report",
                    "Same compliance posture as Free",
                ],
                "highlighted": False,
            },
            {
                "id": "pro_yearly",
                "name": "Pro Yearly",
                "interval": "year",
                "price_inr": config.billing.pro_yearly_inr,
                "price_usd": config.billing.pro_yearly_usd,
                "currency": "INR",
                "description": "Best value — two months free vs monthly.",
                "features": [
                    "Everything in Pro monthly",
                    "2 months free vs monthly billing",
                    f"{config.billing.trial_days}-day free trial",
                ],
                "highlighted": True,
                "trial_days": config.billing.trial_days,
            },
        ]

    def get_plan(self, plan_id: str) -> BillingPlan:
        for plan in self.plans():
            if plan["id"] == plan_id:
                return BillingPlan(**plan)
        raise ValidationError(f"Unknown plan '{plan_id}'", details={"plan_id": plan_id})

    # ------------------------------------------------------------------ #
    # Entitlements
    # ------------------------------------------------------------------ #

    def entitlements(self, user: UserProfile) -> Entitlements:
        """The effective entitlements for a user (server-authoritative)."""
        sub = self._store.get_subscription(user.user_id)
        is_pro = user.tier == Tier.PRO.value or bool(sub and sub.is_active)
        if is_pro and sub is not None and not sub.is_active and user.tier == Tier.PRO.value:
            # Expired subscription with a stale tier flag -> downgrade safely.
            is_pro = False
        tier = Tier.PRO if is_pro else Tier.FREE
        return Entitlements(
            tier=tier,
            is_pro=is_pro,
            plan_id=sub.plan_id if sub else None,
            status=sub.status if sub else SubscriptionStatus.NONE,
            renews_at=sub.renews_at if sub else None,
            features={**PRO_FEATURES} if is_pro else {**FREE_FEATURES},
            limits={
                "saved_screens": (
                    config.billing.pro_saved_screens
                    if is_pro
                    else config.billing.free_saved_screens
                ),
            },
        )

    def require_pro(self, user: UserProfile, feature: str = "") -> Entitlements:
        """Raise ProRequiredError unless the user is on Pro."""
        entitlements = self.entitlements(user)
        if not entitlements.is_pro:
            raise ProRequiredError(feature=feature)
        return entitlements

    # ------------------------------------------------------------------ #
    # Checkout (server-owned sessions)
    # ------------------------------------------------------------------ #

    def create_checkout(self, user: UserProfile, plan_id: str) -> dict[str, Any]:
        """Open a checkout session for a plan. Session is unpaid until confirm."""
        plan = self.get_plan(plan_id)
        session = self._gateway.create_session(user.user_id, plan)
        self._store.create_checkout(
            session_id=session.session_id,
            user_id=user.user_id,
            plan_id=plan.id,
            gateway=self._gateway.name,
            amount_inr=session.amount_inr,
        )
        return session.model_dump(mode="json")

    def confirm_checkout(self, user: UserProfile, session_id: str) -> dict[str, Any]:
        """Settle a checkout session. Grants Pro once the gateway marks paid."""
        stored = self._store.get_checkout(session_id)
        if stored is None:
            raise NotFoundError("Checkout session not found")
        if stored["user_id"] != user.user_id:
            raise NotFoundError("Checkout session not found")

        plan = self.get_plan(stored["plan_id"])
        session = CheckoutSession(**{
            "session_id": stored["session_id"],
            "plan_id": stored["plan_id"],
            "status": stored["status"],
            "gateway": stored["gateway"] or self._gateway.name,
            "amount_inr": stored["amount_inr"],
            "expires_at": datetime.utcnow() + timedelta(minutes=30),
        })
        settled = self._gateway.confirm_session(session)
        if settled.status != "paid":
            raise PaymentError(message="Payment was not completed. Please try again.")

        self._store.mark_checkout_paid(session_id)

        now = datetime.utcnow()
        interval = plan.interval
        renews_at = now + timedelta(days=365 if interval == "year" else 31)
        status = SubscriptionStatus.ACTIVE

        sub = Subscription(
            user_id=user.user_id,
            plan_id=plan.id,
            status=status,
            started_at=now,
            renews_at=renews_at,
            payment_gateway=self._gateway.name,
            last_payment_id=session_id,
        )
        self._store.upsert_subscription(sub)
        self._user_db.update_account(user.user_id, tier=Tier.PRO.value)
        self._capture_receipt(user, plan, session_id, amount=plan.price_inr)

        return {
            "status": "paid",
            "tier": Tier.PRO.value,
            "plan_id": plan.id,
            "renews_at": renews_at.isoformat(),
            "message": "Welcome to Pro!",
        }

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def current_subscription(self, user: UserProfile) -> dict[str, Any]:
        sub = self._store.get_subscription(user.user_id)
        return {
            "tier": user.tier,
            "plan_id": sub.plan_id if sub else None,
            "status": sub.status.value if sub else SubscriptionStatus.NONE.value,
            "started_at": sub.started_at.isoformat() if sub and sub.started_at else None,
            "renews_at": sub.renews_at.isoformat() if sub and sub.renews_at else None,
            "canceled_at": sub.canceled_at.isoformat() if sub and sub.canceled_at else None,
            "is_active": bool(sub and sub.is_active),
            "gateway": self._gateway.name,
        }

    def cancel_subscription(self, user: UserProfile) -> dict[str, Any]:
        """Cancel at renewal: Pro keeps working until renews_at."""
        sub = self._store.get_subscription(user.user_id)
        if not sub or not sub.is_active:
            raise ValidationError("You do not have an active subscription")
        sub = sub.model_copy(update={
            "status": SubscriptionStatus.CANCELED,
            "canceled_at": datetime.utcnow(),
        })
        self._store.upsert_subscription(sub)
        return self.current_subscription(user)

    # ------------------------------------------------------------------ #
    # Admin grant / revoke
    # ------------------------------------------------------------------ #

    def admin_grant_pro(self, user_id: str, days: int = 365) -> dict[str, Any]:
        """Product-owner grant (trial / comped access). Direct, no gateway."""
        user = self._user_db.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        now = datetime.utcnow()
        sub = Subscription(
            user_id=user_id,
            plan_id="pro_yearly",
            status=SubscriptionStatus.ACTIVE,
            started_at=now,
            renews_at=now + timedelta(days=days),
            payment_gateway="admin",
        )
        self._store.upsert_subscription(sub)
        self._user_db.update_account(user_id, tier=Tier.PRO.value)
        return {"user_id": user_id, "tier": Tier.PRO.value, "renews_at": sub.renews_at.isoformat()}

    def admin_revoke_pro(self, user_id: str) -> dict[str, Any]:
        """Product-owner revoke. Downgrades to free immediately."""
        user = self._user_db.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        sub = Subscription(
            user_id=user_id,
            status=SubscriptionStatus.EXPIRED,
            canceled_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self._store.upsert_subscription(sub)
        self._user_db.update_account(user_id, tier=Tier.FREE.value)
        return {"user_id": user_id, "tier": Tier.FREE.value}

    def admin_set_tier(self, user_id: str, tier: str) -> dict[str, Any]:
        """Generic admin tier set (used by the control-center API)."""
        if tier not in (Tier.FREE.value, Tier.PRO.value):
            raise ValidationError("tier must be 'free' or 'pro'")
        if tier == Tier.PRO.value:
            return self.admin_grant_pro(user_id)
        return self.admin_revoke_pro(user_id)

    # ------------------------------------------------------------------ #
    # Receipt outbox (dev delivery adapter; production ships to the provider)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _capture_receipt(user: UserProfile, plan: BillingPlan, session_id: str, amount: float) -> None:
        path = Path(os.getenv("SCREENER_BILLING_OUTBOX", "data/billing_outbox.jsonl"))
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "to": user.email or user.username,
            "purpose": "payment_receipt",
            "session_id": session_id,
            "plan_id": plan.id,
            "amount_inr": amount,
            "created_at": datetime.utcnow().isoformat(),
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

    # ------------------------------------------------------------------ #
    # Saved screens (Pro: unlimited; Free: churn-safe single screen)
    # ------------------------------------------------------------------ #

    def list_screens(self, user: UserProfile) -> list[dict[str, Any]]:
        return [s.model_dump(mode="json") for s in self._store.list_screens(user.user_id)]

    def save_screen(
        self,
        user: UserProfile,
        name: str,
        filter_expr: str = "",
        sort_by: str = "score",
        sort_dir: str = "desc",
        limit: int = 50,
        alert_enabled: bool = False,
        alert_email: str | None = None,
        screen_id: str | None = None,
    ) -> dict[str, Any]:
        if not name or not name.strip():
            raise ValidationError("name is required")
        limit = max(1, min(int(limit or 50), 500))

        # Validate the filter expression *before* persisting so users only save
        # screens that will actually run (matches the /api/scan contract).
        if filter_expr:
            try:
                from screener.services import FilterService

                container.resolve(FilterService).compile_custom(filter_expr)
            except KeyError:
                pass  # Offline unit tests without a bootstrapped container
            except Exception as e:
                raise ValidationError(f"Invalid filter expression: {e}")

        existing = self._store.get_screen(screen_id) if screen_id else None
        if existing is None or existing.user_id != user.user_id:
            screen_id = None
        entitlements = self.entitlements(user)
        if alert_enabled and not entitlements.allows(FEATURE_EMAIL_ALERTS):
            raise ProRequiredError(feature=FEATURE_EMAIL_ALERTS)
        if alert_enabled and not alert_email:
            raise ValidationError("alert_email is required when alert_enabled")

        if screen_id is None:
            count = self._store.count_screens(user.user_id)
            if count >= entitlements.limits.get("saved_screens", 1):
                raise ProRequiredError(
                    feature=FEATURE_SAVED_SCREENS,
                    message=(
                        "Saved-screen limit reached. Free users get "
                        f"{entitlements.limits.get('saved_screens', 1)}; upgrade to Pro "
                        "for unlimited screens and email alerts."
                    ),
                )

        now = datetime.utcnow()
        screen = SavedScreen(
            screen_id=screen_id or f"scr_{uuid.uuid4().hex[:12]}",
            user_id=user.user_id,
            name=name.strip(),
            filter_expr=filter_expr,
            sort_by=sort_by or "score",
            sort_dir=sort_dir or "desc",
            limit=limit,
            alert_enabled=alert_enabled,
            alert_email=alert_email if alert_enabled else None,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        saved = self._store.save_screen(screen)
        return saved.model_dump(mode="json")

    def delete_screen(self, user: UserProfile, screen_id: str) -> dict[str, Any]:
        if not self._store.delete_screen(screen_id, user.user_id):
            raise NotFoundError("Saved screen not found")
        return {"deleted": True, "screen_id": screen_id}

    def evaluate_screen(self, user: UserProfile, screen_id: str, limit: int = 20) -> dict[str, Any]:
        """Run a saved screen against the live universe and dispatch an alert.

        Pro feature (email alerts). Evaluation is synchronous and offline: it
        reuses the exact /api/scan engine, so the match set is identical to what
        the user would see in the UI.
        """
        entitlements = self.require_pro(user, feature=FEATURE_EMAIL_ALERTS)
        screen = self._store.get_screen(screen_id)
        if screen is None or screen.user_id != user.user_id:
            raise NotFoundError("Saved screen not found")

        from screener.services import FilterService, PreferencesService, ScanService

        prefs = container.resolve(PreferencesService)
        effective_config = prefs.get_effective_config(user.user_id)
        symbols = prefs.get_watchlist(user.user_id) or effective_config.default_universe
        # Alert evaluation stays bounded so a single screen can't fan out to the
        # full 500-symbol universe (and hammer the data provider). Prefer the
        # user's watchlist; fall back to a fixed slice of the universe.
        if len(symbols) > ALERT_UNIVERSE_CAP:
            symbols = symbols[:ALERT_UNIVERSE_CAP]

        predicate = None
        if screen.filter_expr:
            expr = container.resolve(FilterService).compile_custom(screen.filter_expr)
            predicate = expr.matches

        result = container.resolve(ScanService).scan(
            symbols, predicate, screen.limit, app_config=effective_config
        )
        matched = [r.to_scan_row() for r in result.matched]

        previous_count = screen.last_match_count
        new_matches = max(0, len(matched) - previous_count)
        email_sent = False
        if matched and screen.alert_enabled:
            email_sent = self._dispatch_alert(screen, matched, new_matches)

        self._store.touch_screen_alert(screen_id, len(matched), email_sent)
        return AlertEvaluation(
            screen=screen.model_copy(
                update={"last_match_count": len(matched)}
            ),
            matched=matched[:limit],
            new_matches=new_matches,
            email_sent=email_sent,
        ).model_dump(mode="json")

    def _dispatch_alert(self, screen: SavedScreen, matched: list[dict], new_matches: int) -> bool:
        """Write a dev-delivery alert record (no real email infra in preview)."""
        try:
            path = Path(os.getenv("SCREENER_ALERTS_OUTBOX", "data/alert_outbox.jsonl"))
            path.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "to": screen.alert_email,
                "purpose": "screen_alert",
                "screen_id": screen.screen_id,
                "screen_name": screen.name,
                "new_matches": new_matches,
                "total_matches": len(matched),
                "symbols": [m.get("symbol") for m in matched][:20],
                "created_at": datetime.utcnow().isoformat(),
            }
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record) + "\n")
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    # Portfolio analytics (Pro)
    # ------------------------------------------------------------------ #

    def portfolio_analytics(
        self, user: UserProfile, holdings: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Aggregate analytics for a user-declared holding list.

        Pro feature. Computes sector exposure, valuation mix, dividend yield
        estimate, concentration (Herfindahl), and per-holding quality scores
        from the same signal engine used everywhere else in the product.
        """
        self.require_pro(user, feature=FEATURE_PORTFOLIO_ANALYTICS)
        if not holdings:
            raise ValidationError("holdings must not be empty")

        from screener.services import AnalysisService

        analysis = container.resolve(AnalysisService)
        enriched: list[dict[str, Any]] = []
        sector_values: dict[str, float] = {}
        total_value = 0.0
        total_cost = 0.0
        total_yield = 0.0
        score_sum = 0.0
        count = 0

        for holding in holdings:
            symbol = (holding.get("symbol") or "").strip()
            qty = float(holding.get("quantity") or 0)
            cost = float(holding.get("avg_cost") or holding.get("buy_price") or 0)
            if not symbol or qty <= 0:
                continue
            try:
                rec = analysis.analyze(symbol)
            except Exception:
                continue
            if rec.error or rec.price is None:
                continue
            row = rec.to_scan_row()
            value = float(rec.price or 0) * qty
            sector = str(row.get("sector") or "Unknown")
            total_value += value
            total_cost += cost * qty
            total_yield += float(row.get("dividend_yield") or 0) * value
            score_sum += float(rec.score or 0)
            count += 1
            sector_values[sector] = sector_values.get(sector, 0.0) + value
            enriched.append({
                "symbol": symbol,
                "name": row.get("name"),
                "sector": sector,
                "price": rec.price,
                "score": rec.score,
                "action": row.get("action"),
                "risk_badge": row.get("risk_badge"),
                "pe": row.get("pe"),
                "roe": row.get("roe"),
                "quantity": qty,
                "value": round(value, 2),
                "unrealized_pnl": round(value - cost * qty, 2),
                "weight": 0.0,
            })

        if total_value <= 0 or not enriched:
            raise ValidationError("No analyzable holdings provided")

        for item in enriched:
            item["weight"] = round(100.0 * item["value"] / total_value, 2)
        enriched.sort(key=lambda h: h["value"], reverse=True)

        herfindahl = sum(w * w for w in (h["weight"] / 100.0 for h in enriched))
        return {
            "total_value": round(total_value, 2),
            "total_cost": round(total_cost, 2),
            "total_unrealized_pnl": round(total_value - total_cost, 2),
            "unrealized_pnl_pct": round(100.0 * (total_value - total_cost) / total_cost, 2) if total_cost else None,
            "weighted_dividend_yield": round(total_yield / total_value, 3),
            "avg_signal_score": round(score_sum / count, 2) if count else None,
            "holdings_count": len(enriched),
            "concentration_herfindahl": round(herfindahl, 4),
            "sector_exposure": [
                {"sector": s, "value": round(v, 2), "weight": round(100.0 * v / total_value, 2)}
                for s, v in sorted(sector_values.items(), key=lambda kv: kv[1], reverse=True)
            ],
            "holdings": enriched,
        }

    # ------------------------------------------------------------------ #
    # Per-strategy deep backtest (Pro)
    # ------------------------------------------------------------------ #

    def strategy_backtest(
        self, user: UserProfile, strategy: str, symbols: list[str] | None = None
    ) -> dict[str, Any]:
        """Run a focused, per-strategy walk-forward replay over a small universe.

        Pro feature. Unlike the published multi-year NIFTY50 track record, this
        re-runs the signal engine on the requested symbols and returns dated
        per-horizon hit-rates plus benchmark comparison — the kind of research a
        paying user actually needs before trusting a strategy.
        """
        self.require_pro(user, feature=FEATURE_STRATEGY_BACKTESTS)
        from screener.services.backtest_service import BacktestService

        service = container.resolve(BacktestService)
        symbols = [s.strip() for s in (symbols or []) if s.strip()][:10]
        if not symbols:
            symbols = list(config.backtest.universe)[:5]
        return service.run_symbols(strategy=strategy, symbols=symbols)
