"""Controle de acesso a laudos de vistoria por usuário (L1)."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from core.database.models import User
from core.inspection_report.models import InspectionReport


def report_user_id(user: User | None) -> uuid.UUID | None:
    """UUID do dono quando auth ativo; None quando auth desligado (modo legado)."""
    return user.id if user else None


def user_is_admin(user: User | None) -> bool:
    return bool(user and user.role == "admin")


def user_can_access_report(report: InspectionReport | None, user: User | None) -> bool:
    if report is None:
        return False
    owner_id = report_user_id(user)
    if owner_id is None:
        return True
    if user_is_admin(user):
        return True
    if report.user_id is None:
        return True
    return report.user_id == owner_id


def require_report_access(
    db: Session,
    report_id: uuid.UUID,
    user: User | None,
) -> InspectionReport:
    from core.inspection_report import service as svc

    report = svc.get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Laudo não encontrado")
    if not user_can_access_report(report, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para acessar este laudo",
        )
    return report
