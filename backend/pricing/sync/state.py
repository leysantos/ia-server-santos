"""Persistência do estado de sincronização de bases de preço."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import KNOWLEDGE_DIR

STATE_PATH = KNOWLEDGE_DIR / "pricing_sync_state.json"


@dataclass
class SourceSyncRecord:
    source: str
    status: str = "idle"
    reference: str = ""
    item_count: int = 0
    document_id: str = ""
    path: str = ""
    error: str = ""
    synced_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PriceSyncStateStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or STATE_PATH

    def load(self) -> dict[str, SourceSyncRecord]:
        if not self.path.is_file():
            return {}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return {
            key: SourceSyncRecord(**value) if isinstance(value, dict) else value
            for key, value in (raw.get("sources") or {}).items()
        }

    def save(self, records: dict[str, SourceSyncRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": _now_iso(),
            "sources": {k: v.to_dict() for k, v in records.items()},
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, source: str) -> SourceSyncRecord | None:
        return self.load().get(source.lower())

    def update(self, record: SourceSyncRecord) -> SourceSyncRecord:
        records = self.load()
        record.synced_at = record.synced_at or _now_iso()
        records[record.source.lower()] = record
        self.save(records)
        return record
