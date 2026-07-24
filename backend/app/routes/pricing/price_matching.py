"""API — módulo Lançar Preços (importação, matching, exportação)."""

from __future__ import annotations

import shutil
import threading
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.auth.dependencies import get_current_user
from core.database.connection import get_db
from core.database.models import User
from pricing.bootstrap import _DEFAULT_DATA_DIR
from pricing.budget.price_matching_catalog import search_catalog
from pricing.budget.price_matching_export import export_price_matching_pdf, export_price_matching_xlsx
from pricing.budget.price_matching_hierarchy import (
    ImportRowKind,
    hierarchy_stats,
    parse_excel_hierarchy,
)
from pricing.budget.price_matching_budget import (
    build_budget_from_hierarchy,
    build_budget_session_from_job,
    ensure_job_price_bases_persisted,
    merge_job_price_bases,
    resolve_price_matching_session,
    sync_and_persist_job_budget,
    sync_priced_rows_to_session,
)
from app.services.budget_db_service import (
    delete_budget as remove_budget_document,
    get_budget,
    save_budget,
    session_from_payload,
)
from pricing.budget.budget_session import SESSION_STORE
from pricing.budget.price_matching_store import STORE, _set_job_progress

router = APIRouter(prefix="/budget/price-matching", tags=["Budget Price Matching"])

_IMPORT_DIR = _DEFAULT_DATA_DIR / "price_matching"
_PROCESS_LOCK = threading.Lock()
_PROCESSING: set[str] = set()


def _user_ctx(user: User | None) -> tuple[Any, str | None]:
    if user is None:
        return None, None
    return user.id, user.email or user.username


class PriceMatchingJobCreate(BaseModel):
    title: str = "Lançar Preços"
    bdi: float = Field(default=0.0, ge=0.0, le=5.0)
    increase_index: float = Field(default=1.0, ge=0.1, le=10.0)
    uf: str = "AM"
    cliente: Optional[str] = None
    obra: Optional[str] = None


class PriceMatchingJobUpdate(BaseModel):
    bdi: Optional[float] = Field(default=None, ge=0.0, le=5.0)
    increase_index: Optional[float] = Field(default=None, ge=0.1, le=10.0)
    cliente: Optional[str] = None
    obra: Optional[str] = None
    uf: Optional[str] = None
    price_bases: Optional[list[dict[str, Any]]] = None


class PriceMatchingReplaceRequest(BaseModel):
    base: str
    code: str
    reference: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    price: Optional[float] = None
    source: Optional[str] = None


class PriceMatchingSaveBudgetRequest(BaseModel):
    payload: Optional[dict[str, Any]] = None
    title: Optional[str] = None
    expected_version: Optional[int] = None


def _run_process(job_id: str, use_llm: bool, usuario: str | None) -> None:
    from core.database.connection import SessionLocal, is_db_enabled

    try:
        if is_db_enabled():
            db = SessionLocal()
            try:
                STORE.process_job(db, job_id, use_llm=use_llm, usuario=usuario)
            finally:
                db.close()
        else:
            STORE.process_job(None, job_id, use_llm=use_llm, usuario=usuario)
    finally:
        with _PROCESS_LOCK:
            _PROCESSING.discard(job_id)


def _run_sync_job_budget(job_id: str, user_id: int | None) -> None:
    """Sincroniza preços do job na sessão PPD em background (replace/accept)."""
    from core.database.connection import SessionLocal, is_db_enabled
    from core.database.models import User

    if not is_db_enabled():
        return
    db = SessionLocal()
    try:
        job = STORE.get_job(db, job_id)
        if not job:
            return
        user = db.get(User, user_id) if user_id else None
        try:
            sync_and_persist_job_budget(db, job, user=user)
        except KeyError:
            pass
    finally:
        db.close()


