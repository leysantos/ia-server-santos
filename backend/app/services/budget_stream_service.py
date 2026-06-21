from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from core.runtime.job_tracking import label_from_text, track_stream_job
from core.stream_events import format_sse
from pricing.orchestrator.budget_orchestrator import BudgetOrchestrator


class BudgetStreamService:
    """Streaming SSE do pipeline de orçamento — intent → qty → pricing → budget."""

    def __init__(self, orchestrator: BudgetOrchestrator | None = None) -> None:
        self._orchestrator = orchestrator or BudgetOrchestrator()

    def stream(
        self,
        text: str,
        source_priority: list[str] | None = None,
        use_llm: bool = True,
        obra_type: str | None = None,
        existing_session_id: str | None = None,
    ) -> Iterator[str]:
        yield format_sse("status", {"message": "Conectado — iniciando pipeline de orçamento…", "phase": "connected"})
        try:
            with track_stream_job(
                kind="budget",
                label=label_from_text(text),
                meta={"session_id": existing_session_id} if existing_session_id else {},
            ) as runtime_job:
                for event_type, data in self._orchestrator.run_events(
                    text,
                    source_priority=source_priority,
                    use_llm=use_llm,
                    obra_type=obra_type,
                    existing_session_id=existing_session_id,
                ):
                    runtime_job.update_from_stream(event_type, data)
                    if event_type == "step" and isinstance(data.get("step"), str):
                        runtime_job.update(phase=data["step"], message=data.get("message"))
                    yield format_sse(event_type, data)
        except Exception as exc:
            yield format_sse("error", {"message": str(exc), "phase": "error"})
