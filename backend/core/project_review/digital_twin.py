"""Digital Twin unificado do projeto (Módulo A)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from core.project_review.constants import TWIN_DISCIPLINE_KEYS
from core.project_review.vision_analysis_service import extract_analysis


def empty_twin_payload() -> dict[str, Any]:
    return {key: {} for key in TWIN_DISCIPLINE_KEYS}


def merge_extraction_into_twin(
    twin: dict[str, Any],
    *,
    discipline: str,
    file_id: str,
    filename: str,
    extraction: dict[str, Any],
    vision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Atualiza payload do digital twin com dados extraídos de um arquivo."""
    result = deepcopy(twin) if twin else empty_twin_payload()
    bucket = discipline if discipline in TWIN_DISCIPLINE_KEYS else "documentacao"
    section = result.setdefault(bucket, {})
    docs = section.setdefault("documentos", [])
    docs.append(
        {
            "file_id": file_id,
            "filename": filename,
            "extraction_summary": _summarize_extraction(extraction),
            "vision_summary": _summarize_vision(vision),
        }
    )
    elements = extraction.get("elementos_detectados") or extraction.get("elements") or []
    if elements:
        existing = section.setdefault("elementos", [])
        for el in elements:
            if el not in existing:
                existing.append(el)
    if vision:
        data = extract_analysis(vision)
        for key in ("escala", "pavimento", "area_construida"):
            if data.get(key):
                section[key] = data[key]
    return result


def build_twin_snapshot(
    *,
    project_id: str,
    extractions: list[dict[str, Any]],
    normas: list[str] | None = None,
    version: int = 1,
) -> dict[str, Any]:
    payload = empty_twin_payload()
    disciplinas: set[str] = set()
    documentos: list[dict[str, str]] = []

    for item in extractions:
        disc = item.get("discipline") or "documentacao"
        disciplinas.add(disc)
        documentos.append(
            {"file_id": item["file_id"], "filename": item["filename"], "discipline": disc}
        )
        payload = merge_extraction_into_twin(
            payload,
            discipline=disc,
            file_id=item["file_id"],
            filename=item["filename"],
            extraction=item.get("extraction_json") or {},
            vision=item.get("vision_json"),
        )

    return {
        "project_id": project_id,
        "disciplinas": sorted(disciplinas),
        "elementos": {k: v.get("elementos", []) for k, v in payload.items() if v.get("elementos")},
        "documentos": documentos,
        "normas_aplicaveis": normas or [],
        "payload": payload,
        "versao": version,
    }


def _summarize_extraction(extraction: dict[str, Any]) -> dict[str, Any]:
    if not extraction:
        return {}
    return {
        "text_chars": len(extraction.get("texto", "") or ""),
        "tables": len(extraction.get("tabelas", []) or []),
        "elements": len(extraction.get("elementos_detectados", []) or []),
        "format": extraction.get("format"),
    }


def _summarize_vision(vision: dict[str, Any] | None) -> dict[str, Any]:
    if not vision:
        return {}
    data = extract_analysis(vision)
    return {
        "disciplina": data.get("disciplina") or vision.get("analysis_mode"),
        "elementos": len(data.get("elementos_detectados", []) or []),
        "inconsistencias": len(data.get("inconsistencias", []) or []),
        "analysis_mode": vision.get("analysis_mode"),
    }
