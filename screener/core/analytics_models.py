"""Product analytics domain models (Phase 5 gap-closure).

The audited KPIs (DAU/WAU, activation funnel, Free->Pro conversion,
retention, MRR, push opt-in) were previously unmeasured. This module adds a
minimal event store plus the derived metrics computed at query time, so the
product-owner dashboard can report them from real product events instead of
estimates.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AnalyticsEvent(BaseModel):
    """A single product event (auth, onboarding, scan, checkout, ...)."""

    event_id: str
    user_id: str
    event_name: str
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)


class FunnelStep(BaseModel):
    """Distinct users who reached one activation-funnel step."""

    step: str
    users: int


class RetentionPoint(BaseModel):
    """Cohort retention: share of an original cohort active in a window."""

    window_start: datetime
    window_end: datetime
    cohort_users: int
    returned_users: int
    retention_rate: float


class AnalyticsOverview(BaseModel):
    """Aggregate analytics snapshot for the product-owner dashboard."""

    generated_at: datetime = Field(default_factory=_utcnow)
    dau: int = 0
    wau: int = 0
    total_users: int = 0
    funnel: list[FunnelStep] = Field(default_factory=list)
    free_to_pro_conversion: float = 0.0
    trial_to_paid_conversion: float = 0.0
    retention_90d: float = 0.0
    mrr_inr: float = 0.0
    push_opt_in_rate: float = 0.0
