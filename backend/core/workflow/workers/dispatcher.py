"""Dispatcher — Celery com fallback thread local."""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from config.settings import get_settings
from core.database.workflow_models import WorkflowJob

logger = logging.getLogger(__name__)


def _redis_available(redis_url: str) -> bool:
    try:
        import redis

        client = redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
        client.ping()
        return True
    except Exception:
        return False


def create_job_record(
    db: Session,
    *,
    project_id: str,
    job_type: str,
    file_id: str | None = None,
    payload: dict | None = None,
) -> WorkflowJob:
    row = WorkflowJob(
        project_id=uuid.UUID(project_id),
        job_type=job_type,
        status="pending",
        file_id=uuid.UUID(file_id) if file_id else None,
        payload=payload or {},
    )
    db.add(row)
    db.flush()
    return row


def _run_file_sync(job_id: str, project_id: str, file_id: str) -> None:
    from core.database.connection import session_scope
    from core.database.models import ProjectFile
    from core.workflow.orchestrator import get_workflow_orchestrator

    try:
        with session_scope() as db:
            job = db.get(WorkflowJob, uuid.UUID(job_id))
            if job:
                job.status = "running"
                job.started_at = datetime.now(timezone.utc)
            pf = db.get(ProjectFile, uuid.UUID(file_id))
            result = get_workflow_orchestrator().process_file(project_id, pf, db, actor="thread")
            if job:
                job.status = "completed"
                job.result = result
                job.completed_at = datetime.now(timezone.utc)
    except Exception as exc:
        logger.exception("workflow thread job failed: %s", exc)
        with session_scope() as db:
            job = db.get(WorkflowJob, uuid.UUID(job_id))
            if job:
                job.status = "failed"
                job.error = str(exc)
                job.completed_at = datetime.now(timezone.utc)


def _run_project_sync(job_id: str, project_id: str) -> None:
    from core.database.connection import session_scope
    from core.workflow.orchestrator import get_workflow_orchestrator

    try:
        with session_scope() as db:
            job = db.get(WorkflowJob, uuid.UUID(job_id))
            if job:
                job.status = "running"
                job.started_at = datetime.now(timezone.utc)
            result = get_workflow_orchestrator().run_full_pipeline(project_id, db, actor="thread")
            if job:
                job.status = "completed"
                job.result = result
                job.completed_at = datetime.now(timezone.utc)
    except Exception as exc:
        logger.exception("workflow thread project job failed: %s", exc)
        with session_scope() as db:
            job = db.get(WorkflowJob, uuid.UUID(job_id))
            if job:
                job.status = "failed"
                job.error = str(exc)
                job.completed_at = datetime.now(timezone.utc)


def enqueue_process_file(db: Session, project_id: str, file_id: str, *, sync: bool = False) -> dict[str, Any]:
    settings = get_settings()
    job = create_job_record(db, project_id=project_id, job_type="process_file", file_id=file_id)
    job_id = str(job.id)

    use_celery = settings.workflow_use_celery and not sync and _redis_available(settings.redis_url)
    if use_celery:
        try:
            from core.workflow.workers.tasks import process_file_task

            async_result = process_file_task.delay(job_id, project_id, file_id)
            job.celery_task_id = async_result.id
            job.status = "queued"
            db.commit()
            return {"mode": "celery", "job_id": job_id, "task_id": async_result.id, "status": "queued"}
        except Exception as exc:
            logger.warning("Celery enqueue failed, fallback thread: %s", exc)
            db.rollback()
            job = create_job_record(db, project_id=project_id, job_type="process_file", file_id=file_id)
            job_id = str(job.id)

    db.commit()
    thread = threading.Thread(
        target=_run_file_sync,
        args=(job_id, project_id, file_id),
        daemon=True,
        name=f"wf-file-{job_id[:8]}",
    )
    thread.start()
    return {"mode": "thread", "job_id": job_id, "status": "running"}


def enqueue_process_project(db: Session, project_id: str, *, sync: bool = False) -> dict[str, Any]:
    settings = get_settings()
    job = create_job_record(db, project_id=project_id, job_type="process_project")
    job_id = str(job.id)

    use_celery = settings.workflow_use_celery and not sync and _redis_available(settings.redis_url)
    if use_celery:
        try:
            from core.workflow.workers.tasks import process_project_task

            async_result = process_project_task.delay(job_id, project_id)
            job.celery_task_id = async_result.id
            job.status = "queued"
            db.commit()
            return {"mode": "celery", "job_id": job_id, "task_id": async_result.id, "status": "queued"}
        except Exception as exc:
            logger.warning("Celery enqueue failed, fallback thread: %s", exc)
            db.rollback()
            job = create_job_record(db, project_id=project_id, job_type="process_project")
            job_id = str(job.id)

    db.commit()
    thread = threading.Thread(
        target=_run_project_sync,
        args=(job_id, project_id),
        daemon=True,
        name=f"wf-project-{job_id[:8]}",
    )
    thread.start()
    return {"mode": "thread", "job_id": job_id, "status": "running"}


def serialize_job(row: WorkflowJob) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "project_id": str(row.project_id),
        "job_type": row.job_type,
        "status": row.status,
        "celery_task_id": row.celery_task_id,
        "file_id": str(row.file_id) if row.file_id else None,
        "result": row.result,
        "error": row.error,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }
