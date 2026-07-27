"""Self-updating knowledge base.

Drop .pdf / .md / .txt files into the `knowledge/` folder and run `learn`.
Text is extracted (pypdf for PDFs), lightly summarised into bullet rules, and
appended to knowledge_graph/market_knowledge.md under "Learned rules".
A manifest prevents re-ingesting the same file twice.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = ROOT / "knowledge"
KB_FILE = ROOT / "knowledge_graph" / "market_knowledge.md"
MANIFEST = ROOT / "knowledge_graph" / ".learn_manifest.json"


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _load_manifest() -> dict:
    if MANIFEST.exists():
        try:
            return json.loads(MANIFEST.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_manifest(m: dict) -> None:
    MANIFEST.write_text(json.dumps(m, indent=2), encoding="utf-8")


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    return path.read_text(encoding="utf-8", errors="ignore")


def distill_rules(text: str, max_rules: int = 12) -> list[str]:
    """Naive extractive distillation: keep lines/sentences that look like rules
    (contain market keywords + a number or an imperative)."""
    keywords = re.compile(
        r"(rsi|macd|moving average|dma|p/e|peg|roe|debt|stop.?loss|target|"
        r"breakout|support|resistance|trend|momentum|volume|buy|sell|"
        r"earnings|valuation|52.?week)", re.I)
    candidates = re.split(r"(?<=[.!?])\s+|\n+", text)
    rules, seen = [], set()
    for c in candidates:
        c = " ".join(c.split())
        if not (30 <= len(c) <= 220):
            continue
        if not keywords.search(c):
            continue
        key = c.lower()[:60]
        if key in seen:
            continue
        seen.add(key)
        rules.append(c)
        if len(rules) >= max_rules:
            break
    return rules


def ingest_bytes(filename: str, content: bytes) -> dict:
    """Save an uploaded file into knowledge/ (PDF, md, txt, or a video *transcript*
    saved as .txt) and immediately learn from it. Returns the learn() result."""
    KNOWLEDGE_DIR.mkdir(exist_ok=True)
    safe = Path(filename).name  # strip any path components
    allowed = {".pdf", ".md", ".txt", ".srt", ".vtt"}
    if Path(safe).suffix.lower() not in allowed:
        return {"ok": False, "error": f"unsupported type; allowed {sorted(allowed)} "
                "(for video, upload its transcript/subtitle as .txt/.srt/.vtt)"}
    dest = KNOWLEDGE_DIR / safe
    dest.write_bytes(content)
    res = learn(verbose=False)
    res.update({"ok": True, "saved_as": safe})
    return res


def ingest_url(url: str) -> dict:
    """Fetch a public URL (blog/article), save readable text as .md, then learn."""
    import re as _re
    try:
        import requests
        resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        return {"ok": False, "error": f"could not fetch URL: {e}"}
    # crude readability: strip scripts/styles/tags
    txt = _re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    txt = _re.sub(r"(?is)<[^>]+>", " ", txt)
    txt = _re.sub(r"\s+", " ", txt).strip()
    if len(txt) < 200:
        return {"ok": False, "error": "page had too little readable text"}
    KNOWLEDGE_DIR.mkdir(exist_ok=True)
    slug = _re.sub(r"[^a-z0-9]+", "_", url.lower())[:40].strip("_") or "page"
    dest = KNOWLEDGE_DIR / f"url_{slug}.md"
    dest.write_text(f"# {url}\n\n{txt}", encoding="utf-8")
    res = learn(verbose=False)
    res.update({"ok": True, "saved_as": dest.name})
    return res


def learn(verbose: bool = True) -> dict:

    KNOWLEDGE_DIR.mkdir(exist_ok=True)
    KB_FILE.parent.mkdir(exist_ok=True)
    manifest = _load_manifest()
    ingested, skipped, total_rules = [], [], 0
    new_lines: list[str] = []

    for path in sorted(KNOWLEDGE_DIR.glob("*")):
        if path.suffix.lower() not in {".pdf", ".md", ".txt", ".srt", ".vtt"}:
            continue

        h = _hash(path)
        if manifest.get(path.name) == h:
            skipped.append(path.name)
            continue
        try:
            text = extract_text(path)
        except Exception as e:
            if verbose:
                print(f"  ! could not read {path.name}: {e}")
            continue
        rules = distill_rules(text)
        if rules:
            new_lines.append(f"\n### From `{path.name}`")
            new_lines += [f"- {r}" for r in rules]
        manifest[path.name] = h
        ingested.append(path.name)
        total_rules += len(rules)

    if new_lines:
        with KB_FILE.open("a", encoding="utf-8") as f:
            f.write("\n".join(new_lines) + "\n")
    _save_manifest(manifest)
    return {"ingested": ingested, "skipped": skipped, "rules_added": total_rules}
