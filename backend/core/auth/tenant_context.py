"""Contexto multi-empresa via header X-Tenant-Id (B27)."""

from __future__ import annotations

import uuid

from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from core.database.models import User
from core.database.budget_access import user_is_admin


def parse_tenant_header(x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")) -> uuid.UUID | None:
    if not x_tenant_id or not str(x_tenant_id).strip():
        return None
    try:
        return uuid.UUID(str(x_tenant_id).strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="X-Tenant-Id inválido") from exc


def resolve_company_id(
    db: Session,
    tenant_id: uuid.UUID | None,
    *,
    project_id: uuid.UUID | None = None,
) -> uuid.UUID | None:
    """Empresa efetiva: header → project.empresa_id."""
    if tenant_id is not None:
        return tenant_id
    if project_id is None:
        return None
    from core.database.models import Project

    project = db.get(Project, project_id)
    if project and getattr(project, "empresa_id", None):
        return project.empresa_id
    return None


def assert_tenant_access(
    db: Session,
    empresa_id: uuid.UUID | None,
    user: User | None,
    tenant_header: uuid.UUID | None,
) -> None:
    """Non-admin só acessa docs da empresa do header (quando informado)."""
    if empresa_id is None or user is None:
        return
    if user_is_admin(user):
        return
    if tenant_header is None:
        return
    if empresa_id != tenant_header:
        raise HTTPException(status_code=403, detail="Orçamento pertence a outra empresa")


def company_exists(db: Session, empresa_id: uuid.UUID | None) -> bool:
    if empresa_id is None:
        return True
    try:
        import core.database.workflow_models  # noqa: F401
        from core.database.workflow_models import Company

        row = db.get(Company, empresa_id)
        return bool(row and row.ativo)
    except Exception:
        return False
