"""Content models — beginner explainers for the SEO moat (Phase 5).

The Moneycontrol lesson applied with depth: instead of thin landing pages,
each article is a real explainer with sections, worked examples, glossary
cross-links and a plain-language summary. Content is structured (not freeform
markdown) so it can be served three ways from one source: the JSON API, the
server-rendered SEO page, and the in-app reader — without duplicating copy.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ArticleSection(BaseModel):
    """One titled block within an article."""

    heading: str
    body: str = ""                 # paragraphs separated by blank lines
    bullets: list[str] = Field(default_factory=list)


class Article(BaseModel):
    """A beginner explainer. ``slug`` is the stable public identifier."""

    slug: str
    title: str
    tagline: str = ""
    category: str = "Concepts"     # Concepts | Funds | Taxation | Strategy | Product
    reading_minutes: int = 3
    seo_meta: dict[str, str] = Field(default_factory=dict)  # {"description": ...}
    sections: list[ArticleSection] = Field(default_factory=list)
    related_slugs: list[str] = Field(default_factory=list)
    published: bool = True
    updated_at: str = ""

    @property
    def word_count(self) -> int:
        words = sum(len(_plain_text(s).split()) for s in self.sections)
        return max(words, 1)

    def excerpt(self, limit: int = 160) -> str:
        text = _plain_text(self.sections[0]) if self.sections else self.tagline
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) <= limit:
            return text
        return text[: limit - 3].rstrip() + "…"


def _plain_text(section: ArticleSection) -> str:
    parts = [section.body]
    parts.extend(section.bullets)
    return "\n".join(p for p in parts if p)


# --------------------------------------------------------------------------- #
# Content store — one JSON catalogue plus per-article files
# --------------------------------------------------------------------------- #

class ContentStore:
    """Loads the curated article catalogue from ``content/*.json``."""

    def __init__(self, content_dir: Path | None = None):
        from screener.core.config import config

        self._dir = content_dir or (config.root_dir / "content")
        self._catalogue = self._dir / "catalogue.json"

    def _load_articles(self) -> list[Article]:
        if not self._catalogue.exists():
            return []
        try:
            raw = json.loads(self._catalogue.read_text(encoding="utf-8"))
            return [Article(**item) for item in raw]
        except Exception:
            return []

    def list_articles(self, only_published: bool = True) -> list[Article]:
        articles = self._load_articles()
        if only_published:
            articles = [a for a in articles if a.published]
        return articles

    def get_article(self, slug: str) -> Article | None:
        for article in self._load_articles():
            if article.slug == slug and article.published:
                return article
        return None


# Global store instance
content_store = ContentStore()
