"""Testes — avaliação da plataforma via project_state.md."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.chat import ChatAgent, detect_intent, should_answer_with_template
from core.intent_layer import analyze_intent
from core.platform_knowledge import (
    build_platform_context,
    format_platform_evaluation_fallback,
    is_platform_evaluation_query,
)


USER_QUERY = (
    "faça uma avaliação do IA Server Santos, analise a estrutura do sistema "
    "e mostre os pontos fortes e fracos"
)


def test_is_platform_evaluation_query():
    assert is_platform_evaluation_query(USER_QUERY)
    assert is_platform_evaluation_query("avaliar a arquitetura da plataforma ia server santos")
    assert is_platform_evaluation_query("mostre os pontos forte e fraco do ia server santos")
    assert not is_platform_evaluation_query("dimensionar viga de concreto armado")
    assert not is_platform_evaluation_query("bom dia")


def test_platform_follow_up_in_thread():
    from core.platform_knowledge import is_platform_follow_up

    thread = (
        "HISTÓRICO DA CONVERSA\n"
        "User: faça uma avaliação do IA Server Santos\n"
        "Assistant: ## Pontos fortes\n\nNOVA MENSAGEM DO USUÁRIO:\n"
        "mostre só os pontos fracos"
    )
    assert is_platform_follow_up(thread, "mostre só os pontos fracos")


def test_detect_intent_platform_evaluation():
    intent = detect_intent(USER_QUERY)
    assert intent.name == "platform_evaluation"
    assert intent.confidence >= 0.95


def test_should_not_use_template_for_platform_evaluation():
    intent = detect_intent(USER_QUERY)
    assert should_answer_with_template(USER_QUERY, intent) is False


def test_analyze_intent_routes_follow_up_with_typo():
    composed = (
        "HISTÓRICO DA CONVERSA (referência — responda à NOVA MENSAGEM abaixo):\n"
        "User: faça uma avaliação do IA Server Santos\n"
        "Assistant: ## Avaliação Técnica\n\n"
        "NOVA MENSAGEM DO USUÁRIO:\n"
        "mostre os pontos forte e fraco do ia server santos"
    )
    analysis = analyze_intent(composed)
    assert analysis.mode == "chat_only"
    assert analysis.chat_intent is not None
    assert analysis.chat_intent.name == "platform_evaluation"


def test_analyze_intent_routes_to_chat_not_engineering():
    analysis = analyze_intent(USER_QUERY)
    assert analysis.mode == "chat_only"
    assert analysis.execution_plan[0].domain == "chat"
    assert analysis.chat_intent.name == "platform_evaluation"


def test_post_format_platform_not_truncated_at_1200():
    from agents.chat import ChatIntent
    from core.intent_layer import post_format_chat_stream
    from core.platform_knowledge import PLATFORM_EVAL_RESPONSE_MAX_CHARS

    long_text = "## Pontos fortes\n\n" + ("x" * 5000)
    intent = ChatIntent("platform_evaluation", 0.98)
    out = post_format_chat_stream(long_text, intent=intent)
    assert len(out) > 4500
    assert len(out) <= PLATFORM_EVAL_RESPONSE_MAX_CHARS


def test_build_platform_context_has_sections():
    ctx = build_platform_context()
    assert "HANDOFF" in ctx or "Monorepo" in ctx or "FastAPI" in ctx
    assert len(ctx) > 200


def test_fallback_includes_strengths_and_weaknesses():
    text = format_platform_evaluation_fallback()
    lower = text.lower()
    assert "pontos fortes" in lower
    assert "pontos fracos" in lower
    assert "estrutura" in lower
    assert "não se preocupe" not in lower


def test_chat_agent_platform_fallback_offline():
    agent = ChatAgent(use_llm=False)
    response = agent.handle(USER_QUERY)
    result = response.get("result") or ""
    assert "Pontos fortes" in result or "pontos fortes" in result.lower()
    assert response["extra"]["intent"] == "platform_evaluation"
    assert response["extra"].get("platform_knowledge") is True


def test_stream_step_chat_agent_platform_no_intent_crash():
    """Regressão: intent deve existir antes de post_format_chat_stream."""
    from agents.chat import ChatAgent
    from core.intent_layer import ExecutionStep, _stream_step_events

    agent = ChatAgent(use_llm=True)

    def fake_iter(text, *, llm_model=None):
        yield "## Estrutura\n\n"
        yield "Texto parcial da avaliação."

    agent.iter_tokens = fake_iter  # type: ignore[method-assign]
    agent._last_model = "gemma4:latest"

    step = ExecutionStep(
        step=1,
        domain="chat",
        discipline="CHAT",
        agent="chat_agent",
        input="faça uma avaliação do IA Server Santos com pontos fortes e fracos",
    )

    from core.dispatcher import AGENTS

    original = AGENTS.get("CHAT")
    AGENTS["CHAT"] = agent
    try:
        events = list(
            _stream_step_events(step, False, False, None, llm_model="gemma4:latest")
        )
    finally:
        if original is not None:
            AGENTS["CHAT"] = original
        else:
            AGENTS.pop("CHAT", None)
    types = [e[0] for e in events]
    assert "segment_done" in types
    assert not any(
        "Ollama" in str(e[1].get("result", ""))
        for e in events
        if e[0] == "segment_done"
    )
    done = next(e[1] for e in events if e[0] == "segment_done")
    assert "Estrutura" in (done.get("result") or "")


def test_platform_stream_recovery_completes_weaknesses():
    from core.platform_knowledge import platform_evaluation_stream_recovery

    partial = "## Estrutura do sistema\n\nMonorepo.\n\n## Pontos fortes\n\n- RAG\n"
    recovery = platform_evaluation_stream_recovery(partial)
    assert "Pontos fracos" in recovery
    assert "Resumo" in recovery
    assert "control plane" in recovery.lower()


def test_chat_agent_platform_stream_with_mock_llm():
    agent = ChatAgent(use_llm=True)

    def fake_stream(prompt, model=None, fallback_models=None, options=None):
        assert "CONTEXTO OFICIAL" in prompt
        assert "Pontos fracos" in prompt or "pontos fracos" in prompt.lower()
        yield "## Estrutura", model or "gemma4:latest"
        yield " ok", model or "gemma4:latest"

    with patch.object(agent, "_platform_llm_config", return_value=("gemma4:latest", [], 300, {})), patch(
        "agents.chat.OllamaClient"
    ) as mock_cls:
        mock_cls.return_value.generate_stream = fake_stream
        tokens = list(agent.iter_tokens(USER_QUERY, llm_model="gemma4:latest"))
    assert "".join(tokens).startswith("## Estrutura")
    assert agent._last_model == "gemma4:latest"
