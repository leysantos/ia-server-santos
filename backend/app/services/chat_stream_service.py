from typing import Generator, Optional

from config.settings import USE_INTENT_LAYER
from core.conversation_context import build_assistant_meta, compose_thread_input
from core.project_rag import resolve_project_id
from core.database.service import append_conversation_messages, ensure_conversation
from core.intent_layer import iter_intent_events
from core.stream_events import format_sse


class ChatStreamService:
    """Streaming SSE do chat com preview em tempo real."""

    def stream(
        self,
        text: str,
        use_rag: bool = True,
        persist: bool = True,
        conversation_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Generator[str, None, None]:
        yield format_sse(
            "status",
            {"message": "Conectado — preparando resposta...", "phase": "connected"},
        )

        try:
            yield from self._stream_body(
                text=text,
                use_rag=use_rag,
                persist=persist,
                conversation_id=conversation_id,
                project_id=project_id,
            )
        except Exception as exc:
            yield format_sse(
                "error",
                {"message": f"Erro no streaming: {exc}", "phase": "error"},
            )

    def _stream_body(
        self,
        text: str,
        use_rag: bool,
        persist: bool,
        conversation_id: Optional[str],
        project_id: Optional[str],
    ) -> Generator[str, None, None]:
        active_conversation_id = conversation_id
        if persist:
            conversation = ensure_conversation(
                text=text,
                mode="single",
                conversation_id=conversation_id,
                project_id=project_id,
            )
            if conversation:
                active_conversation_id = conversation.get("id")

        active_project_id = resolve_project_id(active_conversation_id, project_id)

        if not USE_INTENT_LAYER:
            yield format_sse(
                "status",
                {"message": "Intent Layer desativada — use POST /chat", "phase": "error"},
            )
            yield format_sse("error", {"message": "Streaming requer USE_INTENT_LAYER=true"})
            return

        agent_input = compose_thread_input(text, active_conversation_id)
        final_output: dict | None = None

        for event_type, data in iter_intent_events(
            agent_input,
            use_rag=use_rag,
            persist=persist,
            conversation_id=active_conversation_id,
            project_id=active_project_id,
        ):
            if event_type == "done":
                final_output = data
                data = {**data, "conversation_id": active_conversation_id}
            yield format_sse(event_type, data)

        if persist and active_conversation_id and final_output:
            result_text = final_output.get("result") or final_output.get("response") or ""
            append_conversation_messages(
                active_conversation_id,
                user_text=text,
                assistant_text=result_text,
                assistant_meta=build_assistant_meta(final_output),
            )
