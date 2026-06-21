"""Chaves de armazenamento workflow — tenant/project/discipline/revision/version."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def sanitize_segment(value: str | None, *, fallback: str = "geral") -> str:
    raw = (value or fallback).strip()
    cleaned = re.sub(r"[^\w\-.]+", "_", raw, flags=re.UNICODE)
    return cleaned or fallback


def build_storage_key(
    *,
    tenant: str | None,
    project_id: str,
    discipline: str | None = None,
    revision: str | None = None,
    version: str | None = None,
    filename: str,
) -> str:
    parts = [
        sanitize_segment(tenant, fallback="default"),
        sanitize_segment(project_id, fallback="project"),
        sanitize_segment(discipline, fallback="geral"),
        sanitize_segment(revision, fallback="REV00"),
        sanitize_segment(version, fallback="v1"),
        Path(filename).name if filename else "artifact.bin",
    ]
    return "/".join(parts)


def build_context_from_project(project: Any, ctx: dict[str, Any]) -> dict[str, str]:
    tenant = ctx.get("tenant") or ctx.get("tenant_id")
    if not tenant and getattr(project, "empresa_id", None):
        tenant = str(project.empresa_id)
    return {
        "tenant": tenant or "default",
        "project_id": str(getattr(project, "id", ctx.get("project_id", ""))),
        "discipline": ctx.get("disciplina") or getattr(project, "disciplina", None) or "geral",
        "revision": ctx.get("revisao") or getattr(project, "versao_atual", None) or "REV00",
        "version": ctx.get("version") or ctx.get("commit_hash") or "v1",
    }
