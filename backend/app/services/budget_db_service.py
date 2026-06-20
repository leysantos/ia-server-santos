from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from core.database.models import BudgetDocument
from pricing.budget.budget_session import SESSION_STORE, BudgetSession
from pricing.models.budget_metadata import BudgetProjectMetadata
from pricing.schedule.schedule_models import ProjectSchedule


def _deserialize_item(data: dict[str, Any]):
    from pricing.budget.budget_session import _deserialize_item as _des

    return _des(data)


def session_from_payload(payload: dict[str, Any]) -> BudgetSession:
    """Reconstrói sessão em memória a partir de payload salvo."""
    roots = [_deserialize_item(i) for i in payload.get("items") or []]
    project = BudgetProjectMetadata.from_dict(payload.get("project") or {})
    session = BudgetSession(
        id=payload.get("session_id") or uuid.uuid4().hex,
        title=payload.get("title") or "Orçamento",
        roots=roots,
        source_priority=list(payload.get("source_priority") or []),
        intent=dict(payload.get("intent") or {}),
        project=project,
        calculation_memory=list(payload.get("calculation_memory") or []),
        schedule=ProjectSchedule.from_dict(payload.get("schedule")),
        tech_spec=payload.get("tech_spec"),
        created_at=payload.get("created_at") or datetime.now(timezone.utc).isoformat(),
        updated_at=payload.get("updated_at") or datetime.now(timezone.utc).isoformat(),
    )
    SESSION_STORE._sessions[session.id] = session  # noqa: SLF001
    return session


def _parse_uuid(value: str | uuid.UUID | None) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def list_budgets(db: Session, limit: int = 50, project_id: str | None = None) -> list[dict[str, Any]]:
    query = db.query(BudgetDocument).order_by(BudgetDocument.updated_at.desc())
    parsed_project_id = _parse_uuid(project_id)
    if parsed_project_id:
        query = query.filter(BudgetDocument.project_id == parsed_project_id)
    rows = query.limit(limit).all()
    return [r.to_summary() for r in rows]


def get_budget(db: Session, budget_id: str) -> dict[str, Any] | None:
    doc = db.get(BudgetDocument, uuid.UUID(budget_id))
    if not doc:
        return None
    payload = dict(doc.payload or {})
    payload["db_id"] = str(doc.id)
    if doc.project_id:
        payload["project_id"] = str(doc.project_id)
    session_from_payload(payload)
    return payload


def save_budget(
    db: Session,
    payload: dict[str, Any],
    title: str | None = None,
    input_text: str | None = None,
    budget_id: str | None = None,
    project_id: str | uuid.UUID | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    doc_title = title or payload.get("title") or "Orçamento"
    grand_total = float(payload.get("grand_total") or 0)
    obra_type = (payload.get("project") or {}).get("obra_type") or "RF"
    session_id = payload.get("session_id") or uuid.uuid4().hex
    parsed_project_id = _parse_uuid(project_id)

    if budget_id:
        doc = db.get(BudgetDocument, uuid.UUID(budget_id))
        if not doc:
            raise KeyError(f"Orçamento não encontrado: {budget_id}")
        doc.title = doc_title
        doc.session_id = session_id
        doc.payload = payload
        doc.grand_total = grand_total
        doc.obra_type = obra_type
        doc.input_text = input_text or doc.input_text
        if project_id is not None:
            doc.project_id = parsed_project_id
        doc.updated_at = now
    else:
        doc = BudgetDocument(
            id=uuid.uuid4(),
            title=doc_title,
            project_id=parsed_project_id,
            session_id=session_id,
            payload=payload,
            grand_total=grand_total,
            obra_type=obra_type,
            input_text=input_text,
            created_at=now,
            updated_at=now,
        )
        db.add(doc)

    db.commit()
    db.refresh(doc)
    result = dict(payload)
    result["db_id"] = str(doc.id)
    if doc.project_id:
        result["project_id"] = str(doc.project_id)
    try:
        from core.project_memory.service import record_budget_saved

        record_budget_saved(
            project_id=doc.project_id,
            title=doc_title,
            grand_total=grand_total,
            obra_type=obra_type,
            budget_id=doc.id,
            db=db,
        )
    except Exception:
        pass
    return result


def delete_budget(db: Session, budget_id: str) -> bool:
    doc = db.get(BudgetDocument, uuid.UUID(budget_id))
    if not doc:
        return False
    db.delete(doc)
    db.commit()
    return True
