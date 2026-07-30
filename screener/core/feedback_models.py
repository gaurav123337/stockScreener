"""Domain models for tester feedback."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


FeedbackCategory = Literal["bug", "concern", "idea", "other"]
FeedbackStatus = Literal["new", "triaged", "planned", "in_progress", "resolved", "closed"]
FeedbackPriority = Literal["low", "medium", "high", "critical"]


class FeedbackSubmission(BaseModel):
    """Validated feedback submitted by a tester."""

    category: FeedbackCategory
    title: str = Field(..., min_length=3, max_length=120)
    document: dict[str, Any]
    plain_text: str = Field(..., min_length=10, max_length=5000)


class FeedbackRecord(FeedbackSubmission):
    """Persisted feedback with ownership and audit fields."""

    feedback_id: str
    user_id: str
    username: str
    status: FeedbackStatus = "new"
    priority: FeedbackPriority = "medium"
    assignee_id: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    resolved_at: datetime | None = None


class FeedbackWorkflowUpdate(BaseModel):
    status: FeedbackStatus | None = None
    priority: FeedbackPriority | None = None
    assignee_id: str | None = None
    internal_note: str | None = Field(None, max_length=2000)
    reason: str = Field(..., min_length=3, max_length=500)
