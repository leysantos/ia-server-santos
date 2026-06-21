"""Tarefas Celery do workflow."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from core.database.connection import session_scope
from core.database.workflow_models import WorkflowJob
from core.workflow.orchestrator import get_workflow_orchestrator
from core.workflow.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _update_job(job_id: str, **fields) -> None:
    with session_scope() as db:
        row = db.get(WorkflowJob, uuid.UUID(job_id))
        if not row:
            return
        for key, value in fields.items():
            setattr(row, key, value)


@celery_app.task(name="workflow.process_file", bind=True, max_retries=1)
def process_file_task(self, job_id: str, project_id: str, file_id: str) -> dict:
    _update_job(job_id, status="running", started_at=datetime.now(timezone.utc), celery_task_id=self.request.id)
    try:
        with session_scope() as db:
            from core.database.models import ProjectFile

            pf = db.get(ProjectFile, uuid.UUID(file_id))
            if not pf:
                raise ValueError("Arquivo não encontrado")
            result = get_workflow_orchestrator().process_file(project_id, pf, db, actor="celery")
        _update_job(
            job_id,
            status="completed",
            result=result,
            completed_at=datetime.now(timezone.utc),
        )
        return result
    except Exception as exc:
        logger.exception("workflow process_file_task failed: %s", exc)
        _update_job(
            job_id,
            status="failed",
            error=str(exc),
            completed_at=datetime.now(timezone.utc),
        )
        raise


@celery_app.task(name="workflow.process_project", bind=True, max_retries=1)
def process_project_task(self, job_id: str, project_id: str) -> dict:
    _update_job(job_id, status="running", started_at=datetime.now(timezone.utc), celery_task_id=self.request.id)
    try:
        with session_scope() as db:
            result = get_workflow_orchestrator().run_full_pipeline(project_id, db, actor="celery")
        _update_job(
            job_id,
            status="completed",
            result=result,
            completed_at=datetime.now(timezone.utc),
        )
        return result
    except Exception as exc:
        logger.exception("workflow process_project_task failed: %s", exc)
        _update_job(
            job_id,
            status="failed",
            error=str(exc),
            completed_at=datetime.now(timezone.utc),
        )
        raise
