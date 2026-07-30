"""CSV-based implementation of PredictionRepository and KnowledgeStore."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from screener.core.config import config
from screener.core.interfaces import KnowledgeStore, PredictionRepository
from screener.core.models import (
    Action,
    Outcome,
    PredictionRecord,
)


class CSVPredictionRepository(PredictionRepository):
    """Persists predictions to a CSV file."""

    FIELDS = [
        "ts", "symbol", "action", "price_at_call", "target", "stop_loss",
        "horizon_days", "evaluated", "eval_date", "price_at_eval",
        "outcome", "return_pct",
    ]

    def __init__(self, filepath: Path | None = None):
        self._filepath = filepath or config.predictions_file
        self._ensure()

    def _ensure(self) -> None:
        self._filepath.parent.mkdir(parents=True, exist_ok=True)
        if not self._filepath.exists():
            with self._filepath.open("w", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=self.FIELDS).writeheader()

    def _row_to_record(self, row: dict[str, str]) -> PredictionRecord:
        return PredictionRecord(
            ts=datetime.fromisoformat(row["ts"]),
            symbol=row["symbol"],
            action=Action(row["action"]),
            price_at_call=float(row["price_at_call"]),
            target=float(row["target"]) if row["target"] else None,
            stop_loss=float(row["stop_loss"]) if row["stop_loss"] else None,
            horizon_days=int(row["horizon_days"]),
            evaluated=row["evaluated"] == "1",
            eval_date=datetime.fromisoformat(row["eval_date"]) if row["eval_date"] else None,
            price_at_eval=float(row["price_at_eval"]) if row["price_at_eval"] else None,
            outcome=Outcome(row["outcome"]) if row["outcome"] else None,
            return_pct=float(row["return_pct"]) if row["return_pct"] else None,
        )

    def _record_to_row(self, record: PredictionRecord) -> dict[str, Any]:
        return {
            "ts": record.ts.isoformat(timespec="seconds"),
            "symbol": record.symbol,
            "action": record.action.value,
            "price_at_call": record.price_at_call,
            "target": record.target or "",
            "stop_loss": record.stop_loss or "",
            "horizon_days": record.horizon_days,
            "evaluated": "1" if record.evaluated else "0",
            "eval_date": record.eval_date.isoformat() if record.eval_date else "",
            "price_at_eval": record.price_at_eval or "",
            "outcome": record.outcome.value if record.outcome else "",
            "return_pct": record.return_pct or "",
        }

    def save(self, record: PredictionRecord) -> None:
        if record.action not in (Action.BUY, Action.SELL):
            return  # only verifiable directional calls
        with self._filepath.open("a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=self.FIELDS).writerow(
                self._record_to_row(record)
            )

    def get_all(self) -> list[PredictionRecord]:
        self._ensure()
        with self._filepath.open("r", newline="", encoding="utf-8") as f:
            return [self._row_to_record(r) for r in csv.DictReader(f)]

    def get_due(self, horizon_days: int | None = None) -> list[PredictionRecord]:
        horizon = horizon_days or config.verification.horizon_days
        today = date.today()
        due = []
        for record in self.get_all():
            if record.evaluated:
                continue
            if (today - record.ts.date()).days >= record.horizon_days:
                due.append(record)
        return due

    def update(self, record: PredictionRecord) -> None:
        # Rewrite all rows (CSV has no native update)
        all_records = self.get_all()
        with self._filepath.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.FIELDS)
            writer.writeheader()
            for r in all_records:
                if r.ts == record.ts and r.symbol == record.symbol:
                    writer.writerow(self._record_to_row(record))
                else:
                    writer.writerow(self._record_to_row(r))


class MarkdownKnowledgeStore(KnowledgeStore):
    """Persists knowledge to a Markdown file with a JSON manifest."""

    def __init__(self, kb_file: Path | None = None, manifest_file: Path | None = None):
        self._kb_file = kb_file or config.kb_file
        self._manifest_file = manifest_file or config.learn_manifest_file
        self._kb_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_manifest(self) -> dict[str, str]:
        if self._manifest_file.exists():
            try:
                return json.loads(self._manifest_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_manifest(self, manifest: dict[str, str]) -> None:
        self._manifest_file.write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

    def _hash_file(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]

    def append_rules(self, source: str, rules: list[str]) -> None:
        if not rules:
            return
        lines = [f"\n### From `{source}`"]
        lines += [f"- {r}" for r in rules]
        with self._kb_file.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def get_content(self) -> str:
        try:
            return self._kb_file.read_text(encoding="utf-8")
        except FileNotFoundError:
            # A new or ephemeral deployment may not have learned anything yet.
            # Missing knowledge is a valid empty state, not an API failure.
            return ""

    def has_ingested(self, source_hash: str) -> bool:
        return source_hash in self._load_manifest().values()

    def mark_ingested(self, source_name: str, source_hash: str) -> None:
        manifest = self._load_manifest()
        manifest[source_name] = source_hash
        self._save_manifest(manifest)

    def is_file_ingested(self, path: Path) -> bool:
        """Check if a specific file has been ingested (by content hash)."""
        manifest = self._load_manifest()
        return manifest.get(path.name) == self._hash_file(path)

    def mark_file_ingested(self, path: Path) -> None:
        """Mark a file as ingested using its content hash."""
        self.mark_ingested(path.name, self._hash_file(path))
