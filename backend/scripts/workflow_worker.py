#!/usr/bin/env python3
"""Worker Celery do módulo Workflow Projetos."""

from core.workflow.workers.celery_app import celery_app

if __name__ == "__main__":
    celery_app.worker_main(argv=["worker", "-l", "info", "-Q", "workflow", "-c", "2"])
