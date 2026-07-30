"""Application service for validating and recording tester feedback."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from screener.core.feedback_models import FeedbackRecord, FeedbackSubmission
from screener.core.responses import ValidationError
from screener.infrastructure.persistence.feedback_store import FeedbackStore


class FeedbackService:
    """Validate rich-text documents and persist feedback receipts."""

    _MAX_DOCUMENT_BYTES = 50_000
    _MAX_DETAILS_LENGTH = 5_000
    _BLOCK_NODES = {
        "blockquote", "bulletList", "codeBlock", "heading", "listItem",
        "orderedList", "paragraph",
    }

    def __init__(self, store: FeedbackStore | None = None):
        self._store = store or FeedbackStore()

    def submit(
        self,
        submission: FeedbackSubmission,
        *,
        user_id: str,
        username: str,
    ) -> FeedbackRecord:
        title = submission.title.strip()
        document = submission.document

        if document.get("type") != "doc" or not isinstance(document.get("content"), list):
            raise ValidationError("Feedback document has an invalid rich-text structure")

        plain_text = self._extract_plain_text(document).strip()

        if not title or len(title) < 3:
            raise ValidationError("Feedback title must contain at least 3 characters")
        if not plain_text or len(plain_text) < 10:
            raise ValidationError("Feedback details must contain at least 10 characters")
        if len(plain_text) > self._MAX_DETAILS_LENGTH:
            raise ValidationError("Feedback details must contain at most 5,000 characters")

        document_size = len(json.dumps(document, ensure_ascii=False).encode("utf-8"))
        if document_size > self._MAX_DOCUMENT_BYTES:
            raise ValidationError("Feedback document is too large (max 50 KB)")

        record = FeedbackRecord(
            feedback_id=str(uuid4()),
            user_id=user_id,
            username=username,
            category=submission.category,
            title=title,
            document=document,
            plain_text=plain_text,
            created_at=datetime.now(timezone.utc),
        )
        return self._store.create(record)

    @classmethod
    def _extract_plain_text(cls, node: object) -> str:
        """Validate a TipTap node tree and derive its trusted text projection."""
        if not isinstance(node, dict) or not isinstance(node.get("type"), str):
            raise ValidationError("Feedback document has an invalid rich-text structure")

        node_type = node["type"]
        if node_type == "text":
            text = node.get("text")
            if not isinstance(text, str):
                raise ValidationError("Feedback document has an invalid rich-text structure")
            return text
        if node_type == "hardBreak":
            return "\n"

        content = node.get("content", [])
        if not isinstance(content, list):
            raise ValidationError("Feedback document has an invalid rich-text structure")

        child_text = "".join(cls._extract_plain_text(child) for child in content)
        return f"{child_text}\n" if node_type in cls._BLOCK_NODES else child_text
