"""Helpers para registrar jobs longos no Operations Console."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from config.settings import (
    OLLAMA_BUDGET_MODEL,
    OLLAMA_CHAT_MODEL,
    OLLAMA_EMBED_MODEL,
    OLLAMA_LLM_MODEL,
)
from core.llm_override import get_llm_model_override
from core.runtime.job_registry import get_job_registry
from core.runtime.ops_log import append_ops_log


def _truncate_label(text: str, max_len: int = 72) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1] + "…"


def resolve_runtime_model(kind: str) -> str | None:
    override = get_llm_model_override()
    if override:
        return override
    if kind == "chat":
        return OLLAMA_CHAT_MODEL
    if kind == "budget":
        return OLLAMA_BUDGET_MODEL
    if kind == "vision":
        return None
    if kind == "review":
        return OLLAMA_LLM_MODEL
    if kind in ("knowledge", "norm_bulk"):
        return OLLAMA_EMBED_MODEL
    return OLLAMA_LLM_MODEL


class TrackedJob:
    def __init__(
        self,
        *,
        kind: str,
        label: str,
        project_id: str | None = None,
        model: str | None = None,
        meta: dict | None = None,
    ) -> None:
        self.registry = get_job_registry()
        self.job = self.registry.register(
            kind=kind,
            label=label,
            project_id=project_id,
            model=model or resolve_runtime_model(kind),
            meta=meta or {},
        )
        append_ops_log(
            source=kind,
            message=f"Iniciado: {label}",
            project_id=project_id,
            job_id=self.job.id,
            phase="start",
        )

    @property
    def id(self) -> str:
        return self.job.id

    def update(self, *, log: bool = True, **fields: Any) -> None:
        self.registry.update(self.job.id, **fields)
        if not log:
            return
        message = fields.get("message")
        if message:
            phase = fields.get("phase")
            current = self.registry.get(self.job.id)
            append_ops_log(
                source=self.job.kind,
                message=str(message),
                project_id=self.job.project_id,
                job_id=self.job.id,
                phase=str(phase or (current.phase if current else None)),
            )

    def finish(self, *, status: str = "completed", message: str | None = None) -> None:
        self.registry.finish(self.job.id, status=status, message=message)
        level = "error" if status == "error" else "info"
        append_ops_log(
            source=self.job.kind,
            message=message or status,
            level=level,
            project_id=self.job.project_id,
            job_id=self.job.id,
            phase=status,
        )

    def update_from_stream(self, event_type: str, data: dict[str, Any]) -> None:
        phase = data.get("phase") or event_type
        message = data.get("message")
        fields: dict[str, Any] = {"phase": phase}
        if message:
            fields["message"] = message
        if "step" in data:
            current = self.registry.get(self.job.id)
            prev_meta = dict(current.meta if current else self.job.meta)
            fields["meta"] = {**prev_meta, "step": data["step"]}
        if event_type == "done":
            self.finish(status="completed", message=message or "Concluído")
            return
        if event_type == "error":
            self.finish(status="error", message=message or "Erro")
            return
        self.update(**fields)


@contextmanager
def track_stream_job(
    *,
    kind: str,
    label: str,
    project_id: str | None = None,
    model: str | None = None,
    meta: dict | None = None,
) -> Iterator[TrackedJob]:
    job = TrackedJob(kind=kind, label=label, project_id=project_id, model=model, meta=meta)
    try:
        yield job
        if job.job.status == "running":
            job.finish(status="completed")
    except Exception as exc:
        job.finish(status="error", message=str(exc))
        raise


@contextmanager
def track_sync_job(
    *,
    kind: str,
    label: str,
    project_id: str | None = None,
    model: str | None = None,
    meta: dict | None = None,
) -> Iterator[TrackedJob]:
    with track_stream_job(
        kind=kind,
        label=label,
        project_id=project_id,
        model=model,
        meta=meta,
    ) as job:
        yield job


def label_from_text(text: str) -> str:
    return _truncate_label(text)
