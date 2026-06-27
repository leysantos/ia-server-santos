"""Persistência de esqueletos de orçamento (WBS etapas/sub-etapas) — JSON local."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pricing.bootstrap import _DEFAULT_DATA_DIR

_lock = threading.Lock()
_STORE_PATH = _DEFAULT_DATA_DIR / "budget_skeletons.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _default_skeletons() -> list[dict[str, Any]]:
    return [
        {
            "id": "sk-default-rf-quadra",
            "name": "Reforma de quadra",
            "description": "Esqueleto típico para reforma de quadra esportiva municipal.",
            "obra_type": "RF",
            "etapas": [
                {
                    "name": "Serviços preliminares",
                    "sub_etapas": [
                        {"name": "Limpeza e demolições"},
                        {"name": "Instalações provisórias"},
                    ],
                },
                {
                    "name": "Pavimentação e drenagem",
                    "sub_etapas": [
                        {"name": "Terraplenagem"},
                        {"name": "Pavimento"},
                        {"name": "Drenagem superficial"},
                    ],
                },
                {
                    "name": "Cercamento e acessórios",
                    "sub_etapas": [
                        {"name": "Gradil / alambrado"},
                        {"name": "Iluminação"},
                    ],
                },
            ],
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
    ]


def _normalize_etapas(raw: list[Any] | None) -> list[dict[str, Any]]:
    etapas: list[dict[str, Any]] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        sub_etapas: list[dict[str, str]] = []
        for sub in item.get("sub_etapas") or []:
            if isinstance(sub, dict):
                sub_name = str(sub.get("name") or "").strip()
            else:
                sub_name = str(sub).strip()
            if sub_name:
                sub_etapas.append({"name": sub_name})
        etapas.append({"name": name, "sub_etapas": sub_etapas})
    return etapas


def _ensure_store() -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not _STORE_PATH.is_file():
        payload = {"version": 1, "skeletons": _default_skeletons()}
        _STORE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_all_unlocked() -> list[dict[str, Any]]:
    _ensure_store()
    try:
        data = json.loads(_STORE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = {"version": 1, "skeletons": _default_skeletons()}
    skeletons = data.get("skeletons")
    if not isinstance(skeletons, list):
        skeletons = _default_skeletons()
    return skeletons


def _write_all_unlocked(skeletons: list[dict[str, Any]]) -> None:
    _ensure_store()
    payload = {"version": 1, "skeletons": skeletons, "updated_at": _now_iso()}
    tmp = _STORE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_STORE_PATH)


def list_budget_skeletons() -> list[dict[str, Any]]:
    with _lock:
        return list(_read_all_unlocked())


def get_budget_skeleton(skeleton_id: str) -> Optional[dict[str, Any]]:
    with _lock:
        for sk in _read_all_unlocked():
            if sk.get("id") == skeleton_id:
                return dict(sk)
    return None


def create_budget_skeleton(payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("Nome do modelo é obrigatório")
    obra_type = str(payload.get("obra_type") or "RF").strip() or "RF"
    description = str(payload.get("description") or "").strip()
    etapas = _normalize_etapas(payload.get("etapas"))
    now = _now_iso()
    record = {
        "id": str(payload.get("id") or uuid.uuid4().hex[:12]),
        "name": name,
        "description": description,
        "obra_type": obra_type,
        "etapas": etapas,
        "created_at": now,
        "updated_at": now,
    }
    with _lock:
        skeletons = _read_all_unlocked()
        if any(s.get("id") == record["id"] for s in skeletons):
            raise ValueError("ID de esqueleto já existe")
        skeletons.append(record)
        _write_all_unlocked(skeletons)
    return record


def update_budget_skeleton(skeleton_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        skeletons = _read_all_unlocked()
        for idx, sk in enumerate(skeletons):
            if sk.get("id") != skeleton_id:
                continue
            name = str(payload.get("name", sk.get("name")) or "").strip()
            if not name:
                raise ValueError("Nome do modelo é obrigatório")
            updated = {
                **sk,
                "name": name,
                "description": str(payload.get("description", sk.get("description")) or "").strip(),
                "obra_type": str(payload.get("obra_type", sk.get("obra_type")) or "RF").strip() or "RF",
                "etapas": _normalize_etapas(
                    payload.get("etapas") if "etapas" in payload else sk.get("etapas")
                ),
                "updated_at": _now_iso(),
            }
            skeletons[idx] = updated
            _write_all_unlocked(skeletons)
            return dict(updated)
    raise KeyError(f"Esqueleto não encontrado: {skeleton_id}")


def delete_budget_skeleton(skeleton_id: str) -> None:
    with _lock:
        skeletons = _read_all_unlocked()
        next_list = [s for s in skeletons if s.get("id") != skeleton_id]
        if len(next_list) == len(skeletons):
            raise KeyError(f"Esqueleto não encontrado: {skeleton_id}")
        _write_all_unlocked(next_list)


def build_budget_tree_from_skeleton(
    skeleton: dict[str, Any],
    *,
    projeto: str = "",
    obra_type: str | None = None,
) -> tuple[Any, list]:
    """Retorna (metadata, roots) a partir de um esqueleto cadastrado."""
    from pricing.budget.bdi_types import normalize_obra_type
    from pricing.budget.budget_structure import add_etapa, add_subetapa, refresh_calculation_memory
    from pricing.budget.ppd_template import create_empty_ppd_metadata

    sk_name = str(skeleton.get("name") or "NOVO PROJETO")
    sk_obra = normalize_obra_type(obra_type or skeleton.get("obra_type") or "RF")
    meta = create_empty_ppd_metadata(
        projeto=projeto or sk_name,
        objeto=projeto or sk_name,
        obra_type=sk_obra,
    )
    roots: list = []
    for etapa_data in skeleton.get("etapas") or []:
        etapa_name = str(etapa_data.get("name") or "").strip()
        if not etapa_name:
            continue
        etapa = add_etapa(roots, etapa_name, meta)
        for sub in etapa_data.get("sub_etapas") or []:
            sub_name = str(sub.get("name") if isinstance(sub, dict) else sub or "").strip()
            if not sub_name:
                continue
            add_subetapa(roots, etapa.code, sub_name, meta)
        etapa.recompute_total()
    refresh_calculation_memory(roots)
    return meta, roots
