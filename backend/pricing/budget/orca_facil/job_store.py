"""OF3 — store leve de jobs OrçaFacil (disco + memória)."""

from __future__ import annotations

import json
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pricing.bootstrap import _DEFAULT_DATA_DIR

_ROOT = _DEFAULT_DATA_DIR / "orca_facil"
_LOCK = threading.RLock()
_JOBS: dict[str, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_dir(job_id: str) -> Path:
    d = _ROOT / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _meta_path(job_id: str) -> Path:
    return _job_dir(job_id) / "job.json"


class _SafeEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if hasattr(o, "hex"):
            return str(o)
        return super().default(o)


def _persist(job: dict[str, Any]) -> None:
    path = _meta_path(str(job["id"]))
    path.write_text(json.dumps(job, ensure_ascii=False, indent=2, cls=_SafeEncoder), encoding="utf-8")


def create_job(
    *,
    title: str = "OrçaFacil",
    premissas: dict[str, Any] | None = None,
    etapas_seed: list[dict[str, Any]] | None = None,
    user_prompt: str = "",
    user_id: Any = None,
) -> dict[str, Any]:
    job_id = uuid.uuid4().hex[:16]
    job = {
        "id": job_id,
        "title": title,
        "status": "created",
        "phase": "created",
        "progress": 0,
        "message": "Job criado — envie o modelo e os arquivos do projeto",
        "created_at": _now(),
        "updated_at": _now(),
        "user_id": user_id,
        "files": {
            "modelo": None,
            "exemplo": None,
            "pranchas": [],
            "fotos": [],
        },
        "premissas": premissas
        or {
            "prazo_meses": 6,
            "dmt_jazida_km": 30.0,
            "dmt_bota_km": 30.0,
            "empolamento": 1.30,
            "area_intervencao_m2": None,
            "area_grama_m2": None,
            "obra_type": "ED",
        },
        "etapas_seed": etapas_seed or [],
        "user_prompt": user_prompt or "",
        "skeleton_id": None,
        "skeleton_name": None,
        "base_summary": None,
        "example_summary": None,
        "project_info": None,
        "quantities": [],
        "plan": None,
        "warnings": [],
        "session_id": None,
        "budget_document_id": None,
        "workbook_path": None,
        "workbook_stats": None,
        "preview": None,
        "gemini_model": None,
        "error": None,
        "events": [],
    }
    with _LOCK:
        _JOBS[job_id] = job
        _persist(job)
    return dict(job)


def get_job(job_id: str) -> dict[str, Any] | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if job:
            return dict(job)
    path = _meta_path(job_id)
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        with _LOCK:
            _JOBS[job_id] = data
        return dict(data)
    return None


def list_jobs(*, limit: int = 40) -> list[dict[str, Any]]:
    _ROOT.mkdir(parents=True, exist_ok=True)
    ids = {p.name for p in _ROOT.iterdir() if p.is_dir()}
    with _LOCK:
        ids |= set(_JOBS.keys())
    out: list[dict[str, Any]] = []
    for jid in ids:
        job = get_job(jid)
        if job:
            out.append(job)
    out.sort(key=lambda j: j.get("updated_at") or j.get("created_at") or "", reverse=True)
    return out[:limit]


def delete_job(job_id: str) -> None:
    """Remove job da memória e apaga diretório em disco."""
    with _LOCK:
        _JOBS.pop(job_id, None)
    path = _ROOT / job_id
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)


def job_list_item(job: dict[str, Any]) -> dict[str, Any]:
    """Resumo leve para listagem na UI."""
    preview = job.get("preview") or {}
    files = job.get("files") or {}
    modelo = files.get("modelo")
    total_comd = preview.get("total_comd")
    total_semd = preview.get("total_semd")
    # Fallback: calcular a partir do plan com BDI (paridade planilha) se preview antigo
    if total_comd is None or total_semd is None or preview.get("bdi_rate_comd") is None:
        from pricing.budget.orca_facil.pipeline import _build_preview

        prem = job.get("premissas") or {}
        info = job.get("project_info") or {}
        obra = str(info.get("obra_type") or prem.get("obra_type") or "ED")
        plan = job.get("plan") or {}
        if plan.get("stages"):
            rebuilt = _build_preview(plan, None, obra_type=obra)
            total_comd = rebuilt.get("total_comd")
            total_semd = rebuilt.get("total_semd")
        else:
            total_comd = total_comd if total_comd is not None else 0.0
            total_semd = total_semd if total_semd is not None else 0.0
    return {
        "id": job.get("id"),
        "title": job.get("title") or "OrçaFacil",
        "status": job.get("status"),
        "updated_at": job.get("updated_at"),
        "created_at": job.get("created_at"),
        "n_etapas": preview.get("n_etapas") or preview.get("workbook_n_etapas"),
        "n_services": preview.get("n_services") or preview.get("workbook_n_servicos"),
        "total_comd": total_comd,
        "total_semd": total_semd,
        "bdi_obra_type": preview.get("bdi_obra_type"),
        "bdi_rate_comd": preview.get("bdi_rate_comd"),
        "bdi_rate_semd": preview.get("bdi_rate_semd"),
        "has_workbook": bool(job.get("workbook_path")),
        "has_modelo": bool(modelo),
        "modelo_name": Path(str(modelo)).name if modelo else None,
        "skeleton_name": job.get("skeleton_name"),
    }


def list_job_summaries(*, limit: int = 80) -> list[dict[str, Any]]:
    return [job_list_item(j) for j in list_jobs(limit=limit)]


def update_job(job_id: str, **fields: Any) -> dict[str, Any]:
    with _LOCK:
        job = get_job(job_id)
        if not job:
            raise KeyError(job_id)
        job.update(fields)
        job["updated_at"] = _now()
        _JOBS[job_id] = job
        _persist(job)
        return dict(job)


def append_event(job_id: str, phase: str, progress: int, message: str) -> dict[str, Any]:
    with _LOCK:
        job = get_job(job_id)
        if not job:
            raise KeyError(job_id)
        events = list(job.get("events") or [])
        events.append(
            {
                "at": _now(),
                "phase": phase,
                "progress": progress,
                "message": message,
            }
        )
        job["events"] = events[-80:]
        job["phase"] = phase
        job["progress"] = progress
        job["message"] = message
        job["updated_at"] = _now()
        _JOBS[job_id] = job
        _persist(job)
        return dict(job)


def save_upload(job_id: str, kind: str, filename: str, data: bytes) -> Path:
    safe = Path(filename or "upload.bin").name
    dest_dir = _job_dir(job_id) / kind
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / safe
    dest.write_bytes(data)
    return dest


def register_file(job_id: str, kind: str, path: Path) -> dict[str, Any]:
    with _LOCK:
        job = get_job(job_id)
        if not job:
            raise KeyError(job_id)
        files = dict(job.get("files") or {})
        rel = str(path)
        if kind in ("modelo", "exemplo"):
            files[kind] = rel
        elif kind in ("pranchas", "fotos"):
            lst = list(files.get(kind) or [])
            lst.append(rel)
            files[kind] = lst
        else:
            raise ValueError(f"kind inválido: {kind}")
        job["files"] = files
        job["updated_at"] = _now()
        _JOBS[job_id] = job
        _persist(job)
        return dict(job)
