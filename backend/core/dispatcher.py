from config.settings import USE_INTELLIGENT_AGENTS
from agents.chat import ChatAgent
from core.agents.intelligent_factory import build_intelligent_agents
from core.agents.legacy_factory import build_legacy_agents
from core.agent_registry import get_agent_name

import logging

logger = logging.getLogger(__name__)


def _build_agents_registry() -> dict:
    if USE_INTELLIGENT_AGENTS:
        agents = build_intelligent_agents()
    else:
        agents = build_legacy_agents()

    agents["CHAT"] = ChatAgent()
    return agents


# Registry central — agentes inteligentes por padrão
AGENTS = _build_agents_registry()


def _agent_error_response(
    discipline: str | None,
    user_input: str,
    exc: Exception,
) -> dict:
    """Resposta estruturada quando agente/LLM falha — evita HTTP 500."""
    agent_name = get_agent_name(discipline) if discipline else "unknown_agent"
    logger.error(
        "dispatch_failed discipline=%s agent=%s error=%s",
        discipline,
        agent_name,
        exc,
    )
    return {
        "agent": agent_name,
        "discipline": discipline or "DESCONHECIDA",
        "input": user_input,
        "result": (
            "Não foi possível concluir a análise técnica neste momento.\n\n"
            "**Causa provável:** serviço de IA local (Ollama) indisponível, "
            "sobrecarregado ou tempo limite excedido.\n\n"
            "**O que fazer:**\n"
            "- Verifique se o Ollama está ativo (`ollama serve`)\n"
            "- Aguarde o modelo terminar outra inferência\n"
            "- Tente novamente com uma pergunta mais objetiva"
        ),
        "error": True,
        "extra": {
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:300],
        },
    }


def dispatch(route_result: dict, persist: bool = True):
    discipline = route_result.get("discipline")
    user_input = route_result.get("input")
    context = route_result.get("context")

    agent = AGENTS.get(discipline)

    if agent:
        handle_kwargs = {"context": context}
        if "_use_rag" in route_result:
            handle_kwargs["use_rag"] = route_result["_use_rag"]

        response = None
        if discipline == "ESTRUTURAL" and USE_INTELLIGENT_AGENTS:
            try:
                from core.structural_intelligence.dispatch_adapter import try_sie_dispatch

                response = try_sie_dispatch(
                    agent,
                    user_input,
                    context=handle_kwargs.get("context"),
                    use_rag=handle_kwargs.get("use_rag"),
                )
            except Exception as exc:
                logger.warning("SIE v1 indisponível, fluxo padrão ESTRUTURAL: %s", exc)
                response = None

        if response is None:
            try:
                response = agent.handle(user_input, **handle_kwargs)
            except TypeError:
                # Agentes legados não aceitam use_rag
                try:
                    response = agent.handle(user_input, context=context)
                except Exception as exc:
                    response = _agent_error_response(discipline, user_input, exc)
            except Exception as exc:
                response = _agent_error_response(discipline, user_input, exc)
    else:
        response = {
            "discipline": "GERAL",
            "response": "Nenhum agente especializado encontrado para esta solicitação."
        }

    if persist:
        from core.database.service import save_agent_run

        save_agent_run(route_result=route_result, response=response)

    try:
        from core.learning.feedback_service import record_agent_execution

        record_agent_execution(
            agent_name=response.get("agent") or route_result.get("agent", "unknown_agent"),
            discipline=response.get("discipline") or discipline,
            input_text=user_input or "",
            response_text=response.get("result") or response.get("response"),
            conversation_id=route_result.get("_conversation_id"),
        )
    except Exception:
        logger.debug("Learning Loop: capture ignorado no dispatcher", exc_info=True)

    try:
        from core.evolution.evolution_engine import emit_evolution_signal
        from core.evolution.signal_collector import collect_agent_signal

        signal = collect_agent_signal(route_result, response)
        emit_evolution_signal({**signal.to_dict(), "source": "agent", "module": "dispatcher"})
    except Exception:
        logger.debug("Evolution Loop: capture ignorado no dispatcher", exc_info=True)

    return response
