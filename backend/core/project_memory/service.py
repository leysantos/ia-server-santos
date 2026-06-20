"""Serviço de memória operacional — activity events e project decisions."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from core.database.connection import is_db_enabled, session_scope
from core.database.models import (
    AgentRun,
    Conversation,
    OrchestratorLog,
    ProjectActivityEvent,
    ProjectDecision,
)

logger = logging.getLogger(__name__)


def _parse_uuid(value: str | uuid.UUID | None) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def _project_id_from_conversation(db: Session, conversation_id: uuid.UUID | None) -> uuid.UUID | None:
    if not conversation_id:
        return None
    conv = db.get(Conversation, conversation_id)
    return conv.project_id if conv else None


def record_activity(
    *,
    source: str,
    event_type: str,
    title: str,
    summary: str | None = None,
    project_id: str | uuid.UUID | None = None,
    agent_name: str | None = None,
    discipline: str | None = None,
    phase: str | None = None,
    meta: dict | None = None,
    db: Session | None = None,
) -> dict[str, Any] | None:
    """Registra evento na timeline operacional."""
    if not is_db_enabled():
        return None

    pid = _parse_uuid(project_id)

    def _persist(session: Session) -> dict[str, Any]:
        row = ProjectActivityEvent(
            project_id=pid,
            source=source,
            event_type=event_type,
            title=title,
            summary=summary,
            agent_name=agent_name,
            discipline=discipline,
            phase=phase,
            meta=meta,
        )
        session.add(row)
        session.flush()
        return serialize_activity(row)

    try:
        if db is not None:
            result = _persist(db)
            db.commit()
            return result
        with session_scope() as session:
            return _persist(session)
    except Exception as exc:
        logger.warning("Falha ao registrar activity: %s", exc)
        return None


def record_decision(
    *,
    source: str,
    title: str,
    description: str | None = None,
    rationale: str | None = None,
    disciplines: list[str] | None = None,
    project_id: str | uuid.UUID | None = None,
    meta: dict | None = None,
    db: Session | None = None,
) -> dict[str, Any] | None:
    """Registra decisão técnica/orçamentária."""
    if not is_db_enabled():
        return None

    pid = _parse_uuid(project_id)

    def _persist(session: Session) -> dict[str, Any]:
        row = ProjectDecision(
            project_id=pid,
            source=source,
            title=title,
            description=description,
            rationale=rationale,
            disciplines=disciplines,
            meta=meta,
        )
        session.add(row)
        session.flush()
        return serialize_decision(row)

    try:
        if db is not None:
            result = _persist(db)
            db.commit()
            return result
        with session_scope() as session:
            return _persist(session)
    except Exception as exc:
        logger.warning("Falha ao registrar decision: %s", exc)
        return None


def record_orchestrator_completion(
    *,
    input_text: str,
    disciplines: list[str],
    synthesis: dict,
    conversation_id: str | uuid.UUID | None = None,
    orchestrator_log_id: str | uuid.UUID | None = None,
    db: Session | None = None,
) -> None:
    """Auto-captura após orquestração multidisciplinar."""
    if not is_db_enabled():
        return

    def _persist(session: Session) -> None:
        conv_id = _parse_uuid(conversation_id)
        project_id = _project_id_from_conversation(session, conv_id)
        summary = synthesis.get("technical_summary") or synthesis.get("general_conclusion")
        title = f"Orquestração: {', '.join(disciplines[:4])}" if disciplines else "Orquestração concluída"
        record_activity(
            source="orchestrator",
            event_type="completed",
            title=title,
            summary=(summary or input_text)[:500] if (summary or input_text) else None,
            project_id=project_id,
            discipline=disciplines[0] if disciplines else None,
            phase="synthesis",
            meta={
                "disciplines": disciplines,
                "conversation_id": str(conv_id) if conv_id else None,
                "orchestrator_log_id": str(orchestrator_log_id) if orchestrator_log_id else None,
            },
            db=session,
        )
        record_decision(
            source="orchestrator",
            title=title,
            description=(summary or "")[:2000] or None,
            rationale=synthesis.get("general_conclusion"),
            disciplines=disciplines,
            project_id=project_id,
            meta={"orchestrator_log_id": str(orchestrator_log_id) if orchestrator_log_id else None},
            db=session,
        )

    try:
        if db is not None:
            _persist(db)
            db.commit()
        else:
            with session_scope() as session:
                _persist(session)
    except Exception as exc:
        logger.warning("Falha ao capturar orchestrator: %s", exc)


def record_vision_completion(
    *,
    project_id: str | uuid.UUID,
    mode: str,
    analyzed: int,
    total: int,
    errors: int = 0,
    db: Session | None = None,
) -> None:
    """Auto-captura após análise visual."""
    title = f"Análise visual ({mode}): {analyzed}/{total} arquivo(s)"
    record_activity(
        source="vision",
        event_type="completed" if errors == 0 else "partial",
        title=title,
        summary=f"{analyzed} analisado(s), {errors} erro(s)" if errors else f"{analyzed} arquivo(s) processado(s)",
        project_id=project_id,
        phase=mode,
        meta={"mode": mode, "analyzed": analyzed, "total": total, "errors": errors},
        db=db,
    )
    if analyzed > 0:
        record_decision(
            source="vision",
            title=f"Laudo visual — modo {mode}",
            description=f"Processados {analyzed} de {total} arquivos visuais.",
            project_id=project_id,
            meta={"mode": mode, "analyzed": analyzed},
            db=db,
        )


def record_budget_saved(
    *,
    project_id: str | uuid.UUID | None,
    title: str,
    grand_total: float,
    obra_type: str,
    budget_id: str | uuid.UUID,
    db: Session | None = None,
) -> None:
    """Auto-captura após salvar orçamento."""
    record_activity(
        source="budget",
        event_type="saved",
        title=f"Orçamento salvo: {title}",
        summary=f"Total R$ {grand_total:,.2f} · {obra_type}",
        project_id=project_id,
        phase="persist",
        meta={"budget_id": str(budget_id), "grand_total": grand_total, "obra_type": obra_type},
        db=db,
    )
    if project_id:
        record_decision(
            source="budget",
            title=f"Orçamento {obra_type}: {title}",
            description=f"Valor global R$ {grand_total:,.2f}",
            project_id=project_id,
            meta={"budget_id": str(budget_id), "grand_total": grand_total},
            db=db,
        )


def list_project_activity(
    db: Session,
    project_id: str | uuid.UUID,
    limit: int = 100,
) -> list[dict[str, Any]]:
    pid = _parse_uuid(project_id)
    if not pid:
        return []
    stmt = (
        select(ProjectActivityEvent)
        .where(ProjectActivityEvent.project_id == pid)
        .order_by(desc(ProjectActivityEvent.created_at))
        .limit(limit)
    )
    rows = list(db.scalars(stmt).all())
    return [serialize_activity(r) for r in rows]


def list_project_decisions(
    db: Session,
    project_id: str | uuid.UUID,
    limit: int = 50,
) -> list[dict[str, Any]]:
    pid = _parse_uuid(project_id)
    if not pid:
        return []
    stmt = (
        select(ProjectDecision)
        .where(ProjectDecision.project_id == pid)
        .order_by(desc(ProjectDecision.created_at))
        .limit(limit)
    )
    rows = list(db.scalars(stmt).all())
    return [serialize_decision(r) for r in rows]


def list_console_logs(db: Session, limit: int = 50) -> list[dict[str, Any]]:
    """Logs recentes do orchestrator com agent_runs aninhados."""
    stmt = (
        select(OrchestratorLog)
        .order_by(desc(OrchestratorLog.created_at))
        .limit(limit)
    )
    logs = list(db.scalars(stmt).all())
    log_ids = [log.id for log in logs]
    runs_by_log: dict[uuid.UUID, list[AgentRun]] = {lid: [] for lid in log_ids}

    if log_ids:
        runs_stmt = (
            select(AgentRun)
            .where(AgentRun.orchestrator_log_id.in_(log_ids))
            .order_by(AgentRun.created_at)
        )
        for run in db.scalars(runs_stmt).all():
            if run.orchestrator_log_id:
                runs_by_log.setdefault(run.orchestrator_log_id, []).append(run)

    items: list[dict[str, Any]] = []
    for log in logs:
        conv_project_id = None
        if log.conversation_id:
            conv = db.get(Conversation, log.conversation_id)
            if conv and conv.project_id:
                conv_project_id = str(conv.project_id)

        items.append(
            {
                "id": str(log.id),
                "conversation_id": str(log.conversation_id) if log.conversation_id else None,
                "project_id": conv_project_id,
                "input_text": log.input_text,
                "disciplines": log.disciplines or [],
                "final_report": log.final_report,
                "synthesis": log.synthesis,
                "use_rag": log.use_rag,
                "agent_count": log.agent_count,
                "created_at": log.created_at.isoformat() if log.created_at else None,
                "agent_runs": [
                    {
                        "id": str(r.id),
                        "agent_name": r.agent_name,
                        "discipline": r.discipline,
                        "result_text": (r.result_text or "")[:500],
                        "had_context": r.had_context,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in runs_by_log.get(log.id, [])
                ],
            }
        )
    return items


def console_stats(db: Session) -> dict[str, Any]:
    from sqlalchemy import func

    orch_count = db.scalar(select(func.count()).select_from(OrchestratorLog)) or 0
    agent_count = db.scalar(select(func.count()).select_from(AgentRun)) or 0
    activity_count = db.scalar(select(func.count()).select_from(ProjectActivityEvent)) or 0
    decision_count = db.scalar(select(func.count()).select_from(ProjectDecision)) or 0
    return {
        "orchestrator_logs": orch_count,
        "agent_runs": agent_count,
        "activity_events": activity_count,
        "decisions": decision_count,
    }


def serialize_activity(row: ProjectActivityEvent) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "project_id": str(row.project_id) if row.project_id else None,
        "source": row.source,
        "event_type": row.event_type,
        "title": row.title,
        "summary": row.summary,
        "agent_name": row.agent_name,
        "discipline": row.discipline,
        "phase": row.phase,
        "meta": row.meta,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_decision(row: ProjectDecision) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "project_id": str(row.project_id) if row.project_id else None,
        "source": row.source,
        "title": row.title,
        "description": row.description,
        "rationale": row.rationale,
        "disciplines": row.disciplines,
        "meta": row.meta,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
