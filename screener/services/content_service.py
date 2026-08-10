"""Content Service — beginner explainers for the SEO moat (Phase 5).

Serves the structured explainer catalogue to three consumers: the JSON API
(``/api/learn``), server-rendered SEO pages (``/learn/{slug}``), and the
in-app reader. Content is deliberately structured (sections + bullets) so a
single source can be rendered without a markdown parser.
"""
from __future__ import annotations

from typing import Any

from screener.core.content_models import Article, ContentStore, content_store
from screener.core.responses import NotFoundError


class ContentService:
    """Reads and exposes the explainer catalogue."""

    def __init__(self, store: ContentStore | None = None):
        self._store = store or content_store

    def list_articles(self) -> list[dict[str, Any]]:
        """Lightweight catalogue (no full bodies) for listing screens."""
        return [
            {
                "slug": a.slug,
                "title": a.title,
                "tagline": a.tagline,
                "category": a.category,
                "reading_minutes": a.reading_minutes,
                "word_count": a.word_count,
                "excerpt": a.excerpt(),
                "related_slugs": a.related_slugs,
                "updated_at": a.updated_at,
            }
            for a in self._store.list_articles()
        ]

    def get_article(self, slug: str) -> Article:
        article = self._store.get_article(slug)
        if article is None:
            raise NotFoundError("Article not found")
        return article

    def search(self, q: str = "") -> list[dict[str, Any]]:
        """Keyword search over titles, taglines and section bodies."""
        q = (q or "").strip().lower()
        if not q:
            return self.list_articles()
        results = []
        for article in self._store.list_articles():
            haystack = f"{article.title} {article.tagline}".lower()
            haystack += " " + " ".join(
                f"{s.heading} {s.body} {' '.join(s.bullets)}".lower()
                for s in article.sections
            )
            if q in haystack:
                results.append({
                    "slug": article.slug,
                    "title": article.title,
                    "tagline": article.tagline,
                    "category": article.category,
                    "excerpt": article.excerpt(),
                })
        return results


# Global instance
content_service = ContentService()
