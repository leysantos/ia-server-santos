from __future__ import annotations

from collections.abc import Iterator
from typing import Any

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
            for event_type, data in self._orchestrator.run_events(
                text,
                source_priority=source_priority,
                use_llm=use_llm,
                obra_type=obra_type,
                existing_session_id=existing_session_id,
            ):
                yield format_sse(event_type, data)
        except Exception as exc:
            yield format_sse("error", {"message": str(exc), "phase": "error"})
