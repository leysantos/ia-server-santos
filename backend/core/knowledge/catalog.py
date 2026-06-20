"""
Catálogo central de documentos — knowledge/catalog.jsonl

Um registro por arquivo ingerido. Tipos e disciplina ficam aqui (e no sidecar opcional),
não em subpastas do filesystem.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import KNOWLEDGE_DIR

logger = logging.getLogger(__name__)

CATALOG_PATH = KNOWLEDGE_DIR / "catalog.jsonl"


def append_catalog_entry(record: dict[str, Any]) -> None:
    """Append-only — fonte de verdade para ingestão."""
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        **record,
        "catalog_ts": datetime.now(timezone.utc).isoformat(),
    }
    with open(CATALOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _parse_catalog_line(line: str, line_no: int) -> dict[str, Any] | None:
    cleaned = line.strip("\ufeff").strip()
    if not cleaned:
        return None
    if "\x00" in cleaned:
        logger.warning("catalog.jsonl linha %s ignorada (bytes nulos)", line_no)
        return None
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.warning("catalog.jsonl linha %s inválida: %s", line_no, exc)
        return None


def read_catalog(*, repair: bool = True) -> list[dict[str, Any]]:
    if not CATALOG_PATH.is_file():
        return []

    rows: list[dict[str, Any]] = []
    raw_lines = CATALOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    dropped = 0

    for line_no, line in enumerate(raw_lines, start=1):
        parsed = _parse_catalog_line(line, line_no)
        if parsed is None:
            if line.strip():
                dropped += 1
            continue
        rows.append(parsed)

    if repair and dropped:
        rewrite_catalog(rows)
        logger.info("catalog.jsonl reparado — %s linha(s) inválida(s) removida(s)", dropped)

    return rows


def rewrite_catalog(rows: list[dict[str, Any]]) -> None:
    """Substitui o catálogo inteiro (ex.: após exclusão de documento)."""
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def remove_catalog_entries_by_id(document_id: str) -> int:
    rows = read_catalog()
    kept = [row for row in rows if row.get("id") != document_id]
    removed = len(rows) - len(kept)
    if removed:
        rewrite_catalog(kept)
    return removed
