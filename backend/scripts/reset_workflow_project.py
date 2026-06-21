#!/usr/bin/env python3
"""
Reseta artefatos de workflow de um projeto e opcionalmente reprocessa com classificador atual.

Uso:
  python scripts/reset_workflow_project.py <project_id> [--reprocess] [--keep-jobs]
"""

from __future__ import annotations

import argparse
import shutil
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import session_scope
from core.database.models import Project
from core.database.workflow_models import (
    WorkflowDelivery,
    WorkflowDrawing,
    WorkflowEvent,
    WorkflowJob,
    WorkflowRevision,
    WorkflowSheet,
    WorkflowVersion,
)
from core.workflow.orchestrator import get_workflow_orchestrator
from core.workflow.storage.client import WORKFLOW_LOCAL_ROOT, get_workflow_storage


def _collect_storage_keys(db, project_id: uuid.UUID) -> set[str]:
    keys: set[str] = set()
    deliveries = (
        db.query(WorkflowDelivery)
        .filter(WorkflowDelivery.project_id == project_id)
        .all()
    )
    for row in deliveries:
        manifest = row.manifest or {}
        for section in ("pdf", "zip", "sheet_pdf"):
            info = manifest.get(section)
            if isinstance(info, dict) and info.get("key"):
                keys.add(str(info["key"]))
    return keys


def _purge_storage_artifacts(project_id: str, extra_keys: set[str]) -> int:
    removed = 0
    storage = get_workflow_storage()
    prefix = f"default/{project_id}/"

    if storage.backend == "minio":
        client = storage._client  # noqa: SLF001
        bucket = storage.bucket
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents") or []:
                client.delete_object(Bucket=bucket, Key=obj["Key"])
                removed += 1
        for key in extra_keys:
            if storage.exists(key):
                client.delete_object(Bucket=bucket, Key=key)
                removed += 1
    else:
        local_prefix = WORKFLOW_LOCAL_ROOT / prefix.rstrip("/")
        if local_prefix.exists():
            shutil.rmtree(local_prefix)
            removed += sum(1 for _ in local_prefix.rglob("*")) if local_prefix.exists() else 1
        for key in extra_keys:
            path = WORKFLOW_LOCAL_ROOT / key
            if path.exists():
                path.unlink()
                removed += 1

    return removed


def reset_workflow_project(
    project_id: str,
    *,
    reprocess: bool = False,
    keep_jobs: bool = False,
) -> dict:
    pid = uuid.UUID(project_id)
    stats: dict[str, int | dict] = {}

    with session_scope() as db:
        project = db.get(Project, pid)
        if not project:
            raise SystemExit(f"Projeto não encontrado: {project_id}")

        print(f"Reset workflow — {project.name} ({project_id})")
        print(f"  versao_atual antes: {project.versao_atual}")

        storage_keys = _collect_storage_keys(db, pid)

        stats["deliveries"] = (
            db.query(WorkflowDelivery).filter(WorkflowDelivery.project_id == pid).delete()
        )
        db.query(WorkflowVersion).filter(WorkflowVersion.project_id == pid).update(
            {WorkflowVersion.parent_id: None}
        )
        stats["versions"] = (
            db.query(WorkflowVersion).filter(WorkflowVersion.project_id == pid).delete()
        )
        stats["revisions"] = (
            db.query(WorkflowRevision).filter(WorkflowRevision.project_id == pid).delete()
        )
        stats["sheets"] = (
            db.query(WorkflowSheet).filter(WorkflowSheet.project_id == pid).delete()
        )
        stats["drawings"] = (
            db.query(WorkflowDrawing).filter(WorkflowDrawing.project_id == pid).delete()
        )
        stats["events"] = (
            db.query(WorkflowEvent).filter(WorkflowEvent.project_id == pid).delete()
        )
        if not keep_jobs:
            stats["jobs"] = (
                db.query(WorkflowJob).filter(WorkflowJob.project_id == pid).delete()
            )

        project.versao_atual = "REV00"
        db.flush()

        stats["storage_removed"] = _purge_storage_artifacts(project_id, storage_keys)
        print(f"  removidos: {stats}")

        if reprocess:
            orchestrator = get_workflow_orchestrator()
            result = orchestrator.run_full_pipeline(project_id, db, force=True)
            stats["reprocess"] = result
            print(
                "  reprocessado:",
                f"{result.get('pranchas', 0)} prancha(s),",
                f"{result.get('documentos', 0)} documento(s),",
                f"versao_atual={project.versao_atual}",
            )

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset workflow de um projeto")
    parser.add_argument("project_id", help="UUID do projeto")
    parser.add_argument(
        "--reprocess",
        action="store_true",
        help="Reexecuta pipeline completo após limpeza (force=True)",
    )
    parser.add_argument(
        "--keep-jobs",
        action="store_true",
        help="Mantém histórico de workflow_jobs",
    )
    args = parser.parse_args()
    reset_workflow_project(
        args.project_id,
        reprocess=args.reprocess,
        keep_jobs=args.keep_jobs,
    )
    print("OK")


if __name__ == "__main__":
    main()
