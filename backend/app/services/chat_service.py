from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from config.settings import USE_INTENT_LAYER
from core.conversation_context import build_assistant_meta, compose_thread_input
from core.database.conversation_access import conversation_user_id
from core.database.models import User
from core.project_rag import resolve_project_id
from core.database.service import append_conversation_messages, ensure_conversation
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
        conversation_id: Optional[str] = None,
        project_id: Optional[str] = None,
        user: Optional[User] = None,
    ) -> dict:
        user_id = conversation_user_id(user)
        active_conversation_id = conversation_id
        if persist:
            conversation = ensure_conversation(
                text=text,
                mode="single",
                conversation_id=conversation_id,
                project_id=project_id,
                user_id=user_id,
            )
            if conversation_id and not conversation:
                raise HTTPException(status_code=404, detail="Conversa não encontrada")
            if conversation:
                active_conversation_id = conversation.get("id")

        active_project_id = resolve_project_id(active_conversation_id, project_id)
        agent_input = compose_thread_input(text, active_conversation_id, user_id=user_id)

        if USE_INTENT_LAYER:
            analysis = analyze_intent(agent_input)
            output = execute_intent(
                analysis,
                use_rag=use_rag,
                persist=persist,
                conversation_id=active_conversation_id,
                project_id=active_project_id,
            )
            output["conversation_id"] = active_conversation_id
        else:
            output = self._process_legacy(
                agent_input,
                text,
                use_rag,
                persist,
                active_conversation_id,
                active_project_id,
            )

        if persist and active_conversation_id:
            result_text = output.get("result") or output.get("response") or ""
            append_conversation_messages(
                active_conversation_id,
                user_text=text,
                assistant_text=result_text,
                assistant_meta=build_assistant_meta(output),
                user_id=user_id,
            )

        return output

    def _process_legacy(
        self,
        agent_input: str,
        original_text: str,
        use_rag: bool,
        persist: bool,
        conversation_id: Optional[str],
        project_id: Optional[str] = None,
    ) -> dict:
        route_result = route(agent_input)

        if route_result.get("discipline") == "CHAT":
            route_result["_use_rag"] = False
        elif use_rag:
            engine = get_rag_engine()
            if project_id:
                route_result["_project_id"] = project_id
            route_result = engine.enrich_route_result(route_result)
        else:
            route_result["_use_rag"] = False

        if conversation_id:
            route_result["_conversation_id"] = conversation_id

        agent_response = dispatch(route_result, persist=persist)

        return {
            **agent_response,
            "input": original_text,
            "conversation_id": conversation_id,
            "route": {
                "discipline": route_result.get("discipline"),
                "agent": route_result.get("agent"),
            },
        }
