from typing import Generator, Optional

from config.settings import USE_INTENT_LAYER
from core.conversation_context import build_assistant_meta, compose_thread_input
from core.database.conversation_access import conversation_user_id
from core.database.models import User
from core.project_rag import resolve_project_id
from core.database.service import append_conversation_messages, ensure_conversation
from core.intent_layer import iter_intent_events
from core.runtime.job_tracking import label_from_text, track_stream_job
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
        llm_model: Optional[str] = None,
        user: Optional[User] = None,
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
                llm_model=llm_model,
                user=user,
            )
        except Exception as exc:
            import logging

            logging.getLogger(__name__).exception("Chat stream interrompido")
            yield format_sse(
                "error",
                {"message": f"Erro no streaming: {exc}", "phase": "error"},
            )
            yield format_sse(
                "done",
                {
                    "result": f"Erro no streaming: {exc}",
                    "error": True,
                    "response": f"Erro no streaming: {exc}",
                },
            )

    def _stream_body(
        self,
        text: str,
        use_rag: bool,
        persist: bool,
        conversation_id: Optional[str],
        project_id: Optional[str],
        llm_model: Optional[str] = None,
        user: Optional[User] = None,
    ) -> Generator[str, None, None]:
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
                yield format_sse("error", {"message": "Conversa não encontrada", "phase": "error"})
                yield format_sse("done", {"error": True, "response": "Conversa não encontrada"})
                return
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

        agent_input = compose_thread_input(text, active_conversation_id, user_id=user_id)
        final_output: dict | None = None

        with track_stream_job(
            kind="chat",
            label=label_from_text(text),
            project_id=active_project_id,
            meta={"conversation_id": active_conversation_id},
        ) as runtime_job:
            from core.runtime.ollama_concurrency import resolve_chat_runtime

            chat_plan = resolve_chat_runtime()
            if chat_plan.status_message:
                runtime_job.update(
                    phase="gpu_wait" if chat_plan.parallel_mode == "gpu_wait" else "cpu_parallel",
                    message=chat_plan.status_message,
                )
                yield format_sse(
                    "status",
                    {
                        "message": chat_plan.status_message,
                        "phase": chat_plan.parallel_mode,
                        "chat_runtime": chat_plan.to_dict(),
                    },
                )

            from core.runtime.ollama_concurrency import is_heavy_llm_model

            selected_model = llm_model
            if is_heavy_llm_model(selected_model):
                yield format_sse(
                    "status",
                    {
                        "message": (
                            f"Carregando {selected_model} — modelos grandes podem levar "
                            "1–3 min até o primeiro token. Aguarde..."
                        ),
                        "phase": "model_load",
                        "llm_model": selected_model,
                    },
                )

            for event_type, data in iter_intent_events(
                agent_input,
                use_rag=use_rag,
                persist=persist,
                conversation_id=active_conversation_id,
                project_id=active_project_id,
                llm_model=llm_model,
            ):
                runtime_job.update_from_stream(event_type, data)
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
                user_id=user_id,
            )