@router.post("/jobs")
def create_price_matching_job(
    body: PriceMatchingJobCreate,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    uid, _ = _user_ctx(user)
    job = STORE.create_job(
        db,
        title=body.title,
        bdi=body.bdi,
        increase_index=body.increase_index,
        uf=body.uf,
        cliente=body.cliente,
        obra=body.obra,
        user_id=uid,
        empresa_id=None,
    )
    return job


@router.post("/import")
async def import_price_matching_file(
    file: UploadFile = File(...),
    bdi: float = Query(default=0.0, ge=0.0, le=5.0),
    increase_index: float = Query(default=1.0, ge=0.1, le=10.0),
    uf: str = Query(default="AM"),
    cliente: Optional[str] = Query(default=None),
    obra: Optional[str] = Query(default=None),
    price_bases: Optional[str] = Query(default=None, description="JSON array de bases selecionadas"),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """Importa planilha Excel (.xlsx) com etapas, sub-etapas e composições."""
    suffix = Path(file.filename or "planilha.xlsx").suffix.lower()
    if suffix == ".xls":
        raise HTTPException(
            status_code=400,
            detail="Formato .xls legado não suportado. Salve a planilha como .xlsx.",
        )
    if suffix != ".xlsx":
        raise HTTPException(
            status_code=400,
            detail="Formato não suportado. Use planilha Excel (.xlsx) com colunas Item, Descrição, Und e Quantidade.",
        )

    _IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    dest = _IMPORT_DIR / (file.filename or f"import{suffix}")
    with dest.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)

    try:
        uid, usuario = _user_ctx(user)
        parsed_price_bases: list[dict[str, Any]] | None = None
        if price_bases:
            import json

            raw = json.loads(price_bases)
            if isinstance(raw, list):
                parsed_price_bases = raw

        hierarchy_lines = parse_excel_hierarchy(dest)
        hierarchy_payload = [
            {
                "item": ln.item,
                "codigo": ln.codigo,
                "descricao": ln.descricao,
                "unidade": ln.unidade,
                "quantidade": ln.quantidade,
                "row_type": ln.row_type,
                "row_index": ln.row_index,
                "incomplete": ln.incomplete,
            }
            for ln in hierarchy_lines
        ]
        job_meta = {
            "bdi": bdi,
            "increase_index": increase_index,
            "uf": uf.upper(),
            "cliente": cliente,
            "obra": obra,
            "title": obra or file.filename,
            "price_bases": parsed_price_bases or [],
        }
        session_dict = build_budget_from_hierarchy(hierarchy_lines, job_meta)
        fmt = "xlsx"

        if not hierarchy_lines:
            raise HTTPException(
                status_code=400,
                detail="Nenhuma linha reconhecida na planilha. Verifique colunas Item, Descrição, Und e Quantidade.",
            )

        saved = save_budget(
            db,
            session_dict,
            title=str(obra or session_dict.get("title") or "Orçamento importado"),
            user=user,
        )
        session_dict = saved
        session_from_payload(saved)

        job = STORE.create_job(
            db,
            bdi=bdi,
            increase_index=increase_index,
            uf=uf.upper(),
            cliente=cliente,
            obra=obra,
            source_filename=file.filename,
            source_format=fmt,
            user_id=uid,
            empresa_id=None,
            budget_document_id=uuid.UUID(str(saved["db_id"])),
            session_id=session_dict.get("session_id"),
            hierarchy=hierarchy_payload,
            price_bases=parsed_price_bases,
        )

        service_rows = [
            ln.to_price_row()
            for ln in (hierarchy_lines or [])
            if ln.row_type == ImportRowKind.SERVICO.value
        ]
        imported = STORE.add_import_rows(db, job["id"], service_rows, usuario=usuario)
        payload = STORE.get_job(db, job["id"]) or job
        payload["imported_count"] = len(imported)
        payload["session"] = session_dict
        payload["budget_id"] = saved.get("db_id")
        payload["hierarchy_stats"] = hierarchy_stats(hierarchy_lines or [])
        return payload
    except (ValueError, ImportError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/jobs")
def list_price_matching_jobs(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """Lista jobs de lançamento de preços (histórico)."""
    uid, _ = _user_ctx(user)
    return {"jobs": STORE.list_jobs(db, limit=limit, user_id=uid)}


@router.get("/jobs/{job_id}")
def get_price_matching_job(
    job_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    job = STORE.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    from pricing.budget.price_matching_budget import sync_hierarchy_codes_from_rows

    job = sync_hierarchy_codes_from_rows(job)
    session_dict: dict[str, Any] | None = None
    budget_id = job.get("budget_document_id")
    if budget_id and not (job.get("price_bases") or []):
        saved = get_budget(db, str(budget_id), user=user)
        if saved:
            session_dict = saved
            session_from_payload(saved)
    job = ensure_job_price_bases_persisted(db, job_id, job, session_dict)
    return job


@router.get("/jobs/{job_id}/session")
def get_price_matching_session(
    job_id: str,
    sync_prices: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """Retorna sessão PPD vinculada ao job (banco ou memória)."""
    job = STORE.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    from pricing.budget.price_matching_budget import sync_hierarchy_codes_from_rows

    job = sync_hierarchy_codes_from_rows(job)
    session_dict = resolve_price_matching_session(db, job, user=user, sync_prices=sync_prices)
    job = STORE.get_job(db, job_id) or job
    job = ensure_job_price_bases_persisted(db, job_id, job, session_dict)
    job = STORE.get_job(db, job_id) or job
    budget_id = job.get("budget_document_id") or session_dict.get("db_id")
    return {
        "session": session_dict,
        "job": job,
        "budget_id": str(budget_id) if budget_id else None,
    }


@router.post("/jobs/{job_id}/save-budget")
def save_price_matching_budget(
    job_id: str,
    body: PriceMatchingSaveBudgetRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """Persiste orçamento vinculado ao job de lançamento de preços."""
    job = STORE.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    session_id = job.get("session_id")
    if body.payload:
        session_payload = dict(body.payload)
    elif session_id:
        session = SESSION_STORE.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Sessão não encontrada")
        session_payload = session.to_dict()
    else:
        raise HTTPException(status_code=400, detail="Job sem sessão vinculada")

    job_bases = list(job.get("price_bases") or [])
    if job_bases:
        project = dict(session_payload.get("project") or {})
        project["price_bases"] = job_bases
        session_payload = {**session_payload, "project": project}
        if session_id:
            live = SESSION_STORE.get(session_id)
            if live:
                live.project.price_bases = job_bases

    budget_id = job.get("budget_document_id")
    title = body.title or session_payload.get("title") or job.get("obra") or "Orçamento importado"
    try:
        saved = save_budget(
            db,
            session_payload,
            title=title,
            budget_id=str(budget_id) if budget_id else None,
            user=user,
            expected_version=body.expected_version,
        )
    except Exception as exc:
        from app.services.budget_db_service import BudgetVersionConflictError

        if isinstance(exc, BudgetVersionConflictError):
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session_from_payload(saved)
    if not budget_id:
        STORE.link_budget(
            db,
            job_id,
            budget_document_id=str(saved.get("db_id")),
            session_id=saved.get("session_id"),
        )

    project = saved.get("project") or session_payload.get("project") or {}
    price_bases = list(project.get("price_bases") or [])
    if price_bases:
        STORE.update_job_meta(db, job_id, price_bases=price_bases)

    return {"session": saved, "job_id": job_id, "budget_id": saved.get("db_id")}


@router.delete("/jobs/{job_id}")
def delete_price_matching_job(
    job_id: str,
    delete_budget_doc: bool = Query(default=True, alias="delete_budget"),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """Remove job de lançamento de preços e, opcionalmente, o orçamento vinculado."""
    job = STORE.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    budget_id = job.get("budget_document_id")
    if delete_budget_doc and budget_id:
        remove_budget_document(db, str(budget_id), user=user)

    session_id = job.get("session_id")
    if session_id and session_id in SESSION_STORE._sessions:  # noqa: SLF001
        SESSION_STORE._sessions.pop(session_id, None)  # noqa: SLF001

    if not STORE.delete_job(db, job_id):
        raise HTTPException(status_code=404, detail="Job não encontrado")
    return {
        "deleted": True,
        "job_id": job_id,
        "budget_deleted": bool(delete_budget_doc and budget_id),
    }


@router.patch("/jobs/{job_id}")
def update_price_matching_job(
    job_id: str,
    body: PriceMatchingJobUpdate,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    job = STORE.update_job_meta(
        db,
        job_id,
        bdi=body.bdi,
        increase_index=body.increase_index,
        cliente=body.cliente,
        obra=body.obra,
        uf=body.uf,
        price_bases=body.price_bases,
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    if body.price_bases is not None and job.get("session_id"):
        session = SESSION_STORE.get(job["session_id"])
        if session:
            session.project.price_bases = list(body.price_bases)
            enabled = [b for b in body.price_bases if b.get("enabled", True)]
            if enabled:
                session.source_priority = [
                    str(b.get("source") or "sinapi").lower() for b in enabled
                ]
            SESSION_STORE._persist_snapshot(session)  # noqa: SLF001

    return job


@router.post("/jobs/{job_id}/process")
def process_price_matching_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    use_llm: bool = Query(default=True),
    async_mode: bool = Query(default=True),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    job = STORE.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if not job.get("rows"):
        raise HTTPException(status_code=400, detail="Job sem linhas importadas")

    enabled_bases = [b for b in job.get("price_bases") or [] if b.get("enabled", True) and b.get("reference")]
    if not enabled_bases:
        raise HTTPException(
            status_code=400,
            detail="Selecione ao menos uma base de preços e período antes de processar",
        )

    _, usuario = _user_ctx(user)
    rows_total = len(job.get("rows") or [])
    if async_mode:
        with _PROCESS_LOCK:
            if job_id in _PROCESSING:
                progress_job = STORE.get_job(db, job_id) or job
                return {
                    "job_id": job_id,
                    "status": "processing",
                    "rows_total": rows_total,
                    "rows_processed": int(progress_job.get("rows_processed") or 0),
                    "process_percent": float(progress_job.get("process_percent") or 0),
                    "message": "Processamento já em andamento",
                }
            _PROCESSING.add(job_id)
        _set_job_progress(job_id, 0, rows_total)
        background_tasks.add_task(_run_process, job_id, use_llm, usuario)
        STORE.update_job_meta(db, job_id, status="processing")
        return {
            "job_id": job_id,
            "status": "processing",
            "rows_total": rows_total,
            "rows_processed": 0,
            "process_percent": 0.0,
            "message": "Processamento iniciado em background",
        }

    result = STORE.process_job(db, job_id, use_llm=use_llm, usuario=usuario)
    return result


@router.post("/jobs/{job_id}/rows/{row_id}/accept")
def accept_price_matching_row(
    job_id: str,
    row_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    row = STORE.accept_row(db, job_id, row_id)
    if not row:
        raise HTTPException(status_code=404, detail="Linha não encontrada")
    uid, _ = _user_ctx(user)
    background_tasks.add_task(_run_sync_job_budget, job_id, uid)
    return row


@router.post("/jobs/{job_id}/rows/{row_id}/replace")
def replace_price_matching_row(
    job_id: str,
    row_id: str,
    body: PriceMatchingReplaceRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    job = STORE.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    row = STORE.replace_row(
        db,
        job_id,
        row_id,
        base=body.base.upper(),
        code=body.code,
        reference=body.reference,
        uf=str(job.get("uf") or "AM"),
        increase_index=float(job.get("increase_index") or 1.0),
        description=body.description,
        unit=body.unit,
        price=body.price,
        source=body.source,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Composição não encontrada")
    uid, _ = _user_ctx(user)
    background_tasks.add_task(_run_sync_job_budget, job_id, uid)
    return row


@router.get("/search")
def manual_search_compositions(
    q: str = Query(default=""),
    code: Optional[str] = Query(default=None),
    base: Optional[str] = Query(default=None),
    unit: Optional[str] = Query(default=None),
    uf: str = Query(default="AM"),
    job_id: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    price_bases: list[dict[str, Any]] | None = None
    search_uf = uf.upper()
    if job_id:
        job = STORE.get_job(db, job_id)
        if job:
            price_bases = job.get("price_bases") or None
            search_uf = str(job.get("uf") or uf).upper()
    hits = search_catalog(
        q,
        code=code,
        base=base,
        unit=unit,
        limit=limit,
        uf=search_uf,
        price_bases=price_bases,
    )
    return {"results": [h.to_dict() for h in hits], "count": len(hits)}


@router.post("/jobs/{job_id}/generate-budget")
def generate_budget_from_price_matching(
    job_id: str,
    sync_schedule: bool = Query(default=True),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """Sincroniza preços na sessão PPD existente e persiste no banco."""
    from pricing.budget.budget_engine_v2 import BudgetEngineV2

    job = STORE.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if not job.get("rows"):
        raise HTTPException(status_code=400, detail="Job sem linhas importadas")

    matched = sum(1 for r in job["rows"] if r.get("codigo_base"))
    if matched == 0:
        raise HTTPException(
            status_code=400,
            detail="Processe os preços antes de gerar o orçamento (nenhuma composição encontrada)",
        )

    session_payload = sync_and_persist_job_budget(db, job, user=user)
    if not session_payload:
        session_payload = build_budget_session_from_job(job)
    session_id = session_payload["session_id"]

    if sync_schedule:
        try:
            engine = BudgetEngineV2()
            synced = engine.sync_schedule(session_id)
            session_payload = synced.to_dict()
            saved = save_budget(
                db,
                session_payload,
                title=str(job.get("obra") or session_payload.get("title") or "Orçamento importado"),
                budget_id=str(job.get("budget_document_id")) if job.get("budget_document_id") else None,
                user=user,
                sync_composition_snapshots=False,
            )
            session_from_payload(saved)
            session_payload = saved
        except Exception:
            saved = session_payload
    else:
        saved = session_payload

    budget_id = job.get("budget_document_id") or saved.get("db_id")
    if not job.get("budget_document_id") and saved.get("db_id"):
        STORE.link_budget(
            db,
            job_id,
            budget_document_id=str(saved.get("db_id")),
            session_id=saved.get("session_id"),
        )

    STORE.update_job_meta(db, job_id, status="budget_generated")
    return {
        "session": saved,
        "session_id": saved.get("session_id") or session_id,
        "job_id": job_id,
        "budget_id": saved.get("db_id"),
        "rows_imported": len(job["rows"]),
        "rows_matched": matched,
        "message": "Orçamento atualizado com preços lançados",
    }


@router.post("/jobs/{job_id}/export/excel")
def export_price_matching_excel(
    job_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    job = STORE.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    data = export_price_matching_xlsx(job)
    filename = f"lancar_precos_{job_id[:8]}.xlsx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/jobs/{job_id}/export/pdf")
def export_price_matching_pdf_route(
    job_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    job = STORE.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    data = export_price_matching_pdf(job)
    filename = f"lancar_precos_{job_id[:8]}.pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
