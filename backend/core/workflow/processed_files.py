"""Controle de arquivos já processados pelo workflow."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from core.database.workflow_models import WorkflowDrawing, WorkflowRevision


def file_already_processed(db: Session, project_id: str, file_id: str) -> bool:
    """True se o arquivo já passou pelo workflow (prancha ou indexação de documento)."""
    pid = uuid.UUID(project_id)
    fid = uuid.UUID(file_id)

    drawing = (
        db.query(WorkflowDrawing)
        .filter(
            WorkflowDrawing.project_id == pid,
            WorkflowDrawing.project_file_id == fid,
        )
        .first()
    )
    if drawing is not None:
        return True

    revision = (
        db.query(WorkflowRevision)
        .filter(
            WorkflowRevision.project_id == pid,
            WorkflowRevision.arquivo_origem_id == fid,
        )
        .first()
    )
    return revision is not None
