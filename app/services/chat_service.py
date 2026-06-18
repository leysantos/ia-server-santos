from typing import Optional

from core.database.service import save_conversation
from core.dispatcher import dispatch
from core.router import route
from memory.rag_engine import get_rag_engine


class ChatService:
    """Orquestra router → RAG v2 → dispatcher para chat single-domain."""

    def process(
        self,
        text: str,
        use_rag: bool = True,
        persist: bool = True,
    ) -> dict:
        conversation_id = None
        if persist:
            conversation = save_conversation(input_text=text, mode="single")
            if conversation:
                conversation_id = conversation.get("id")

        route_result = route(text)

        if use_rag:
            engine = get_rag_engine()
            route_result = engine.enrich_route_result(route_result)

        if conversation_id:
            route_result["_conversation_id"] = conversation_id

        agent_response = dispatch(route_result, persist=persist)

        output = {
            **agent_response,
            "input": text,
            "conversation_id": conversation_id,
            "route": {
                "discipline": route_result.get("discipline"),
                "agent": route_result.get("agent"),
            },
        }
        return output
