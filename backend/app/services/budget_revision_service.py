"""Fluxo aditivo — baseline congelada + revisões (B6)."""

from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from core.database.budget_access import user_can_access_budget
from core.database.models import BudgetDocument, User
from pricing.budget.budget_baseline_compare import compare_budget_payloads


class BudgetBaselineFrozenError(Exception):
    """Tentativa de alterar orçamento baseline congelado."""


def _parse_uuid(value: str | uuid.UUID | None) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def is_baseline_frozen(doc: BudgetDocument) -> bool:
    return doc.baseline_frozen_at is not None


def baseline_root_id(doc: BudgetDocument) -> uuid.UUID:
    return doc.baseline_document_id or doc.id


def assert_editable(doc: BudgetDocument) -> None:
    if is_baseline_frozen(doc):
        raise BudgetBaselineFrozenError(
            "Orçamento baseline congelado — crie uma revisão (aditivo) para editar."
        )


def revision_meta(doc: BudgetDocument) -> dict[str, Any]:
    return {
        "baseline_document_id": str(doc.baseline_document_id) if doc.baseline_document_id else None,
        "revision_number": doc.revision_number or 0,
        "revision_label": doc.revision_label,
        "baseline_frozen": is_baseline_frozen(doc),
        "baseline_frozen_at": doc.baseline_frozen_at.isoformat() if doc.baseline_frozen_at else None,
    }


def freeze_baseline(db: Session, budget_id: str, user: User | None = None) -> dict[str, Any]:
    doc = db.get(BudgetDocument, uuid.UUID(budget_id))
    if not doc or not user_can_access_budget(doc, user):
        raise KeyError(f"Orçamento não encontrado: {budget_id}")
    if is_baseline_frozen(doc):
        raise ValueError("Baseline já congelada para este documento")
    if doc.baseline_document_id and doc.baseline_document_id != doc.id:
        raise ValueError("Somente o documento raiz pode ser congelado como baseline")

    now = datetime.now(timezone.utc)
    doc.baseline_frozen_at = now
    doc.baseline_snapshot = copy.deepcopy(doc.payload or {})
    doc.revision_number = 0
    doc.revision_label = doc.revision_label or "Baseline"
    doc.updated_at = now
    db.commit()
    db.refresh(doc)
    return {"document": doc.to_summary(), "revision": revision_meta(doc)}


def create_revision(
    db: Session,
    budget_id: str,
    user: User | None = None,
    *,
    revision_label: str | None = None,
) -> dict[str, Any]:
    source = db.get(BudgetDocument, uuid.UUID(budget_id))
    if not source or not user_can_access_budget(source, user):
        raise KeyError(f"Orçamento não encontrado: {budget_id}")

    root_id = baseline_root_id(source)
    root = db.get(BudgetDocument, root_id)
    if not root or not is_baseline_frozen(root):
        raise ValueError("Congele a baseline antes de criar revisões/aditivos")

    siblings = (
        db.query(BudgetDocument)
        .filter(
            (BudgetDocument.id == root_id)
            | (BudgetDocument.baseline_document_id == root_id)
        )
        .all()
    )
    next_num = max((s.revision_number or 0 for s in siblings), default=0) + 1
    label = revision_label or f"Aditivo {next_num:02d}"

    payload = copy.deepcopy(source.payload or {})
    new_session_id = uuid.uuid4().hex
    payload["session_id"] = new_session_id
    payload["title"] = f"{source.title} — {label}"
    payload["db_id"] = None

    now = datetime.now(timezone.utc)
    from core.database.budget_access import budget_user_id

    doc = BudgetDocument(
        id=uuid.uuid4(),
        title=payload["title"],
        project_id=source.project_id,
        user_id=budget_user_id(user) or source.user_id,
        version=1,
        session_id=new_session_id,
        payload=payload,
        grand_total=float(payload.get("grand_total") or source.grand_total),
        obra_type=source.obra_type,
        input_text=source.input_text,
        baseline_document_id=root_id,
        revision_number=next_num,
        revision_label=label,
        created_at=now,
        updated_at=now,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    from app.services.budget_db_service import get_budget

    loaded = get_budget(db, str(doc.id), user=user)
    return {
        "revision": revision_meta(doc),
        "document": doc.to_summary(),
        "session": loaded,
    }


def list_revisions(
    db: Session,
    budget_id: str,
    user: User | None = None,
) -> list[dict[str, Any]]:
    doc = db.get(BudgetDocument, uuid.UUID(budget_id))
    if not doc or not user_can_access_budget(doc, user):
        raise KeyError(f"Orçamento não encontrado: {budget_id}")

    root_id = baseline_root_id(doc)
    rows = (
        db.query(BudgetDocument)
        .filter(
            (BudgetDocument.id == root_id)
            | (BudgetDocument.baseline_document_id == root_id)
        )
        .order_by(BudgetDocument.revision_number.asc(), BudgetDocument.created_at.asc())
        .all()
    )
    return [{**r.to_summary(), **revision_meta(r)} for r in rows]


def compare_with_baseline(
    db: Session,
    budget_id: str,
    user: User | None = None,
) -> dict[str, Any]:
    doc = db.get(BudgetDocument, uuid.UUID(budget_id))
    if not doc or not user_can_access_budget(doc, user):
        raise KeyError(f"Orçamento não encontrado: {budget_id}")

    root_id = baseline_root_id(doc)
    root = db.get(BudgetDocument, root_id)
    if not root or not root.baseline_snapshot:
        raise ValueError("Baseline ainda não congelada — use Congelar baseline primeiro")

    comparison = compare_budget_payloads(root.baseline_snapshot, doc.payload or {})
    return {
        "baseline_document_id": str(root_id),
        "revision": revision_meta(doc),
        "comparison": comparison,
    }
