"""Domain models for tester feedback."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


FeedbackCategory = Literal["bug", "concern", "idea", "other"]


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
    created_at: datetime
