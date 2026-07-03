"""Controle de acesso a orçamentos persistidos por usuário e empresa (B1/B27)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Query, Session

from core.database.models import BudgetDocument, User


def budget_user_id(user: User | None) -> uuid.UUID | None:
    """UUID do dono quando auth ativo; None quando auth desligado (modo legado)."""
    return user.id if user else None


def user_is_admin(user: User | None) -> bool:
    return bool(user and user.role == "admin")


def user_can_access_budget(
    doc: BudgetDocument | None,
    user: User | None,
    *,
    tenant_id: uuid.UUID | None = None,
) -> bool:
    if doc is None:
        return False
    owner_id = budget_user_id(user)
    if owner_id is None:
        return True
    if user_is_admin(user):
        if tenant_id is not None and doc.empresa_id and doc.empresa_id != tenant_id:
            return False
        return True
    if doc.user_id is None:
        pass
    elif doc.user_id != owner_id:
        return False
    if tenant_id is not None and doc.empresa_id and doc.empresa_id != tenant_id:
        return False
    return True


def apply_budget_list_filter(
    query: Query,
    user: User | None,
    *,
    tenant_id: uuid.UUID | None = None,
) -> Query:
    owner_id = budget_user_id(user)
    if tenant_id is not None:
        query = query.filter(
            (BudgetDocument.empresa_id == tenant_id) | (BudgetDocument.empresa_id.is_(None))
        )
    if owner_id is None:
        return query
    if user_is_admin(user):
        return query
    return query.filter(
        (BudgetDocument.user_id == owner_id) | (BudgetDocument.user_id.is_(None))
    )
