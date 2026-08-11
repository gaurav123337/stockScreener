"""Analytics Service — product KPIs from real events + billing state.

Closes the Phase-5 audit gap where DAU/WAU, the activation funnel,
Free->Pro conversion, retention and MRR were listed as KPIs but never
measured. Event tracking is best-effort (a failed event insert must never
break a product request), while the product-owner overview is assembled from
the event log plus the billing store.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from screener.core.analytics_models import AnalyticsEvent, AnalyticsOverview
from screener.core.container import container
from screener.core.subscription_models import subscription_store
from screener.core.user_models import user_store
from screener.infrastructure.persistence.analytics_store import (
    AnalyticsStore,
    analytics_store,
)

# Canonical activation funnel (order matters — later steps are the deeper
# product commitments the audit wanted to see move).
FUNNEL_STEPS = [
    "auth_register",
    "risk_profile_saved",
    "plan_built",
    "scan_run",
    "checkout_created",
    "checkout_paid",
]


class AnalyticsService:
    """Record product events and compute the analytics dashboard."""

    def __init__(
        self,
        store: AnalyticsStore | None = None,
        billing_store: Any = None,
        user_db: Any = None,
    ):
        self._store = store or analytics_store
        self._billing_store = billing_store or subscription_store
        self._user_db = user_db or user_store

    # ------------------------------------------------------------------ track

    def track(self, user_id: str, event_name: str, **properties: Any) -> None:
        """Record a product event. Best-effort: never raises on failure."""
        try:
            event = AnalyticsEvent(
                event_id=f"evt_{uuid.uuid4().hex[:16]}",
                user_id=user_id,
                event_name=event_name,
                properties=properties,
                created_at=datetime.utcnow(),
            )
            self._store.track(event)
        except Exception:
            pass

    # ------------------------------------------------------------- overview

    def overview(self) -> AnalyticsOverview:
        """Assemble the product-owner analytics snapshot from real data."""
        return self._store.overview(
            funnel_steps=FUNNEL_STEPS,
            billing_provider=_BillingMetrics(self._billing_store, self._user_db),
        )

    def overview_dict(self) -> dict[str, Any]:
        """JSON-ready overview for the admin API."""
        return self.overview().model_dump(mode="json")

    def recent_events(self, event_name: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """Recent event log (admin debugging surface)."""
        return [
            e.model_dump(mode="json")
            for e in self._store.list_events(event_name=event_name, limit=limit)
        ]


class _BillingMetrics:
    """Adapter exposing billing-derived KPIs to the analytics overview.

    Mirrors the SubscriptionService surface (paid_mrr / trial_to_paid_conversion
    / push_opt_in_rate) but computes directly from the stores so the analytics
    endpoint does not need to resolve the full SubscriptionService (which would
    pull in a payment gateway).
    """

    def __init__(self, billing_store: Any, user_db: Any):
        self._store = billing_store
        self._user_db = user_db

    def paid_mrr(self) -> float:
        from screener.core.subscription_models import SubscriptionStatus

        plans = {
            "pro_monthly": (199.0, "month"),
            "pro_yearly": (1999.0, "year"),
        }
        total = 0.0
        for row in self._store._list_subscriptions():
            status = (row.get("status") or "none")
            if status not in (
                SubscriptionStatus.ACTIVE.value,
                SubscriptionStatus.TRIAL.value,
            ):
                continue
            if status == SubscriptionStatus.TRIAL.value:
                continue
            spec = plans.get(row.get("plan_id"))
            if spec is None:
                continue
            price, interval = spec
            total += price / 12.0 if interval == "year" else price
        return round(total, 2)

    def trial_to_paid_conversion(self) -> float:
        starters: dict[str, bool] = {}
        payers: dict[str, bool] = {}
        for row in self._store._list_checkouts():
            uid = row.get("user_id")
            if uid is None:
                continue
            starters[uid] = True
            if (row.get("status") or "") == "paid":
                payers[uid] = True
        if not starters:
            return 0.0
        return round(len(payers) / len(starters), 4)

    def push_opt_in_rate(self) -> float:
        total = self._user_db.count_users()
        if total <= 0:
            return 0.0
        return round(self._store._distinct_push_users() / total, 4)


# Global instance
analytics_service = AnalyticsService()
