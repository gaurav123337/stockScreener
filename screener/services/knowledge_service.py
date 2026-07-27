"""Knowledge Service — ingestion and distillation of market rules."""
from __future__ import annotations

import re
from pathlib import Path

from screener.core.config import config
from screener.core.container import container
from screener.core.interfaces import KnowledgeStore
from screener.core.models import LearnResult


class KnowledgeService:
    """Manages learning from PDFs, notes, URLs, and transcripts."""

    def __init__(self, store: KnowledgeStore | None = None):
        self._store = store or container.resolve(KnowledgeStore)

    def learn_from_file(self, path: Path) -> LearnResult:
        """Ingest a single file."""
        if path.suffix.lower() not in config.knowledge.allowed_extensions:
            return LearnResult(
                ok=False,
                error=f"unsupported type {path.suffix}; allowed {sorted(config.knowledge.allowed_extensions)}",
            )

        if self._store.is_file_ingested(path):
            return LearnResult(ok=True, skipped=[path.name])

        try:
            text = self._extract_text(path)
        except Exception as e:
            return LearnResult(ok=False, error=f"could not read {path.name}: {e}")

        rules = self._distill_rules(text)
        if rules:
            self._store.append_rules(path.name, rules)
        self._store.mark_file_ingested(path)

        return LearnResult(ok=True, ingested=[path.name], rules_added=len(rules))

    def learn_from_directory(self, directory: Path | None = None) -> LearnResult:
        """Ingest all eligible files in a directory."""
        directory = directory or config.knowledge_dir
        directory.mkdir(parents=True, exist_ok=True)

        ingested: list[str] = []
        skipped: list[str] = []
        total_rules = 0

        for path in sorted(directory.glob("*")):
            if path.suffix.lower() not in config.knowledge.allowed_extensions:
                continue
            result = self.learn_from_file(path)
            if result.ok and result.ingested:
                ingested.extend(result.ingested)
                total_rules += result.rules_added
            elif result.ok and result.skipped:
                skipped.extend(result.skipped)

        return LearnResult(
            ok=True,
            ingested=ingested,
            skipped=skipped,
            rules_added=total_rules,
        )

    def learn_from_url(self, url: str) -> LearnResult:
        """Fetch a public URL, save readable text, and learn from it."""
        try:
            import requests
            resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            html = resp.text
        except Exception as e:
            return LearnResult(ok=False, error=f"could not fetch URL: {e}")

        # Crude readability: strip scripts/styles/tags
        txt = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
        txt = re.sub(r"(?is)<[^>]+>", " ", txt)
        txt = re.sub(r"\s+", " ", txt).strip()

        if len(txt) < 200:
            return LearnResult(ok=False, error="page had too little readable text")

        config.knowledge_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "_", url.lower())[:40].strip("_") or "page"
        dest = config.knowledge_dir / f"url_{slug}.md"
        dest.write_text(f"# {url}\n\n{txt}", encoding="utf-8")

        result = self.learn_from_file(dest)
        result.saved_as = dest.name
        return result

    def get_knowledge_content(self) -> str:
        """Return the full knowledge base content."""
        return self._store.get_content()

    def _extract_text(self, path: Path) -> str:
        """Extract text from PDF or plain text file."""
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            return "\n".join((p.extract_text() or "") for p in reader.pages)
        return path.read_text(encoding="utf-8", errors="ignore")

    def _distill_rules(self, text: str) -> list[str]:
        """Naive extractive distillation: keep lines/sentences that look like rules."""
        keywords = re.compile(
            r"(rsi|macd|moving average|dma|p/e|peg|roe|debt|stop.?loss|target|"
            r"breakout|support|resistance|trend|momentum|volume|buy|sell|"
            r"earnings|valuation|52.?week)", re.I)
        candidates = re.split(r"(?<=[.!?])\s+|\n+", text)
        rules, seen = [], set()
        for c in candidates:
            c = " ".join(c.split())
            if not (config.knowledge.min_rule_length <= len(c) <= config.knowledge.max_rule_length):
                continue
            if not keywords.search(c):
                continue
            key = c.lower()[:60]
            if key in seen:
                continue
            seen.add(key)
            rules.append(c)
            if len(rules) >= config.knowledge.max_rules_per_doc:
                break
        return rules
