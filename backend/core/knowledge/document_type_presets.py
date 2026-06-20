"""Presets de tipo de documento (rótulo + content_type + disciplina) — configurável via Settings."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any
from uuid import uuid4

from config.settings import KNOWLEDGE_DIR
from core.agent_registry import DISCIPLINE_TO_AGENT
from core.knowledge.content_types import normalize_content_type

PRESETS_PATH = KNOWLEDGE_DIR / "config" / "document_type_presets.json"

_DEFAULT_PRESETS: list[dict[str, Any]] = [
    {
        "id": "normas_pci_cbmam",
        "label": "Normas PCI / CBMAM (Incêndio)",
        "content_type": "nbrs",
        "discipline": "INCÊNDIO",
        "register_price_base": False,
        "register_budget_model": False,
    },
    {
        "id": "instrucoes_pci_cbmam",
        "label": "Instruções Técnicas PCI / CBMAM (Incêndio)",
        "content_type": "nbrs",
        "discipline": "INCÊNDIO",
        "register_price_base": False,
        "register_budget_model": False,
    },
]


class DocumentTypePresetError(ValueError):
    pass


def _slugify_id(label: str) -> str:
    text = unicodedata.normalize("NFKD", label)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[-\s]+", "_", text.strip()).strip("_").lower()
    return text[:64] or f"preset_{uuid4().hex[:8]}"


def _ensure_unique_id(base_id: str, existing_ids: set[str]) -> str:
    if base_id not in existing_ids:
        return base_id
    for i in range(2, 100):
        candidate = f"{base_id}_{i}"
        if candidate not in existing_ids:
            return candidate
    return f"{base_id}_{uuid4().hex[:6]}"


def _validate_preset_data(data: dict[str, Any], *, existing_ids: set[str], current_id: str | None = None) -> dict[str, Any]:
    label = (data.get("label") or "").strip()
    if not label:
        raise DocumentTypePresetError("Informe o nome do tipo de documento")

    raw_id = (data.get("id") or "").strip()
    if raw_id:
        preset_id = re.sub(r"[^\w-]", "_", raw_id.lower())[:64]
    else:
        preset_id = _slugify_id(label)

    if current_id and preset_id != current_id and preset_id in existing_ids:
        raise DocumentTypePresetError(f"ID já em uso: {preset_id}")
    if not current_id and preset_id in existing_ids:
        preset_id = _ensure_unique_id(preset_id, existing_ids)

    discipline = (data.get("discipline") or "").strip().upper()
    if discipline not in DISCIPLINE_TO_AGENT:
        valid = ", ".join(sorted(DISCIPLINE_TO_AGENT))
        raise DocumentTypePresetError(f"Disciplina inválida. Use: {valid}")

    try:
        content_type = normalize_content_type(str(data.get("content_type") or ""))
    except KeyError as exc:
        raise DocumentTypePresetError(str(exc)) from exc

    return {
        "id": preset_id,
        "label": label[:120],
        "content_type": content_type,
        "discipline": discipline,
        "register_price_base": bool(data.get("register_price_base")),
        "register_budget_model": bool(data.get("register_budget_model")),
    }


def _write_presets(presets: list[dict[str, Any]]) -> None:
    PRESETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"presets": presets}
    PRESETS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _seed_if_missing() -> None:
    if PRESETS_PATH.is_file():
        return
    _write_presets(list(_DEFAULT_PRESETS))


def list_presets() -> list[dict[str, Any]]:
    _seed_if_missing()
    try:
        raw = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        _write_presets(list(_DEFAULT_PRESETS))
        raw = {"presets": list(_DEFAULT_PRESETS)}

    presets = raw.get("presets") if isinstance(raw, dict) else raw
    if not isinstance(presets, list):
        presets = list(_DEFAULT_PRESETS)
        _write_presets(presets)

    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in presets:
        if not isinstance(item, dict):
            continue
        try:
            validated = _validate_preset_data(item, existing_ids=seen)
        except DocumentTypePresetError:
            continue
        if validated["id"] in seen:
            continue
        seen.add(validated["id"])
        cleaned.append(validated)

    if not cleaned:
        cleaned = list(_DEFAULT_PRESETS)
        _write_presets(cleaned)

    return cleaned


def get_preset(preset_id: str) -> dict[str, Any] | None:
    return next((p for p in list_presets() if p["id"] == preset_id), None)


def create_preset(data: dict[str, Any]) -> dict[str, Any]:
    presets = list_presets()
    existing_ids = {p["id"] for p in presets}
    preset = _validate_preset_data(data, existing_ids=existing_ids)
    presets.append(preset)
    _write_presets(presets)
    return preset


def update_preset(preset_id: str, data: dict[str, Any]) -> dict[str, Any]:
    presets = list_presets()
    idx = next((i for i, p in enumerate(presets) if p["id"] == preset_id), None)
    if idx is None:
        raise DocumentTypePresetError("Tipo de documento não encontrado")

    existing_ids = {p["id"] for p in presets if p["id"] != preset_id}
    merged = {**presets[idx], **data, "id": preset_id}
    preset = _validate_preset_data(merged, existing_ids=existing_ids, current_id=preset_id)
    presets[idx] = preset
    _write_presets(presets)
    return preset


def delete_preset(preset_id: str) -> dict[str, Any]:
    presets = list_presets()
    target = next((p for p in presets if p["id"] == preset_id), None)
    if target is None:
        raise DocumentTypePresetError("Tipo de documento não encontrado")
    remaining = [p for p in presets if p["id"] != preset_id]
    _write_presets(remaining)
    return target
