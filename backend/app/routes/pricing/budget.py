from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.services.budget_db_service import (
    BudgetVersionConflictError,
    delete_budget,
    get_budget,
    list_budgets,
    save_budget,
)
from app.services.budget_stream_service import BudgetStreamService
from core.auth.dependencies import get_current_user
from core.auth.tenant_context import parse_tenant_header
from core.database.connection import get_db
from core.database.models import User
from core.llm_override import llm_model_scope
from pricing.bootstrap import (
    _DEFAULT_DATA_DIR,
    ensure_providers_registered,
)
from pricing.budget.budget_builder import BudgetBuilder
from pricing.budget.budget_session import SESSION_STORE
from pricing.budget.ppd_parser import extract_price_base_rows, parse_ppd_workbook
from pricing.budget.ppd_template import create_empty_ppd_metadata, create_empty_ppd_tree
from pricing.budget.project_importer import ProjectImporter
from pricing.core.price_query import build_price_request, price_item_to_dict
from pricing.registry.provider_registry import ProviderRegistry

from app.routes.pricing.schemas import (
    AddServiceRequest,
    ApplyGroupQuantityRequest,
    BdiUpdateRequest,
    BudgetBuildRequest,
    BudgetGenerateRequest,
    BudgetRestoreRequest,
    BudgetRevisionCreateRequest,
    BudgetSaveRequest,
    BudgetSkeletonCreateRequest,
    BudgetSkeletonUpdateRequest,
    CellUpdateRequest,
    ComposeEtapaRequest,
    EtapaCreateRequest,
    EtapaUpdateRequest,
    MemoryGenerateRequest,
    ProjectUpdateRequest,
    ReplaceServiceRequest,
    ScheduleComposeRequest,
    ScheduleLinkRequest,
    ScheduleSettingsRequest,
    ScheduleTaskUpdateRequest,
    SearchPriceRequest,
    SubEtapaCreateRequest,
)
from app.routes.pricing.shared import (
    PPD_EXAMPLE,
    _ensure_budget_pricing_context,
    _ensure_price_base_loaded,
    _get_budget_engine,
    _get_engine,
    _get_orchestrator,
    logger,
)

router = APIRouter()


def _persist_audit_delta(
    db: Session,
    session: Any,
    session_id: str,
    audit_before: int,
    user: User | None,
) -> None:
    from app.services.budget_audit_service import persist_audit_delta

    persist_audit_delta(db, session, session_id, audit_before, user=user)


def _guard_budget_edit(db: Session, session_id: str, user: User | None) -> None:
    from app.services.budget_session_lock_service import assert_session_lock

    assert_session_lock(db, session_id, user)

@router.post("/budget/new-template")
def create_ppd_template(
    obra_type: str = Query(default="RF"),
    projeto: str = Query(default=""),
):
    """Cria sessão vazia no template PPD municipal padrão."""
    from pricing.budget.bdi_types import normalize_obra_type

    meta = create_empty_ppd_metadata(projeto=projeto, obra_type=normalize_obra_type(obra_type))
    roots = create_empty_ppd_tree(meta)
    session = SESSION_STORE.create(
        roots=roots,
        title=meta.projeto,
        intent={"template": True},
        project=meta,
    )
    return session.to_dict()


@router.get("/budget/skeletons")
def list_budget_skeletons_route():
    """Lista esqueletos de orçamento cadastrados (etapas/sub-etapas)."""
    from pricing.budget.budget_skeleton_store import list_budget_skeletons

    items = list_budget_skeletons()
    return {"items": items, "count": len(items)}


@router.get("/budget/skeletons/{skeleton_id}")
def get_budget_skeleton_route(skeleton_id: str):
    from pricing.budget.budget_skeleton_store import get_budget_skeleton

    sk = get_budget_skeleton(skeleton_id)
    if not sk:
        raise HTTPException(status_code=404, detail="Esqueleto não encontrado")
    return sk


