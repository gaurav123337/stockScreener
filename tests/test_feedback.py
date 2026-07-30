"""Offline tests for rich-text feedback validation and persistence."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from screener.core.feedback_models import FeedbackSubmission
from screener.core.responses import ValidationError
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


if __name__ == "__main__":
    unittest.main()
