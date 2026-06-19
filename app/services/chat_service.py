from typing import Optional

from config.settings import USE_INTENT_LAYER
from core.database.service import save_conversation
from core.intent_layer import analyze_intent, execute_intent
from core.dispatcher import dispatch
from core.router import route
from memory.rag_engine import get_rag_engine


class ChatService:
    """Orquestra Intent Layer v2 → RAG v2 → dispatcher para chat single-domain."""

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

        if USE_INTENT_LAYER:
            analysis = analyze_intent(text)
            output = execute_intent(
                analysis,
                use_rag=use_rag,
                persist=persist,
                conversation_id=conversation_id,
            )
            output["conversation_id"] = conversation_id
            return output

        return self._process_legacy(text, use_rag, persist, conversation_id)

    def _process_legacy(
        self,
        text: str,
        use_rag: bool,
        persist: bool,
        conversation_id: Optional[str],
    ) -> dict:
        route_result = route(text)

        if route_result.get("discipline") == "CHAT":
            route_result["_use_rag"] = False
        elif use_rag:
            engine = get_rag_engine()
            route_result = engine.enrich_route_result(route_result)
        else:
            route_result["_use_rag"] = False

        if conversation_id:
            route_result["_conversation_id"] = conversation_id

        agent_response = dispatch(route_result, persist=persist)

        return {
            **agent_response,
            "input": text,
            "conversation_id": conversation_id,
            "route": {
                "discipline": route_result.get("discipline"),
                "agent": route_result.get("agent"),
            },
        }
