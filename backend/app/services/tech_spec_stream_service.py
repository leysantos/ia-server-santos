from __future__ import annotations

from collections.abc import Iterator
from typing import Literal

from core.stream_events import format_sse
from pricing.budget.budget_session import SESSION_STORE
from pricing.spec.tech_spec_agent import build_budget_context, compose_tech_spec_stream
from pricing.spec.tech_spec_editor import edit_tech_spec_stream
from pricing.spec.tech_spec_models import TechSpecDocument

TechSpecMode = Literal["generate", "edit"]


class TechSpecStreamService:
    """Streaming SSE — geração e edição da Especificação Técnica."""

    def stream(
        self,
        session_id: str,
        prompt: str = "",
        *,
        mode: TechSpecMode = "generate",
        use_llm: bool = True,
    ) -> Iterator[str]:
        session = SESSION_STORE.get(session_id)
        if not session:
            yield format_sse("error", {"message": "Sessão não encontrada", "phase": "error"})
            return

        if not session.roots:
            yield format_sse("error", {"message": "Orçamento vazio — adicione etapas primeiro.", "phase": "error"})
            return

        label = "edição" if mode == "edit" else "geração"
        yield format_sse(
            "status",
            {"message": f"Conectado — iniciando {label} da especificação técnica…", "phase": "connected"},
        )

        try:
            if mode == "edit":
                current = TechSpecDocument.from_dict(session.tech_spec) or TechSpecDocument()
                if not prompt.strip():
                    yield format_sse(
                        "error",
                        {"message": "Descreva a alteração desejada no prompt.", "phase": "error"},
                    )
                    return
                event_iter = edit_tech_spec_stream(
                    current,
                    prompt,
                    budget_context=build_budget_context(session),
                    use_llm=use_llm,
                )
            else:
                event_iter = compose_tech_spec_stream(session, prompt, use_llm=use_llm)

            for event_type, data in event_iter:
                if event_type == "done":
                    doc = TechSpecDocument.from_dict(data.get("tech_spec"))
                    if doc:
                        session.tech_spec = doc.to_dict()
                        session.updated_at = doc.updated_at
                    payload = dict(data)
                    payload["session"] = session.to_dict()
                    yield format_sse("done", payload)
                else:
                    yield format_sse(event_type, data)
        except Exception as exc:
            yield format_sse("error", {"message": str(exc), "phase": "error"})
