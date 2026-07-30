"""Offline tests for rich-text feedback validation and persistence."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

from screener.core.feedback_models import FeedbackSubmission
from screener.core.responses import ValidationError
from screener.infrastructure.notifications import (
    ResendFeedbackNotifier,
    SMTPFeedbackNotifier,
)
from screener.infrastructure.persistence.feedback_store import FeedbackStore
from screener.services.feedback_service import FeedbackService


class FeedbackServiceTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.store = FeedbackStore(Path(self._temp_dir.name) / "feedback.db")
        self.service = FeedbackService(self.store)

    def tearDown(self):
        self._temp_dir.cleanup()

    @staticmethod
    def submission() -> FeedbackSubmission:
        return FeedbackSubmission(
            category="concern",
            title="Signal explanation is unclear",
            plain_text="The highlighted score explanation needs more detail. 😕",
            document={
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": "The highlighted score explanation needs more detail. 😕",
                                "marks": [{"type": "highlight"}],
                            }
                        ],
                    }
                ],
            },
        )

    def test_preserves_rich_text_emoji_and_tenant_attribution(self):
        record = self.service.submit(
            self.submission(), user_id="tenant-a", username="tester-a"
        )

        stored = self.store.list_by_user("tenant-a")

        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].feedback_id, record.feedback_id)
        self.assertEqual(stored[0].username, "tester-a")
        self.assertIn("😕", stored[0].plain_text)
        self.assertEqual(
            stored[0].document["content"][0]["content"][0]["marks"],
            [{"type": "highlight"}],
        )
        self.assertEqual(self.store.list_by_user("tenant-b"), [])

    def test_rejects_invalid_document_structure(self):
        submission = self.submission().model_copy(update={"document": {"type": "html"}})

        with self.assertRaises(ValidationError):
            self.service.submit(submission, user_id="tenant-a", username="tester-a")

    def test_derives_plain_text_from_document_instead_of_client_projection(self):
        submission = self.submission().model_copy(
            update={"plain_text": "This forged projection is not persisted."}
        )

        record = self.service.submit(
            submission, user_id="tenant-a", username="tester-a"
        )

        self.assertEqual(
            record.plain_text,
            "The highlighted score explanation needs more detail. 😕",
        )

    def test_rejects_effectively_empty_document_even_with_client_text(self):
        submission = self.submission().model_copy(
            update={
                "plain_text": "This client text is long enough but untrusted.",
                "document": {"type": "doc", "content": [{"type": "paragraph"}]},
            }
        )

        with self.assertRaises(ValidationError):
            self.service.submit(submission, user_id="tenant-a", username="tester-a")

    def test_rejects_malformed_nested_content(self):
        submission = self.submission().model_copy(
            update={
                "document": {
                    "type": "doc",
                    "content": [{"type": "paragraph", "content": "not-a-list"}],
                }
            }
        )

        with self.assertRaises(ValidationError):
            self.service.submit(submission, user_id="tenant-a", username="tester-a")

    def test_rejects_derived_text_over_limit(self):
        submission = self.submission().model_copy(
            update={
                "plain_text": "Client projection remains within its model limit.",
                "document": {
                    "type": "doc",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "x" * 5001}],
                        }
                    ],
                },
            }
        )

        with self.assertRaises(ValidationError):
            self.service.submit(submission, user_id="tenant-a", username="tester-a")

    def test_notifies_product_owner_after_feedback_is_persisted(self):
        notifier = MagicMock()
        service = FeedbackService(self.store, notifier=notifier)

        record = service.submit(
            self.submission(),
            user_id="tenant-a",
            username="tester-a",
            reporter_email="tester@example.com",
        )

        notifier.notify.assert_called_once_with(record, "tester@example.com")
        self.assertEqual(len(self.store.list_by_user("tenant-a")), 1)

    def test_notification_failure_does_not_lose_persisted_feedback(self):
        notifier = MagicMock()
        notifier.notify.side_effect = RuntimeError("SMTP unavailable")
        service = FeedbackService(self.store, notifier=notifier)

        with self.assertLogs("screener.services.feedback_service", level="ERROR"):
            record = service.submit(
                self.submission(), user_id="tenant-a", username="tester-a"
            )

        self.assertEqual(
            self.store.list_by_user("tenant-a")[0].feedback_id, record.feedback_id
        )


class SMTPFeedbackNotifierTests(unittest.TestCase):
    @patch("screener.infrastructure.notifications.smtp_feedback_notifier.smtplib.SMTP")
    def test_sends_feedback_to_configured_product_owner(self, smtp_type):
        smtp = smtp_type.return_value.__enter__.return_value
        with tempfile.TemporaryDirectory() as temp_dir:
            service_record = FeedbackService(
                FeedbackStore(Path(temp_dir) / "feedback.db")
            ).submit(
                FeedbackServiceTests.submission(),
                user_id="tenant-a",
                username="tester-a",
            )
            notifier = SMTPFeedbackNotifier(
                host="smtp.example.com",
                username="sender@example.com",
                password="secret",
            )

            notifier.notify(service_record, "tester@example.com")

            smtp_type.assert_called_once_with("smtp.example.com", 587, timeout=10.0)
            smtp.starttls.assert_called_once_with()
            smtp.login.assert_called_once_with("sender@example.com", "secret")
            message = smtp.send_message.call_args.args[0]
            self.assertEqual(message["To"], "garudagaura@gmail.com")
            self.assertEqual(message["Reply-To"], "tester@example.com")
            self.assertIn(service_record.feedback_id, message.get_content())

    @patch.dict("os.environ", {"SCREENER_SMTP_PORT": "invalid"})
    def test_invalid_environment_port_falls_back_to_standard_submission_port(self):
        notifier = SMTPFeedbackNotifier.from_environment()

        self.assertEqual(notifier._port, 587)


class ResendFeedbackNotifierTests(unittest.TestCase):
    @staticmethod
    def record():
        with tempfile.TemporaryDirectory() as temp_dir:
            return FeedbackService(
                FeedbackStore(Path(temp_dir) / "feedback.db")
            ).submit(
                FeedbackServiceTests.submission(),
                user_id="tenant-a",
                username="tester-a",
            )

    @patch("screener.infrastructure.notifications.resend_feedback_notifier.requests.post")
    def test_sends_feedback_over_https(self, post):
        post.return_value.raise_for_status.return_value = None
        record = self.record()
        notifier = ResendFeedbackNotifier(
            api_key="re_test",
            sender="Stock Screener <feedback@example.com>",
        )

        notifier.notify(record, "tester@example.com")

        request = post.call_args
        self.assertEqual(request.args[0], "https://api.resend.com/emails")
        self.assertEqual(request.kwargs["headers"]["Authorization"], "Bearer re_test")
        self.assertEqual(request.kwargs["json"]["to"], ["garudagaura@gmail.com"])
        self.assertEqual(request.kwargs["json"]["reply_to"], "tester@example.com")
        self.assertIn(record.feedback_id, request.kwargs["json"]["text"])

    def test_missing_configuration_is_reported(self):
        notifier = ResendFeedbackNotifier()

        with self.assertRaisesRegex(RuntimeError, "RESEND_API_KEY"):
            notifier.notify(self.record(), None)

    @patch("screener.infrastructure.notifications.resend_feedback_notifier.requests.post")
    def test_rejected_request_includes_provider_response(self, post):
        response = post.return_value
        response.status_code = 403
        response.text = '{"message":"Sender domain is not verified"}'
        response.raise_for_status.side_effect = requests.HTTPError("forbidden")
        notifier = ResendFeedbackNotifier(
            api_key="re_test",
            sender="Stock Screener <feedback@example.com>",
        )

        with self.assertRaisesRegex(RuntimeError, "Sender domain is not verified"):
            notifier.notify(self.record(), None)


if __name__ == "__main__":
    unittest.main()
