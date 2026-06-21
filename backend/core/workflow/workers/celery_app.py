"""Celery app — fila workflow."""

from __future__ import annotations

from celery import Celery

from config.settings import get_settings


def make_celery() -> Celery:
    settings = get_settings()
    app = Celery("ia_workflow", broker=settings.redis_url, backend=settings.redis_url)
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_default_queue="workflow",
        imports=("core.workflow.workers.tasks",),
    )
    return app


celery_app = make_celery()
