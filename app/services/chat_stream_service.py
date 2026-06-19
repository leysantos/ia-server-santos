from typing import Generator, Optional

from config.settings import USE_INTENT_LAYER
from core.database.service import save_conversation
from core.intent_layer import analyze_intent, execute_intent, iter_intent_events
from core.stream_events import format_sse


class ChatStreamService:
    """Streaming SSE do chat com preview em tempo real."""

    def stream(
        self,
        text: str,
        use_rag: bool = True,
        persist: bool = True,
    ) -> Generator[str, None, None]:
        conversation_id = None
        if persist:
            conversation = save_conversation(input_text=text, mode="single")
            if conversation:
                conversation_id = conversation.get("id")

        if not USE_INTENT_LAYER:
            yield format_sse(
                "status",
                {"message": "Intent Layer desativada — use POST /chat", "phase": "error"},
            )
            yield format_sse("error", {"message": "Streaming requer USE_INTENT_LAYER=true"})
            return

        for event_type, data in iter_intent_events(
            text,
            use_rag=use_rag,
            persist=persist,
            conversation_id=conversation_id,
        ):
            yield format_sse(event_type, data)
