"""Compliance & provenance helpers — the trust surface of the product.

Every screen that shows a score or action carries a compliance block:
- an educational framing note ("not SEBI-registered advice"),
- a "scores are not guarantees" disclaimer,
- data-source attribution,
- a last-updated timestamp so stale data is visible, not hidden.

These helpers centralise that envelope so the wording (configured in
``config.compliance``) is applied consistently across every endpoint.
"""
from __future__ import annotations

from datetime import datetime, timezone

from screener.core.config import config


def coverage_ratio(matched: int, total: int) -> float:
    """Fraction (0.0–1.0) of the scanned universe that produced results."""
    if total <= 0:
        return 0.0
    return round(max(0.0, min(1.0, matched / total)), 4)


def is_stale(data_updated_at: datetime | None) -> bool:
    """True when the freshest underlying data is older than the history TTL.

    A scan served entirely from a warm cache (or with no cache at all) is
    flagged so the UI can surface a stale-data warning to the user.
    """
    if data_updated_at is None:
        return True
    age = datetime.now(timezone.utc) - data_updated_at
    return age.total_seconds() > config.data.history_cache_ttl_seconds


def compliance_block(data_source: str | None = None) -> dict:
    """The standard disclaimer + attribution block for a response."""
    return {
        "educational_note": config.compliance.educational_note,
        "disclaimer": config.compliance.disclaimer,
        "data_source": data_source or config.compliance.data_source_label,
        "is_investment_advice": False,
    }


def provenance_block(data_updated_at: datetime | None = None) -> dict:
    """The freshness block (data attribution + last-updated timestamp)."""
    return {
        "data_updated_at": data_updated_at.isoformat() if data_updated_at else None,
        "stale": is_stale(data_updated_at),
    }
