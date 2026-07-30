"""API — OrçaFacil (submódulo Orçamento)."""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.auth.dependencies import get_current_user
from core.database.connection import get_db
from core.database.models import User
from pricing.budget.orca_facil import job_store
from pricing.budget.orca_facil.pipeline import (
    enrich_plan_prices,
    rewrite_workbook_from_plan,
    run_orca_facil_job,
    _build_preview,
)

router = APIRouter(prefix="/budget/orca-facil", tags=["OrçaFacil"])

_PROCESS_LOCK = threading.Lock()
_PROCESSING: set[str] = set()
_BASE_INDEX_CACHE: dict[str, Any] = {}


def _resolve_modelo_path(job: dict[str, Any]) -> Path:
    modelo = (job.get("files") or {}).get("modelo")
    if not modelo:
        raise HTTPException(status_code=400, detail="Planilha modelo não enviada")
    path = Path(str(modelo))
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Arquivo modelo não encontrado no job")
    return path


def _base_index_for_job(job_id: str, job: dict[str, Any]):
    from pricing.budget.orca_facil.base_index import build_base_index_from_model

    path = _resolve_modelo_path(job)
    mtime = path.stat().st_mtime
    cache_key = f"{job_id}:{mtime}"
    cached = _BASE_INDEX_CACHE.get(cache_key)
    if cached is not None:
        return cached
    index = build_base_index_from_model(path)
    if index.size == 0:
        raise HTTPException(status_code=400, detail="Base de preços não encontrada no modelo")
    _BASE_INDEX_CACHE.clear()
    _BASE_INDEX_CACHE[cache_key] = index
    return index


class OrcaFacilJobCreate(BaseModel):
    title: str = "OrçaFacil"
    premissas: dict[str, Any] = Field(default_factory=dict)
    etapas_seed: list[dict[str, Any]] = Field(default_factory=list)
    user_prompt: str = ""
    skeleton_id: Optional[str] = None
    skeleton_name: Optional[str] = None


class OrcaFacilJobUpdate(BaseModel):
    title: Optional[str] = None
    premissas: Optional[dict[str, Any]] = None
    etapas_seed: Optional[list[dict[str, Any]]] = None
    user_prompt: Optional[str] = None
    skeleton_id: Optional[str] = None
    skeleton_name: Optional[str] = None


class OrcaFacilPlanPatch(BaseModel):
    """Árvore MCQ editada no editor próprio do OrçaFacil."""

    stages: list[dict[str, Any]] = Field(default_factory=list)
    rewrite_workbook: bool = True


def _user_id(user: User | None) -> str | None:
    return str(user.id) if user else None


def _run_job(job_id: str) -> None:
    try:
        run_orca_facil_job(job_id)
    except Exception as exc:
        try:
            job_store.update_job(job_id, status="error", error=str(exc))
            job_store.append_event(job_id, "error", 0, str(exc))
        except Exception:
            pass
    finally:
        with _PROCESS_LOCK:
            _PROCESSING.discard(job_id)


