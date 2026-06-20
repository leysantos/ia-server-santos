"""
Metadata de documentos — knowledge/raw/documents/

Sidecar: {filename}.knowledge.json (contém id UUID)
Disciplinas e tipos vivem APENAS aqui + catalog.jsonl
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

from core.knowledge.content_types import (
    BASE_KEY_ACCEPTS_CONTENT_TYPES,
    default_content_type_for_discipline,
    infer_content_type_from_filename,
    normalize_content_type,
)
from core.knowledge.disciplines import slug_for_discipline

SIDECAR_SUFFIX = ".knowledge.json"


def sidecar_path(file_path: Path) -> Path:
    return file_path.with_name(file_path.name + SIDECAR_SUFFIX)


def read_metadata(file_path: Path) -> dict[str, Any] | None:
    path = sidecar_path(file_path)
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8", errors="replace").strip()
        if not raw or "\x00" in raw:
            logger.warning("Sidecar vazio/corrompido ignorado: %s", path.name)
            return None
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Sidecar JSON inválido %s: %s", path.name, exc)
        return None


def write_metadata(file_path: Path, payload: dict[str, Any]) -> Path:
    path = sidecar_path(file_path)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def _discipline_list(meta: dict[str, Any] | None, fallback_slug: str | None) -> list[str]:
    if not meta:
        return [fallback_slug] if fallback_slug else []
    if "discipline" in meta:
        raw = meta["discipline"]
        if isinstance(raw, str):
            return [slug_for_discipline(raw)]
        return [slug_for_discipline(str(d)) for d in raw]
    if "discipline_slug" in meta:
        return [slug_for_discipline(str(meta["discipline_slug"]))]
    if "discipline_slugs" in meta:
        return [slug_for_discipline(str(d)) for d in meta["discipline_slugs"]]
    return [fallback_slug] if fallback_slug else []


def resolve_content_type(
    file_path: Path,
    *,
    discipline_slug: str | None = None,
) -> str:
    meta = read_metadata(file_path)
    if meta and meta.get("content_type"):
        return normalize_content_type(str(meta["content_type"]))
    inferred = infer_content_type_from_filename(file_path.name)
    if inferred:
        return inferred
    if discipline_slug:
        return default_content_type_for_discipline(discipline_slug)
    discs = _discipline_list(meta, discipline_slug)
    if discs:
        return default_content_type_for_discipline(discs[0])
    return "tdrs"


def file_matches_base(
    file_path: Path,
    base_key: str,
    *,
    discipline_slug: str | None = None,
) -> bool:
    meta = read_metadata(file_path)
    content_type = resolve_content_type(
        file_path,
        discipline_slug=discipline_slug or (meta and meta.get("discipline_slug")),
    )
    accepted = BASE_KEY_ACCEPTS_CONTENT_TYPES.get(base_key, frozenset())
    return content_type in accepted


def file_matches_discipline(
    file_path: Path,
    discipline_slug: str,
) -> bool:
    meta = read_metadata(file_path)
    discs = _discipline_list(meta, None)
    if not discs:
        return True  # sem metadata → indexador usa content_type only
    target = slug_for_discipline(discipline_slug)
    return target in discs


def build_metadata_record(
    *,
    discipline_slugs: list[str],
    layer: str,
    content_type: str,
    source: str,
    confidence: float,
    filename: str | None = None,
    doc_id: str | None = None,
    name: str | None = None,
    description: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    slugs = [slug_for_discipline(d) for d in discipline_slugs if d]
    if not slugs:
        slugs = ["geral"]
    display_name = (name or "").strip() or (filename or "")
    record: dict[str, Any] = {
        "id": doc_id or str(uuid.uuid4()),
        "name": display_name,
        "description": (description or "").strip(),
        "filename": filename or "",
        "discipline": slugs,
        "layer": layer,
        "content_type": normalize_content_type(content_type),
        "source": source,
        "confidence": confidence,
        "tags": [],
    }
    # compat campos legados
    record["discipline_slug"] = slugs[0]
    record["discipline_slugs"] = slugs
    if extra:
        record.update(extra)
    return record