@router.post("/budget/skeletons")
def create_budget_skeleton_route(body: BudgetSkeletonCreateRequest):
    from pricing.budget.budget_skeleton_store import create_budget_skeleton

    try:
        return create_budget_skeleton(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/budget/skeletons/{skeleton_id}")
def update_budget_skeleton_route(skeleton_id: str, body: BudgetSkeletonUpdateRequest):
    from pricing.budget.budget_skeleton_store import update_budget_skeleton

    try:
        return update_budget_skeleton(skeleton_id, body.model_dump(exclude_unset=True))
    except KeyError:
        raise HTTPException(status_code=404, detail="Esqueleto não encontrado") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/budget/skeletons/{skeleton_id}")
def delete_budget_skeleton_route(skeleton_id: str):
    from pricing.budget.budget_skeleton_store import delete_budget_skeleton

    try:
        delete_budget_skeleton(skeleton_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Esqueleto não encontrado") from None
    return {"deleted": skeleton_id}


@router.post("/budget/new-from-skeleton")
def create_budget_from_skeleton_route(
    skeleton_id: str = Query(..., min_length=1),
    projeto: str = Query(default=""),
    obra_type: Optional[str] = Query(default=None),
):
    """Cria sessão de orçamento a partir de esqueleto cadastrado."""
    from pricing.budget.budget_skeleton_store import (
        build_budget_tree_from_skeleton,
        get_budget_skeleton,
    )

    skeleton = get_budget_skeleton(skeleton_id)
    if not skeleton:
        raise HTTPException(status_code=404, detail="Esqueleto não encontrado")

    meta, roots = build_budget_tree_from_skeleton(
        skeleton, projeto=projeto, obra_type=obra_type
    )
    session = SESSION_STORE.create(
        roots=roots,
        title=meta.projeto,
        intent={"template": True, "skeleton_id": skeleton_id},
        project=meta,
    )
    return session.to_dict()


@router.post("/budget/import-project")
async def import_project_budget(
    file: UploadFile = File(...),
    use_llm: bool = Query(default=True),
    obra_type: Optional[str] = Query(default=None),
):
    """Importa documento de projeto — IA extrai quantitativos e gera orçamento."""
    suffix = Path(file.filename or "doc.pdf").suffix.lower()
    allowed = (".pdf", ".docx", ".xlsx", ".xls", ".txt", ".md", ".csv", ".json", ".rtf")
    if suffix not in allowed:
        raise HTTPException(status_code=400, detail=f"Formato não suportado: {suffix}")

    import_dir = _DEFAULT_DATA_DIR / "projects"
    import_dir.mkdir(parents=True, exist_ok=True)
    dest = import_dir / (file.filename or f"project{suffix}")
    with dest.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)

    _ensure_price_base_loaded()
    importer = ProjectImporter(_get_orchestrator())
    try:
        return importer.import_and_generate(dest, use_llm=use_llm, obra_type=obra_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.post("/budget/build")
def build_budget(body: BudgetBuildRequest):
    builder = BudgetBuilder(engine=_get_engine())
    return builder.build_dict(body.intent, body.source_priority)


@router.post("/budget/generate")
def generate_budget(body: BudgetGenerateRequest):
    """Pipeline completo: LLM → Quantity → Pricing → Budget v2."""
    _ensure_price_base_loaded()
    orchestrator = _get_orchestrator()
    return orchestrator.run(
        body.text,
        source_priority=body.source_priority or ["sinapi"],
        use_llm=body.use_llm,
        obra_type=body.obra_type,
    )


@router.post("/budget/generate/stream")
def generate_budget_stream(body: BudgetGenerateRequest):
    """Pipeline com SSE — tokens LLM e etapas em tempo real."""
    _ensure_price_base_loaded()
    service = BudgetStreamService(orchestrator=_get_orchestrator())
    return StreamingResponse(
        service.stream(
            body.text,
            source_priority=body.source_priority or ["sinapi"],
            use_llm=body.use_llm,
            obra_type=body.obra_type,
            existing_session_id=body.existing_session_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


@router.get("/budget/saved")
def list_saved_budgets(
    project_id: Optional[str] = None,
    mine_only: bool = Query(default=False, description="Somente orçamentos do usuário autenticado"),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
    tenant_id=Depends(parse_tenant_header),
):
    try:
        return {
            "items": list_budgets(
                db,
                project_id=project_id,
                user=user,
                mine_only=mine_only,
                tenant_id=tenant_id,
            )
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Banco indisponível: {exc}") from exc


@router.get("/budget/saved/{budget_id}")
def get_saved_budget(
    budget_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
    tenant_id=Depends(parse_tenant_header),
):
    try:
        payload = get_budget(db, budget_id, user=user, tenant_id=tenant_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Banco indisponível: {exc}") from exc
    if not payload:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")
    return payload


@router.post("/budget/saved")
def create_saved_budget(
    body: BudgetSaveRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
    tenant_id=Depends(parse_tenant_header),
):
    try:
        return save_budget(
            db,
            body.payload,
            title=body.title,
            input_text=body.input_text,
            project_id=body.project_id,
            user=user,
            tenant_id=tenant_id,
        )
    except Exception as exc:
        if "indisponível" in str(exc).lower() or "connection" in str(exc).lower():
            raise HTTPException(status_code=503, detail=f"Banco indisponível — rode make db-init ou docker-up: {exc}") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/budget/saved/{budget_id}")
def update_saved_budget(
    budget_id: str,
    body: BudgetSaveRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
    tenant_id=Depends(parse_tenant_header),
):
    session_id = (body.payload or {}).get("session_id")
    if session_id:
        _guard_budget_edit(db, session_id, user)
    try:
        return save_budget(
            db,
            body.payload,
            title=body.title,
            input_text=body.input_text,
            budget_id=budget_id,
            project_id=body.project_id,
            user=user,
            expected_version=body.expected_version,
            tenant_id=tenant_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except BudgetVersionConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": str(exc), "current_version": exc.current_version},
        ) from exc
    except KeyError:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado") from None
    except Exception as exc:
        from app.services.budget_revision_service import BudgetBaselineFrozenError

        if isinstance(exc, BudgetBaselineFrozenError):
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        if "connection" in str(exc).lower():
            raise HTTPException(status_code=503, detail=f"Banco indisponível: {exc}") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/budget/saved/{budget_id}/freeze-baseline")
def freeze_budget_baseline(
    budget_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    from app.services.budget_revision_service import freeze_baseline

    try:
        return freeze_baseline(db, budget_id, user=user)
    except KeyError:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Banco indisponível: {exc}") from exc


@router.post("/budget/saved/{budget_id}/revision")
def create_budget_revision(
    budget_id: str,
    body: BudgetRevisionCreateRequest | None = None,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    from app.services.budget_revision_service import create_revision

    req = body or BudgetRevisionCreateRequest()
    try:
        return create_revision(
            db,
            budget_id,
            user=user,
            revision_label=req.revision_label,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Banco indisponível: {exc}") from exc


@router.get("/budget/saved/{budget_id}/revisions")
def list_budget_revisions(
    budget_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    from app.services.budget_revision_service import list_revisions

    try:
        return {"items": list_revisions(db, budget_id, user=user)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado") from None
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Banco indisponível: {exc}") from exc


@router.get("/budget/saved/{budget_id}/baseline-compare")
def compare_budget_baseline(
    budget_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    from app.services.budget_revision_service import compare_with_baseline

    try:
        return compare_with_baseline(db, budget_id, user=user)
    except KeyError:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Banco indisponível: {exc}") from exc


@router.delete("/budget/saved/{budget_id}")
def remove_saved_budget(
    budget_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
    tenant_id=Depends(parse_tenant_header),
):
    try:
        if not delete_budget(db, budget_id, user=user, tenant_id=tenant_id):
            raise HTTPException(status_code=404, detail="Orçamento não encontrado")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Banco indisponível: {exc}") from exc
    return {"deleted": budget_id}


@router.post("/budget/restore")
def restore_budget_session(body: BudgetRestoreRequest):
    """Reidrata sessão em memória a partir do payload (ex.: após restart do backend)."""
    from app.services.budget_db_service import session_from_payload

    payload = body.payload
    if not payload.get("items") and not payload.get("rows"):
        raise HTTPException(status_code=400, detail="Payload inválido: sem itens da sessão")
    session = session_from_payload(payload)
    return session.to_dict()


@router.get("/budget/{session_id}")
def get_budget_session(session_id: str):
    engine = _get_budget_engine()
    session = engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    return session.to_dict()


@router.get("/budget/{session_id}/compositions/batch")
def get_budget_compositions_batch(
    session_id: str,
    backfill: bool = Query(
        default=False,
        description="Persiste CPUs ausentes no snapshot (lento — use POST /compositions/backfill)",
    ),
    db: Session = Depends(get_db),
):
    """Retorna todas as CPUs abertas do orçamento (cache global + fallback price_bank)."""
    engine = _get_budget_engine()
    session = engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    from pricing.budget.composition_snapshot_service import get_batch_compositions

    budget_id = session.db_id or (session.to_dict().get("db_id"))
    try:
        result = get_batch_compositions(
            db,
            roots=session.roots,
            meta=session.project,
            budget_document_id=budget_id,
            backfill=backfill,
        )
    except Exception as exc:
        logger.exception("compositions/batch failed for session %s", session_id)
        raise HTTPException(status_code=500, detail=f"Erro ao carregar composições: {exc}") from exc
    return {
        "session_id": session_id,
        "budget_document_id": budget_id,
        **result,
    }


@router.post("/budget/{session_id}/compositions/backfill")
def backfill_budget_composition_snapshots(
    session_id: str,
    db: Session = Depends(get_db),
):
    """Popula cache global com CPUs ausentes do orçamento (lazy backfill)."""
    engine = _get_budget_engine()
    session = engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    budget_id = session.db_id or session.to_dict().get("db_id")
    if not budget_id:
        raise HTTPException(
            status_code=400,
            detail="Orçamento não salvo — salve o orçamento antes de gerar snapshots",
        )

    from pricing.budget.composition_snapshot_service import sync_missing_snapshots

    stats = sync_missing_snapshots(db, uuid.UUID(str(budget_id)), session.roots, session.project)
    return {"session_id": session_id, "budget_document_id": str(budget_id), **stats}


@router.patch("/budget/{session_id}/bdi")
def update_budget_bdi(
    session_id: str,
    body: BdiUpdateRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    from pricing.budget.bdi_edital_profiles import BdiTcuComponents, get_bdi_edital_profile
    from pricing.budget.bdi_types import normalize_obra_type
    from pricing.models.budget_metadata import BdiConfig

    engine = _get_budget_engine()
    session = engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    obra_type = normalize_obra_type(body.obra_type or session.project.obra_type)
    audit_before = len(session.audit_log)

    try:
        if body.profile_id:
            if body.profile_id == "seminf_table":
                config = BdiConfig.from_obra_type(obra_type, label=body.label or session.project.bdi.label)
            else:
                profile = get_bdi_edital_profile(body.profile_id)
                if not profile:
                    raise HTTPException(status_code=400, detail=f"Perfil BDI desconhecido: {body.profile_id}")
                config = BdiConfig.from_profile(profile, obra_type=obra_type)
                if body.label:
                    config.label = body.label
        elif body.source == "custom" or body.components_comd or body.components_semd:
            config = BdiConfig.from_dict(session.project.bdi.to_dict())
            config.source = body.source or "custom"
            config.profile_id = body.profile_id or "custom_edital"
            config.obra_type = obra_type
            if body.label:
                config.label = body.label
            if body.components_comd:
                config.components_comd = BdiTcuComponents.from_dict(body.components_comd.model_dump())
            if body.components_semd:
                config.components_semd = BdiTcuComponents.from_dict(body.components_semd.model_dump())
            config.sync_rates()
        elif body.obra_type:
            config = BdiConfig.from_obra_type(obra_type)
        else:
            raise HTTPException(status_code=400, detail="Informe obra_type, profile_id ou componentes BDI")
        updated = engine.set_bdi_config(session_id, config)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    new_entries = updated.audit_log[audit_before:]
    if new_entries:
        _persist_audit_delta(db, updated, session_id, audit_before, user)

    return updated.to_dict()


@router.get("/budget/{session_id}/bdi/validation")
def get_budget_bdi_validation(session_id: str):
    from pricing.budget.bdi_edital_validator import validate_bdi_config

    engine = _get_budget_engine()
    session = engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    return validate_bdi_config(session.project.bdi)


@router.get("/budget/{session_id}/audit")
def get_budget_audit_trail(
    session_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    from app.services.budget_audit_service import list_audit_trail

    session = SESSION_STORE.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    db_items = list_audit_trail(
        db,
        session_id=session_id,
        budget_document_id=session.db_id,
    )
    session_items = list(reversed(session.audit_log[-200:]))
    return {
        "session_id": session_id,
        "db_id": session.db_id,
        "session_entries": session_items,
        "persisted_entries": db_items,
        "items": session_items + db_items,
    }


@router.post("/budget/{session_id}/subetapas")
def create_budget_subetapa(session_id: str, body: SubEtapaCreateRequest):
    engine = _get_budget_engine()
    try:
        session = engine.add_subetapa(session_id, body.parent_code, body.name)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return session.to_dict()


@router.post("/budget/{session_id}/memory/generate")
def generate_budget_memories(session_id: str, body: MemoryGenerateRequest):
    engine = _get_budget_engine()
    try:
        with llm_model_scope(body.llm_model):
            session, log = engine.generate_memories(
                session_id,
                group_code=body.group_code,
                use_llm=body.use_llm,
            )
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"session": session.to_dict(), "memory_log": log}


@router.get("/budget/{session_id}/schedule")
def get_budget_schedule(session_id: str):
    engine = _get_budget_engine()
    try:
        session = engine.get_schedule(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    return {"schedule": session.schedule.to_dict() if session.schedule else None}


@router.post("/budget/{session_id}/schedule/sync")
def sync_budget_schedule(
    session_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    engine = _get_budget_engine()
    session_before = engine.get_session(session_id)
    if not session_before:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    audit_before = len(session_before.audit_log)
    try:
        session = engine.sync_schedule(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    _persist_audit_delta(db, session, session_id, audit_before, user)
    return session.to_dict()


@router.post("/budget/{session_id}/schedule/recalculate")
def recalculate_budget_schedule(
    session_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    engine = _get_budget_engine()
    session_before = engine.get_session(session_id)
    if not session_before:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    audit_before = len(session_before.audit_log)
    try:
        session = engine.recalculate_schedule(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    _persist_audit_delta(db, session, session_id, audit_before, user)
    return session.to_dict()


@router.patch("/budget/{session_id}/schedule/settings")
def update_budget_schedule_settings(
    session_id: str,
    body: ScheduleSettingsRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    engine = _get_budget_engine()
    session_before = engine.get_session(session_id)
    if not session_before:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    audit_before = len(session_before.audit_log)
    try:
        session = engine.update_schedule_settings(session_id, project_start=body.project_start)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    _persist_audit_delta(db, session, session_id, audit_before, user)
    return session.to_dict()


@router.patch("/budget/{session_id}/schedule/tasks/{task_id}")
def update_budget_schedule_task(
    session_id: str,
    task_id: str,
    body: ScheduleTaskUpdateRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    engine = _get_budget_engine()
    session_before = engine.get_session(session_id)
    if not session_before:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    audit_before = len(session_before.audit_log)
    try:
        session = engine.update_schedule_task(
            session_id,
            task_id,
            duration_days=body.duration_days,
            manual_start=body.manual_start,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _persist_audit_delta(db, session, session_id, audit_before, user)
    return session.to_dict()


@router.post("/budget/{session_id}/schedule/links")
def add_budget_schedule_link(
    session_id: str,
    body: ScheduleLinkRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    engine = _get_budget_engine()
    session_before = engine.get_session(session_id)
    if not session_before:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    audit_before = len(session_before.audit_log)
    try:
        session = engine.add_schedule_link(
            session_id,
            body.predecessor_id,
            body.successor_id,
            link_type=body.link_type,
            lag_days=body.lag_days,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _persist_audit_delta(db, session, session_id, audit_before, user)
    return session.to_dict()


@router.delete("/budget/{session_id}/schedule/links/{link_id}")
def delete_budget_schedule_link(
    session_id: str,
    link_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    engine = _get_budget_engine()
    session_before = engine.get_session(session_id)
    if not session_before:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    audit_before = len(session_before.audit_log)
    try:
        session = engine.remove_schedule_link(session_id, link_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    _persist_audit_delta(db, session, session_id, audit_before, user)
    return session.to_dict()


@router.post("/budget/{session_id}/schedule/compose")
def compose_budget_schedule(
    session_id: str,
    body: ScheduleComposeRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    engine = _get_budget_engine()
    session_before = engine.get_session(session_id)
    if not session_before:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    audit_before = len(session_before.audit_log)
    try:
        with llm_model_scope(body.llm_model):
            session, log, summary, llm_model = engine.compose_schedule(
                session_id,
                body.prompt,
                use_llm=body.use_llm,
                replace_links=body.replace_links,
            )
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _persist_audit_delta(db, session, session_id, audit_before, user)
    return {
        "session": session.to_dict(),
        "schedule_log": log,
        "summary": summary,
        "llm_model": llm_model,
    }

@router.patch("/budget/{session_id}/project")
def update_budget_project(session_id: str, body: ProjectUpdateRequest):
    engine = _get_budget_engine()
    try:
        session = engine.update_project(session_id, body.model_dump(exclude_none=True))
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    return session.to_dict()


@router.post("/budget/{session_id}/etapas")
def create_budget_etapa(session_id: str, body: EtapaCreateRequest):
    engine = _get_budget_engine()
    try:
        session = engine.add_etapa(session_id, body.name)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    return session.to_dict()


@router.patch("/budget/{session_id}/etapas/{etapa_code}")
def update_budget_etapa(session_id: str, etapa_code: str, body: EtapaUpdateRequest):
    engine = _get_budget_engine()
    try:
        session = engine.update_etapa(session_id, etapa_code, body.name)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return session.to_dict()


@router.delete("/budget/{session_id}/rows/{row_id}")
def delete_budget_row(session_id: str, row_id: str):
    engine = _get_budget_engine()
    try:
        session = engine.delete_row(session_id, row_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return session.to_dict()


@router.post("/budget/{session_id}/itemization/renumber")
def renumber_budget_itemization(session_id: str):
    engine = _get_budget_engine()
    try:
        session, mapping = engine.renumber_itemization(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    payload = session.to_dict()
    payload["renumber_result"] = {"changed_count": len(mapping), "mapping": mapping}
    return payload


@router.get("/budget/{session_id}/groups/{group_code}/compose-prompt")
def get_group_compose_prompt(session_id: str, group_code: str):
    engine = _get_budget_engine()
    try:
        prompt, count = engine.get_group_compose_prompt(session_id, group_code)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"prompt": prompt, "service_count": count}


@router.post("/budget/{session_id}/etapas/{etapa_code}/compose")
def compose_budget_etapa(
    session_id: str,
    etapa_code: str,
    body: ComposeEtapaRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    priority = _ensure_budget_pricing_context(session_id, body.source_priority)
    engine = _get_budget_engine()
    session_before = engine.get_session(session_id)
    if not session_before:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    audit_before = len(session_before.audit_log)
    try:
        session, log, removed = engine.compose_etapa(
            session_id,
            etapa_code,
            body.prompt,
            source_priority=priority or body.source_priority or ["sinapi"],
            default_quantity=body.default_quantity,
            replace_existing=body.replace_existing,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _persist_audit_delta(db, session, session_id, audit_before, user)
    return {"session": session.to_dict(), "compose_log": log, "removed_count": removed}


@router.post("/budget/{session_id}/services/{row_id}/replace")
def replace_budget_service(
    session_id: str,
    row_id: str,
    body: ReplaceServiceRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    has_pick = bool(body.code or body.description)
    engine = _get_budget_engine()
    session_before = engine.get_session(session_id)
    if not session_before:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    audit_before = len(session_before.audit_log)

    if has_pick:
        price_data = {
            "code": body.code or "",
            "description": body.description or "",
            "unit": body.unit or "",
            "price": body.price or 0,
            "source": body.source or "sinapi",
        }
    elif body.query:
        priority = _ensure_budget_pricing_context(session_id, body.source_priority)
        pricing = _get_engine()
        from pricing.budget.budget_structure import parse_term_hints

        q, unit_hint, _ = parse_term_hints(body.query)
        request = build_price_request(q, unit=unit_hint, source_priority=priority, limit=1)
        item = pricing.resolve(request)
        if not item:
            raise HTTPException(status_code=404, detail="Serviço não encontrado na base de preços")
        price_data = price_item_to_dict(item) or {}
        if unit_hint:
            price_data["unit_hint"] = unit_hint
        price_data["query"] = q
    else:
        raise HTTPException(status_code=400, detail="Informe code/description ou query")

    try:
        session = engine.replace_service(session_id, row_id, price_data)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    budget_id = session.db_id or session.to_dict().get("db_id")
    if budget_id:
        try:
            from pricing.budget.budget_export_tables import _resolve_open_composition_lookup
            from pricing.budget.budget_structure import find_item
            from pricing.budget.composition_snapshot_service import upsert_snapshot_for_service

            replaced, _, _ = find_item(session.roots, row_id=row_id)
            if replaced is not None:
                lookup = _resolve_open_composition_lookup(replaced, session.project)
                source_code = (replaced.source_code or price_data.get("code") or "").strip()
                if lookup and source_code:
                    ref, uf = lookup
                    upsert_snapshot_for_service(
                        db, budget_id, code=source_code, reference=ref, uf=uf
                    )
        except Exception:
            pass

    _persist_audit_delta(db, session, session_id, audit_before, user)
    return session.to_dict()


@router.post("/budget/{session_id}/groups/{group_code}/apply-quantity")
def apply_group_quantity(
    session_id: str,
    group_code: str,
    body: ApplyGroupQuantityRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    engine = _get_budget_engine()
    session_before = engine.get_session(session_id)
    if not session_before:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    audit_before = len(session_before.audit_log)
    try:
        session, count = engine.apply_group_quantity(
            session_id,
            group_code,
            body.quantity,
            include_subgroups=body.include_subgroups,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _persist_audit_delta(db, session, session_id, audit_before, user)
    return {"session": session.to_dict(), "updated_count": count}


@router.post("/budget/{session_id}/services")
def add_budget_service(
    session_id: str,
    body: AddServiceRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    has_pick = bool(body.code or body.description)
    engine = _get_budget_engine()
    session_before = engine.get_session(session_id)
    if not session_before:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    audit_before = len(session_before.audit_log)
    if has_pick:
        price_data = {
            "code": body.code or "",
            "description": body.description or "",
            "unit": body.unit or "",
            "price": body.price or 0,
            "source": body.source or "sinapi",
        }
        quantity = body.quantity
    else:
        priority = _ensure_budget_pricing_context(session_id, body.source_priority)
        pricing = _get_engine()
        quantity = body.quantity
        if body.query:
            from pricing.budget.budget_structure import parse_term_hints

            q, unit_hint, term_qty = parse_term_hints(body.query)
            request = build_price_request(q, unit=unit_hint, source_priority=priority, limit=1)
            item = pricing.resolve(request)
            if not item:
                raise HTTPException(status_code=404, detail="Serviço não encontrado na base de preços")
            price_data = price_item_to_dict(item) or {}
            if unit_hint:
                price_data["unit_hint"] = unit_hint
            quantity = term_qty if term_qty is not None else body.quantity
        else:
            raise HTTPException(status_code=400, detail="Informe code/description ou query")

    try:
        session = engine.add_service(
            session_id,
            body.etapa_code,
            price_data,
            quantity=quantity,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _persist_audit_delta(db, session, session_id, audit_before, user)
    return session.to_dict()


@router.post("/budget/search")
def search_price_items(body: SearchPriceRequest):
    from pricing.budget.budget_structure import parse_term_hints

    priority = _ensure_budget_pricing_context(body.session_id, body.source_priority)
    engine = _get_engine()
    query, unit_hint, parsed_qty = parse_term_hints(body.query)
    request = build_price_request(
        query or body.query,
        unit=unit_hint,
        source_priority=priority,
        limit=body.limit,
    )
    results = engine.resolve_many(request, best_only=False)
    if unit_hint and results:
        preferred = [r for r in results if r.unit and r.unit.upper() == unit_hint]
        if preferred:
            results = preferred + [r for r in results if r not in preferred]
    return {
        "query": body.query,
        "parsed_query": query,
        "unit_hint": unit_hint,
        "parsed_quantity": parsed_qty,
        "parsed": {
            "query": query,
            "unit_hint": unit_hint,
            "quantity": parsed_qty,
        },
        "results": [price_item_to_dict(i) for i in results],
        "count": len(results),
    }


@router.post("/budget/import-model-template")
async def import_model_template(
    file: UploadFile = File(...),
    session_id: Optional[str] = Query(default=None),
    include_services: bool = Query(default=False),
):
    """Importa etapas de planilha modelo de orçamento (PPD/WBS)."""
    suffix = Path(file.filename or "model.xlsm").suffix.lower()
    if suffix not in (".xlsm", ".xlsx", ".xls"):
        raise HTTPException(status_code=400, detail="Formato inválido — use .xlsm/.xlsx")

    import_dir = _DEFAULT_DATA_DIR / "imports"
    import_dir.mkdir(parents=True, exist_ok=True)
    dest = import_dir / (file.filename or f"model{suffix}")
    with dest.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)

    from core.knowledge.regional_budget_indexer import extract_regional_budget_model
    from pricing.budget.budget_structure import import_etapas_from_sidecar
    from pricing.budget.ppd_template import create_empty_ppd_metadata

    model = extract_regional_budget_model(dest)
    etapas_data = model.get("etapas") or []
    if not etapas_data:
        raise HTTPException(status_code=400, detail="Nenhuma etapa detectada no modelo")

    engine = _get_budget_engine()
    if session_id:
        session = engine.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Sessão não encontrada")
        count = import_etapas_from_sidecar(
            session.roots,
            etapas_data,
            session.project,
            include_services=include_services,
        )
        session.title = session.title or model.get("projeto") or dest.stem
        if model.get("projeto") and not session.project.projeto:
            session.project.projeto = str(model["projeto"])
        from pricing.budget.budget_structure import refresh_calculation_memory

        session.calculation_memory = refresh_calculation_memory(session.roots)
        return {**session.to_dict(), "imported_etapas": count}

    meta = create_empty_ppd_metadata(
        projeto=str(model.get("projeto") or dest.stem),
        obra_type=str(model.get("obra_type") or "RF"),
    )
    roots: list = []
    count = import_etapas_from_sidecar(roots, etapas_data, meta, include_services=include_services)
    session = SESSION_STORE.create(
        roots=roots,
        title=meta.projeto,
        intent={"imported_template": True},
        project=meta,
    )
    return {**session.to_dict(), "imported_etapas": count}


@router.patch("/budget/{session_id}/cell")
def update_budget_cell(
    session_id: str,
    body: CellUpdateRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    _guard_budget_edit(db, session_id, user)
    if not body.row_id and not body.code:
        raise HTTPException(status_code=400, detail="Informe row_id ou code")
    engine = _get_budget_engine()
    session_before = engine.get_session(session_id)
    if not session_before:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    audit_before = len(session_before.audit_log)
    try:
        session = engine.update_cell(
            session_id,
            body.row_id or "",
            body.field,
            body.value,
            code=body.code,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    new_entries = session.audit_log[audit_before:]
    if new_entries:
        _persist_audit_delta(db, session, session_id, audit_before, user)

    return session.to_dict()
def import_ppd_from_path(source_path: Path, load_base: bool = True) -> dict[str, Any]:
    """Importa PPD de caminho local (sync — usado por API e testes)."""
    ensure_providers_registered()
    metadata, roots, info = parse_ppd_workbook(source_path)
    base_loaded = 0
    if load_base:
        base_rows = extract_price_base_rows(source_path)
        if base_rows:
            provider = ProviderRegistry.get("sinapi")
            if provider:
                provider._data = base_rows  # noqa: SLF001
                from pricing.models.price_source import PriceSource
                provider._source = PriceSource(  # noqa: SLF001
                    name="sinapi",
                    label="SINAPI (PPD Base)",
                    item_count=len(base_rows),
                    path=str(source_path),
                )
                base_loaded = len(base_rows)

    session = SESSION_STORE.create(
        roots=roots,
        title=metadata.projeto or metadata.objeto or "Orçamento PPD",
        intent={"imported": True, "project": metadata.to_dict()},
        project=metadata,
    )
    session.calculation_memory = [{"step": "import", "source": str(source_path), **info}]
    return {
        **session.to_dict(),
        "import_info": {**info, "base_loaded": base_loaded, "path": str(source_path)},
    }


@router.post("/budget/import-ppd")
async def import_ppd_budget(
    file: UploadFile | None = File(default=None),
    load_base: bool = Query(default=True),
):
    """Importa planilha PPD MC/OR (.xlsm/.xlsx) como sessão editável."""
    if file and file.filename:
        suffix = Path(file.filename).suffix.lower()
        if suffix not in (".xlsm", ".xlsx", ".xls"):
            raise HTTPException(status_code=400, detail="Formato PPD inválido")
        import_dir = _DEFAULT_DATA_DIR / "imports"
        import_dir.mkdir(parents=True, exist_ok=True)
        dest = import_dir / file.filename
        with dest.open("wb") as handle:
            shutil.copyfileobj(file.file, handle)
        source_path = dest
    elif PPD_EXAMPLE.exists():
        source_path = PPD_EXAMPLE
    else:
        raise HTTPException(status_code=400, detail="Envie um arquivo PPD ou configure planilha-exemplo")

    return import_ppd_from_path(source_path, load_base=load_base)


@router.post("/budget/load-ppd-example")
def load_ppd_example_base():
    """Carrega aba Base da planilha PPD de exemplo no provider SINAPI."""
    ensure_providers_registered()
    if not PPD_EXAMPLE.exists():
        raise HTTPException(status_code=404, detail="Planilha exemplo não encontrada")
    rows = extract_price_base_rows(PPD_EXAMPLE)
    provider = ProviderRegistry.get("sinapi")
    if not provider:
        raise HTTPException(status_code=500, detail="Provider sinapi não registrado")
    provider._data = rows  # noqa: SLF001
    from pricing.models.price_source import PriceSource
    provider._source = PriceSource(
        name="sinapi",
        label="SINAPI PPD Março/2026",
        item_count=len(rows),
        path=str(PPD_EXAMPLE),
        metadata={"sheet": "Base_Março2026-copia"},
    )
    return {"loaded": len(rows), "source": str(PPD_EXAMPLE)}


@router.get("/budget/{session_id}/lock")
def get_budget_session_lock(
    session_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    from app.services.budget_session_lock_service import lock_status

    return lock_status(db, session_id, user)


@router.post("/budget/{session_id}/lock")
def acquire_budget_session_lock(
    session_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    from app.services.budget_session_lock_service import (
        BudgetSessionLockConflictError,
        acquire_lock,
    )

    try:
        return acquire_lock(db, session_id, user)
    except BudgetSessionLockConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Sessão bloqueada por outro usuário",
                "holder_user_id": str(exc.holder_user_id) if exc.holder_user_id else None,
                "expires_at": exc.expires_at.isoformat() if exc.expires_at else None,
            },
        ) from exc


@router.post("/budget/{session_id}/lock/renew")
def renew_budget_session_lock(
    session_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    from app.services.budget_session_lock_service import (
        BudgetSessionLockConflictError,
        renew_lock,
    )

    try:
        return renew_lock(db, session_id, user)
    except BudgetSessionLockConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Sessão bloqueada por outro usuário",
                "holder_user_id": str(exc.holder_user_id) if exc.holder_user_id else None,
                "expires_at": exc.expires_at.isoformat() if exc.expires_at else None,
            },
        ) from exc


@router.delete("/budget/{session_id}/lock")
def release_budget_session_lock(
    session_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    from app.services.budget_session_lock_service import (
        BudgetSessionLockConflictError,
        release_lock,
    )

    try:
        release_lock(db, session_id, user)
        return {"released": True}
    except BudgetSessionLockConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Lock pertence a outro usuário",
                "holder_user_id": str(exc.holder_user_id) if exc.holder_user_id else None,
            },
        ) from exc
