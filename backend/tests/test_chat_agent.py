"""Testes do ChatAgent — intent, pipeline e metadata."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.chat import (
    ChatAgent,
    TEMPLATE_CAPABILITIES,
    TEMPLATE_GREETING,
    build_chat_extra,
    detect_intent,
    post_format_response,
)
from models.ollama_client import OllamaClient


def test_detect_intent_greeting():
    intent = detect_intent("bom dia")
    assert intent.name == "greeting"
    assert intent.confidence == 1.0


def test_detect_intent_capabilities():
    intent = detect_intent("o que vc sabe fazer de melhor?")
    assert intent.name == "capabilities"
    assert intent.confidence >= 0.9


def test_detect_intent_identity():
    intent = detect_intent("quem é você?")
    assert intent.name == "identity"


def test_post_format_strips_think_blocks():
    think_open = "<" + "think" + ">"
    think_close = "</" + "think" + ">"
    raw = f"{think_open}reasoning{think_close}\n\nResposta limpa."
    assert post_format_response(raw) == "Resposta limpa."


def test_post_format_strips_unclosed_think():
    think_open = "<" + "think" + ">"
    think_close = "</" + "think" + ">"
    raw_open = f"{think_open}Raciocínio interrompido"
    assert post_format_response(raw_open) == ""
    raw_closed = f"{think_open}ok{think_close}\n\n## Pontos fracos\n\nLacunas reais."
    out = post_format_response(raw_closed)
    assert "Raciocínio" not in out
    assert "Pontos fracos" in out


def test_iter_visible_llm_tokens_filters_think():
    from agents.chat import iter_visible_llm_tokens

    think_open = "<" + "think" + ">"
    think_close = "</" + "think" + ">"

    def fake_stream():
        yield think_open, "deepseek-r1:14b"
        yield "reasoning...\n", "deepseek-r1:14b"
        yield think_close, "deepseek-r1:14b"
        yield "\n\n## Pontos fortes\n\n", "deepseek-r1:14b"
        yield "Item A", "deepseek-r1:14b"

    tokens = list(iter_visible_llm_tokens(fake_stream(), max_chars=8000))
    merged = "".join(tokens)
    assert "reasoning" not in merged.lower()
    assert "## Pontos fortes" in merged
    assert merged.endswith("Item A")


def test_build_chat_extra_schema():
    from agents.chat import ChatIntent

    extra = build_chat_extra(ChatIntent("capabilities", 0.95), "llm", "qwen3:8b")
    assert extra["domain"] == "chat"
    assert extra["mode"] == "conversational"
    assert extra["intent"] == "capabilities"
    assert extra["confidence"] == 0.95
    assert extra["response_source"] == "llm"
    assert extra["model"] == "qwen3:8b"
    assert extra["conversational"] is True


def test_chat_agent_greeting_instant_template():
    agent = ChatAgent(use_llm=False)
    response = agent.handle("oi")

    assert response["extra"]["intent"] == "greeting"
    assert response["extra"]["response_source"] == "template"
    assert response["result"] == TEMPLATE_GREETING


def test_chat_agent_llm_pipeline():
    with patch.object(
        OllamaClient,
        "generate",
        return_value=("Sou o ChatAgent do IA Server Santos.", "qwen3:8b"),
    ):
        agent = ChatAgent()
        response = agent.handle("o que vc sabe fazer de melhor?")

    assert response["extra"]["domain"] == "chat"
    assert response["extra"]["response_source"] == "llm"
    assert response["extra"]["model"] == "qwen3:8b"
    assert response["extra"]["intent"] == "capabilities"
    assert "ChatAgent" in response["result"]


def test_chat_agent_llm_fallback():
    with patch.object(OllamaClient, "generate", side_effect=RuntimeError("offline")):
        agent = ChatAgent()
        response = agent.handle("o que vc sabe fazer de melhor?")

    assert response["extra"]["response_source"] == "template_fallback"
    assert response["result"] == TEMPLATE_CAPABILITIES


if __name__ == "__main__":
    test_detect_intent_greeting()
    test_detect_intent_capabilities()
    test_detect_intent_identity()
    test_post_format_strips_think_blocks()
    test_build_chat_extra_schema()
    test_chat_agent_greeting_instant_template()
    test_chat_agent_llm_pipeline()
    test_chat_agent_llm_fallback()
    print("OK: testes ChatAgent passaram")
