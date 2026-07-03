from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from core.database.budget_access import (
    apply_budget_list_filter,
    budget_user_id,
    user_can_access_budget,
)
from core.database.models import BudgetDocument, User
from pricing.budget.budget_session import SESSION_STORE, BudgetSession
from pricing.models.budget_metadata import BudgetProjectMetadata
from pricing.schedule.schedule_models import ProjectSchedule


class BudgetVersionConflictError(Exception):
    """Conflito de lock otimista — outro save ocorreu antes."""

    def __init__(self, current_version: int):
        self.current_version = current_version
        super().__init__(
            f"Conflito de versão: o documento foi alterado (versão atual {current_version}). "
            "Recarregue o orçamento e tente salvar novamente."
        )


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
        audit_log=list(payload.get("audit_log") or []),
        db_id=payload.get("db_id"),
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


def _attach_document_meta(payload: dict[str, Any], doc: BudgetDocument) -> dict[str, Any]:
    from app.services.budget_revision_service import revision_meta

    result = dict(payload)
    result["db_id"] = str(doc.id)
    result["document_version"] = doc.version
    if doc.project_id:
        result["project_id"] = str(doc.project_id)
    if doc.user_id:
        result["user_id"] = str(doc.user_id)
    if doc.empresa_id:
        result["empresa_id"] = str(doc.empresa_id)
    result.update(revision_meta(doc))
    return result


def list_budgets(
    db: Session,
    limit: int = 50,
    project_id: str | None = None,
    user: User | None = None,
    *,
    mine_only: bool = False,
    tenant_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    query = db.query(BudgetDocument).order_by(BudgetDocument.updated_at.desc())
    parsed_project_id = _parse_uuid(project_id)
    if parsed_project_id:
        query = query.filter(BudgetDocument.project_id == parsed_project_id)
    if mine_only and budget_user_id(user) is not None:
        owner_id = budget_user_id(user)
        query = query.filter(BudgetDocument.user_id == owner_id)
    else:
        query = apply_budget_list_filter(query, user, tenant_id=tenant_id)
    rows = query.limit(limit).all()
    return [r.to_summary() for r in rows]


def get_budget(
    db: Session,
    budget_id: str,
    user: User | None = None,
    *,
    tenant_id: uuid.UUID | None = None,
) -> dict[str, Any] | None:
    doc = db.get(BudgetDocument, uuid.UUID(budget_id))
    if not doc or not user_can_access_budget(doc, user, tenant_id=tenant_id):
        return None
    payload = dict(doc.payload or {})
    payload["db_id"] = str(doc.id)
    session = session_from_payload(payload)
    session.db_id = str(doc.id)
    return _attach_document_meta(payload, doc)


def save_budget(
    db: Session,
    payload: dict[str, Any],
    title: str | None = None,
    input_text: str | None = None,
    budget_id: str | None = None,
    project_id: str | uuid.UUID | None = None,
    user: User | None = None,
    expected_version: int | None = None,
    *,
    tenant_id: uuid.UUID | None = None,
    empresa_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    from core.auth.tenant_context import company_exists, resolve_company_id

    now = datetime.now(timezone.utc)
    doc_title = title or payload.get("title") or "Orçamento"
    grand_total = float(payload.get("grand_total") or 0)
    obra_type = (payload.get("project") or {}).get("obra_type") or "RF"
    session_id = payload.get("session_id") or uuid.uuid4().hex
    parsed_project_id = _parse_uuid(project_id)
    owner_id = budget_user_id(user)
    resolved_empresa = resolve_company_id(
        db, empresa_id or tenant_id, project_id=parsed_project_id
    )
    if resolved_empresa and not company_exists(db, resolved_empresa):
        raise ValueError("Empresa (tenant) inválida ou inativa")

    if budget_id:
        doc = db.get(BudgetDocument, uuid.UUID(budget_id))
        if not doc:
            raise KeyError(f"Orçamento não encontrado: {budget_id}")
        if not user_can_access_budget(doc, user, tenant_id=tenant_id):
            raise PermissionError("Sem permissão para alterar este orçamento")
        from app.services.budget_revision_service import assert_editable

        assert_editable(doc)
        if expected_version is not None and doc.version != expected_version:
            raise BudgetVersionConflictError(doc.version)
        doc.title = doc_title
        doc.session_id = session_id
        doc.payload = payload
        doc.grand_total = grand_total
        doc.obra_type = obra_type
        doc.input_text = input_text or doc.input_text
        if project_id is not None:
            doc.project_id = parsed_project_id
        if resolved_empresa and doc.empresa_id is None:
            doc.empresa_id = resolved_empresa
        doc.version = (doc.version or 1) + 1
        doc.updated_at = now
    else:
        doc = BudgetDocument(
            id=uuid.uuid4(),
            title=doc_title,
            project_id=parsed_project_id,
            user_id=owner_id,
            empresa_id=resolved_empresa,
            version=1,
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
    result = _attach_document_meta(payload, doc)
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


def delete_budget(
    db: Session,
    budget_id: str,
    user: User | None = None,
    *,
    tenant_id: uuid.UUID | None = None,
) -> bool:
    doc = db.get(BudgetDocument, uuid.UUID(budget_id))
    if not doc or not user_can_access_budget(doc, user, tenant_id=tenant_id):
        return False
    db.delete(doc)
    db.commit()
    return True
