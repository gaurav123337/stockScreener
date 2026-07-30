"""SMTP delivery adapter for newly submitted feedback."""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

from screener.core.feedback_models import FeedbackRecord
from screener.core.interfaces import FeedbackNotifier


class SMTPFeedbackNotifier(FeedbackNotifier):
    """Send feedback email when SMTP credentials are configured."""

    DEFAULT_RECIPIENT = "garudagaura@gmail.com"

    def __init__(
        self,
        *,
        host: str = "",
        port: int = 587,
        username: str = "",
        password: str = "",
        recipient: str = DEFAULT_RECIPIENT,
        sender: str = "",
        use_tls: bool = True,
        timeout: float = 10.0,
    ):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._recipient = recipient
        self._sender = sender or username
        self._use_tls = use_tls
        self._timeout = timeout

    @classmethod
    def from_environment(cls) -> "SMTPFeedbackNotifier":
        try:
            port = int(os.getenv("SCREENER_SMTP_PORT", "587"))
        except ValueError:
            port = 587
        return cls(
            host=os.getenv("SCREENER_SMTP_HOST", "").strip(),
            port=port,
            username=os.getenv("SCREENER_SMTP_USERNAME", "").strip(),
            password=os.getenv("SCREENER_SMTP_PASSWORD", ""),
            recipient=os.getenv(
                "SCREENER_FEEDBACK_EMAIL_TO", cls.DEFAULT_RECIPIENT
            ).strip(),
            sender=os.getenv("SCREENER_SMTP_FROM", "").strip(),
            use_tls=os.getenv("SCREENER_SMTP_USE_TLS", "true").strip().lower()
            not in {"0", "false", "no"},
        )

    def notify(self, feedback: FeedbackRecord, reporter_email: str | None) -> None:
        if not self._host or not self._sender or not self._recipient:
            return

        message = EmailMessage()
        safe_title = " ".join(feedback.title.split())
        message["Subject"] = f"[stockScreener feedback] {feedback.category}: {safe_title}"
        message["From"] = self._sender
        message["To"] = self._recipient
        if reporter_email:
            message["Reply-To"] = reporter_email
        message.set_content(
            "\n".join(
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
        )

        with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as client:
            if self._use_tls:
                client.starttls()
            if self._username and self._password:
                client.login(self._username, self._password)
            client.send_message(message)