"""Resend HTTPS delivery adapter for newly submitted feedback."""
from __future__ import annotations

import os
from html import escape

import requests

from screener.core.feedback_models import FeedbackRecord
from screener.core.interfaces import FeedbackNotifier


class ResendFeedbackNotifier(FeedbackNotifier):
    """Send feedback through Resend's HTTPS API."""

    API_URL = "https://api.resend.com/emails"
    DEFAULT_RECIPIENT = "garudagaura@gmail.com"

    def __init__(
        self,
        *,
        api_key: str = "",
        sender: str = "",
        recipient: str = DEFAULT_RECIPIENT,
        timeout: float = 10.0,
    ):
        self._api_key = api_key
        self._sender = sender
        self._recipient = recipient
        self._timeout = timeout

    @classmethod
    def from_environment(cls) -> "ResendFeedbackNotifier":
        return cls(
            api_key=os.getenv("RESEND_API_KEY", "").strip(),
            sender=os.getenv("SCREENER_FEEDBACK_EMAIL_FROM", "").strip(),
            recipient=os.getenv(
                "SCREENER_FEEDBACK_EMAIL_TO", cls.DEFAULT_RECIPIENT
            ).strip(),
        )

    def notify(self, feedback: FeedbackRecord, reporter_email: str | None) -> None:
        missing = [
            name
            for name, value in (
                ("RESEND_API_KEY", self._api_key),
                ("SCREENER_FEEDBACK_EMAIL_FROM", self._sender),
                ("SCREENER_FEEDBACK_EMAIL_TO", self._recipient),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Feedback email notification is not configured; missing "
                + ", ".join(missing)
            )

        safe_title = " ".join(feedback.title.split())
        text = "\n".join(
            [
                "New stockScreener feedback was submitted.",
                "",
                f"Feedback ID: {feedback.feedback_id}",
                f"Submitted: {feedback.created_at.isoformat()}",
                f"Reporter: {feedback.username} ({feedback.user_id})",
                f"Reporter email: {reporter_email or 'Not available'}",
                f"Category: {feedback.category}",
                f"Title: {safe_title}",
                "",
                "Details:",
                feedback.plain_text,
            ]
        )
        payload: dict[str, object] = {
            "from": self._sender,
            "to": [self._recipient],
            "subject": f"[stockScreener feedback] {feedback.category}: {safe_title}",
            "text": text,
            "html": f"<pre>{escape(text)}</pre>",
        }
        if reporter_email:
            payload["reply_to"] = reporter_email

        response = requests.post(
            self.API_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self._timeout,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            detail = response.text[:500]
            raise RuntimeError(
                f"Resend rejected feedback email ({response.status_code}): {detail}"
            ) from exc