@router.post("/jobs/{job_id}/export/xlsm")
def export_job_xlsm(
    job_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """Baixa a CÓPIA do modelo .xlsm preenchida (entregável principal). Fallback: export genérico."""
    from app.services.budget_db_service import get_budget, session_from_payload
    from pricing.budget.budget_session import SESSION_STORE
    from pricing.budget.ppd_workbook_service import get_workbook_bytes, sync_workbook

    _ = db
    _ = user
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    # 1) Preferir workbook gerado a partir do modelo anexado
    wb_path = job.get("workbook_path")
    if wb_path and Path(wb_path).is_file():
        content = Path(wb_path).read_bytes()
        slug = str(job.get("title") or "OrcaFacil").replace(" ", "_")[:50]
        filename = f"{slug}_MODELO.xlsm"
        return Response(
            content=content,
            media_type="application/vnd.ms-excel.sheet.macroEnabled.12",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # 2) Fallback legado (template genérico do sistema) — marcado como secundário
    session_id = job.get("session_id")
    budget_id = job.get("budget_document_id")
    session = SESSION_STORE.get(session_id) if session_id else None

    if session is None and budget_id:
        saved = get_budget(db, str(budget_id), user=user)
        if not saved:
            raise HTTPException(status_code=404, detail="Orçamento salvo não encontrado")
        session_from_payload(saved)
        session_id = saved.get("session_id")
        session = SESSION_STORE.get(session_id)

    if not session_id or session is None:
        raise HTTPException(
            status_code=404,
            detail="Planilha modelo não gerada — execute Gerar novamente",
        )

    try:
        sync_workbook(session_id)
        content = get_workbook_bytes(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha no export .xlsm: {exc}") from exc

    slug = str(job.get("title") or "OrcaFacil").replace(" ", "_")[:40]
    filename = f"PPD_{slug}_{str(session_id)[:8]}_FALLBACK.xlsm"
    return Response(
        content=content,
        media_type="application/vnd.ms-excel.sheet.macroEnabled.12",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/jobs")
def create_job(
    body: OrcaFacilJobCreate,
    user: User | None = Depends(get_current_user),
):
    job = job_store.create_job(
        title=body.title,
        premissas=body.premissas or None,
        etapas_seed=body.etapas_seed or None,
        user_prompt=body.user_prompt or "",
        user_id=_user_id(user),
    )
    if body.skeleton_id or body.skeleton_name:
        job = job_store.update_job(
            str(job["id"]),
            skeleton_id=body.skeleton_id,
            skeleton_name=body.skeleton_name,
        )
    return job


@router.get("/jobs")
def list_jobs(limit: int = 40, summary: bool = False, user: User | None = Depends(get_current_user)):
    _ = user
    if summary:
        jobs = job_store.list_jobs(limit=limit)
        out = []
        for j in jobs:
            preview = j.get("preview") or {}
            if (preview.get("bdi_rate_comd") is None or preview.get("total_comd") is None) and j.get("plan"):
                j = _ensure_job_prices(str(j["id"]), j)
            out.append(job_store.job_list_item(j))
        return {"jobs": out}
    return {"jobs": job_store.list_jobs(limit=limit)}


def _job_obra_type(job: dict[str, Any]) -> str:
    prem = job.get("premissas") or {}
    info = job.get("project_info") or {}
    return str(info.get("obra_type") or prem.get("obra_type") or "ED")


def _ensure_job_prices(job_id: str, job: dict[str, Any]) -> dict[str, Any]:
    """Enriquece plan com preços da base do modelo e atualiza preview (jobs antigos inclusos)."""
    plan = job.get("plan")
    if not isinstance(plan, dict) or not plan.get("stages"):
        return job
    needs_prices = False
    for st in plan.get("stages") or []:
        for it in st.get("items") or []:
            if it.get("code") and (it.get("price_comd") is None or it.get("price_semd") is None):
                needs_prices = True
                break
        if needs_prices:
            break
    preview = job.get("preview") or {}
    needs_bdi_preview = preview.get("bdi_rate_comd") is None
    if not needs_prices and not needs_bdi_preview and preview.get("total_comd") is not None:
        return job
    try:
        if needs_prices:
            index = _base_index_for_job(job_id, job)
            if index.size == 0 and needs_prices:
                return job
            if index.size:
                enrich_plan_prices(plan, index)
        new_preview = _build_preview(plan, None, obra_type=_job_obra_type(job))
        for k in ("workbook_n_servicos", "workbook_n_etapas"):
            if preview.get(k) is not None:
                new_preview[k] = preview[k]
        return job_store.update_job(job_id, plan=plan, preview=new_preview)
    except Exception:
        return job


@router.get("/jobs/{job_id}")
def get_job(job_id: str, user: User | None = Depends(get_current_user)):
    _ = user
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    return _ensure_job_prices(job_id, job)


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str, user: User | None = Depends(get_current_user)):
    _ = user
    if not job_store.get_job(job_id):
        raise HTTPException(status_code=404, detail="Job não encontrado")
    job_store.delete_job(job_id)
    return {"deleted": job_id}


@router.get("/jobs/{job_id}/base-search")
def search_base_compositions(
    job_id: str,
    q: str = "",
    top_k: int = 20,
    user: User | None = Depends(get_current_user),
):
    """Busca composições na base indexada da planilha modelo (código ou descrição)."""
    _ = user
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    query = (q or "").strip()
    if len(query) < 1:
        return {"hits": [], "query": query, "base_size": 0}
    index = _base_index_for_job(job_id, job)
    hits = []
    for row, score in index.search_base(query, top_k=min(max(top_k, 1), 50)):
        hits.append(
            {
                "code": row.code,
                "description": row.description,
                "unit": row.unit,
                "price_comd": row.price_comd,
                "price_semd": row.price_semd,
                "score": round(score, 2),
            }
        )
    return {
        "hits": hits,
        "query": query,
        "base_size": index.size,
        "sheet_name": index.sheet_name,
    }


@router.patch("/jobs/{job_id}")
def update_job(
    job_id: str,
    body: OrcaFacilJobUpdate,
    user: User | None = Depends(get_current_user),
):
    _ = user
    if not job_store.get_job(job_id):
        raise HTTPException(status_code=404, detail="Job não encontrado")
    fields: dict[str, Any] = {}
    if body.title is not None:
        fields["title"] = body.title
    if body.premissas is not None:
        fields["premissas"] = body.premissas
    if body.etapas_seed is not None:
        fields["etapas_seed"] = body.etapas_seed
    if body.user_prompt is not None:
        fields["user_prompt"] = body.user_prompt
    if body.skeleton_id is not None:
        fields["skeleton_id"] = body.skeleton_id
    if body.skeleton_name is not None:
        fields["skeleton_name"] = body.skeleton_name
    return job_store.update_job(job_id, **fields)


@router.put("/jobs/{job_id}/plan")
def put_plan(
    job_id: str,
    body: OrcaFacilPlanPatch,
    user: User | None = Depends(get_current_user),
):
    """Atualiza o plano MCQ e regrava a planilha modelo (editor próprio OrçaFacil)."""
    _ = user
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if job.get("status") not in ("ready", "error", "created", "running"):
        raise HTTPException(status_code=400, detail="Job em estado inválido para edição")

    plan = dict(job.get("plan") or {})
    plan["stages"] = body.stages
    plan["edited"] = True
    try:
        index = _base_index_for_job(job_id, job)
        if index.size:
            enrich_plan_prices(plan, index)
    except Exception:
        pass
    preview = _build_preview(plan, None, obra_type=_job_obra_type(job))
    old_preview = job.get("preview") or {}
    for k in ("workbook_n_servicos", "workbook_n_etapas"):
        if old_preview.get(k) is not None:
            preview[k] = old_preview[k]
    job_store.update_job(job_id, plan=plan, preview=preview, status="ready")

    if body.rewrite_workbook:
        try:
            return rewrite_workbook_from_plan(job_id)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Falha ao regravar modelo: {exc}") from exc
    return job_store.get_job(job_id)


@router.post("/jobs/{job_id}/upload")
async def upload_files(
    job_id: str,
    kind: str = Form(...),
    files: list[UploadFile] = File(...),
    user: User | None = Depends(get_current_user),
):
    _ = user
    if not job_store.get_job(job_id):
        raise HTTPException(status_code=404, detail="Job não encontrado")
    kind = kind.strip().lower()
    if kind not in ("modelo", "exemplo", "pranchas", "fotos"):
        raise HTTPException(status_code=400, detail="kind inválido")
    if kind in ("modelo", "exemplo") and len(files) != 1:
        raise HTTPException(status_code=400, detail=f"Envie exatamente 1 arquivo para {kind}")

    saved = []
    for uf in files:
        data = await uf.read()
        if not data:
            continue
        path = job_store.save_upload(job_id, kind, uf.filename or "file.bin", data)
        job = job_store.register_file(job_id, kind, path)
        saved.append({"name": path.name, "path": str(path), "kind": kind})
    job = job_store.get_job(job_id)
    return {"job": job, "saved": saved}


@router.post("/jobs/{job_id}/process")
def process_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    async_mode: bool = True,
    user: User | None = Depends(get_current_user),
):
    _ = user
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if not (job.get("files") or {}).get("modelo"):
        raise HTTPException(status_code=400, detail="Envie a planilha modelo antes de processar")

    with _PROCESS_LOCK:
        if job_id in _PROCESSING:
            return {**job, "status": "running", "message": "Já em processamento"}
        _PROCESSING.add(job_id)

    if async_mode:
        background_tasks.add_task(_run_job, job_id)
        job_store.update_job(job_id, status="running")
        job_store.append_event(job_id, "ingest", 1, "Processamento iniciado…")
        return job_store.get_job(job_id)

    try:
        return run_orca_facil_job(job_id)
    finally:
        with _PROCESS_LOCK:
            _PROCESSING.discard(job_id)


@router.get("/jobs/{job_id}/events")
async def stream_events(job_id: str, user: User | None = Depends(get_current_user)):
    """SSE leve — emite progresso até ready/error."""
    _ = user
    if not job_store.get_job(job_id):
        raise HTTPException(status_code=404, detail="Job não encontrado")

    async def gen():
        last_len = 0
        idle = 0
        while idle < 180:
            job = job_store.get_job(job_id) or {}
            events = job.get("events") or []
            if len(events) > last_len:
                for ev in events[last_len:]:
                    payload = {
                        "phase": ev.get("phase"),
                        "progress": ev.get("progress"),
                        "message": ev.get("message"),
                        "status": job.get("status"),
                        "session_id": job.get("session_id"),
                        "budget_document_id": job.get("budget_document_id"),
                    }
                    yield f"event: progress\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                last_len = len(events)
                idle = 0
            status = job.get("status")
            if status in ("ready", "error"):
                yield (
                    "event: done\ndata: "
                    + json.dumps(
                        {
                            "status": status,
                            "session_id": job.get("session_id"),
                            "budget_document_id": job.get("budget_document_id"),
                            "error": job.get("error"),
                            "preview": job.get("preview"),
                        },
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )
                break
            await asyncio.sleep(0.8)
            idle += 1

    return StreamingResponse(gen(), media_type="text/event-stream")
