"""Testes do router — classificação por regras (sem LLM)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.router import route, route_by_rules, normalize_discipline


def test_estrutural_viga_concreto():
    text = "dimensionar viga de concreto armado"
    assert route_by_rules(text) == "ESTRUTURAL"
    result = route(text)
    assert result["discipline"] == "ESTRUTURAL"
    assert result["agent"] == "estruturas_agent"


def test_hidrossanitario():
    text = "projeto de tubulação de esgoto sanitário"
    assert route_by_rules(text) == "HIDROSSANITÁRIO"
    assert route(text)["discipline"] == "HIDROSSANITÁRIO"


def test_eletrica():
    text = "calcular carga elétrica do circuito de iluminação"
    assert route_by_rules(text) == "ELÉTRICA"


def test_geotecnia():
    text = "sondagem SPT para fundação"
    assert route_by_rules(text) == "GEOTECNIA"


def test_drenagem():
    text = "dimensionar drenagem de águas pluviais"
    assert route_by_rules(text) == "DRENAGEM"


def test_incendio():
    text = "projeto de sistema sprinkler e combate a incêndio"
    assert route_by_rules(text) == "INCÊNDIO"


def test_normalize_discipline():
    assert normalize_discipline("estrutural") == "ESTRUTURAL"
    assert normalize_discipline("hidrossanitario") == "HIDROSSANITÁRIO"
    assert normalize_discipline("resposta: ESTRUTURAL\n") == "ESTRUTURAL"


def test_rules_priority_over_generic():
    # Estrutural deve vencer termos genéricos
    text = "dimensionar viga de concreto armado"
    result = route(text)
    assert result["discipline"] != "GERAL"


def test_chat_greeting_routes_to_chat_agent():
    for text in ("oi", "Olá!", "bom dia", "boa tarde", "tudo bem?"):
        result = route(text)
        assert result["discipline"] == "CHAT"
        assert result["agent"] == "chat_agent"


def test_chat_identity_questions():
    for text in (
        "oi quem é vc?",
        "quem é você?",
        "o que você faz?",
        "o que vc sabe fazer de melhor?",
        "quais são suas capacidades?",
        "como funciona?",
        "bom dia, quem é vc",
        "me ajuda?",
    ):
        result = route(text)
        assert result["discipline"] == "CHAT", f"falhou para: {text!r}"
        assert result["agent"] == "chat_agent"


def test_chat_agent_capabilities_response():
    from unittest.mock import patch

    from agents.chat import ChatAgent, TEMPLATE_CAPABILITIES
    from models.ollama_client import OllamaClient

    with patch.object(OllamaClient, "generate", side_effect=RuntimeError("offline")):
        agent = ChatAgent()
        response = agent.handle("o que vc sabe fazer de melhor?")

    assert response["discipline"] == "CHAT"
    assert "multidisciplinar" in response["result"]
    assert response["result"] == TEMPLATE_CAPABILITIES
    assert response["extra"]["response_source"] == "template"
    assert response["extra"]["domain"] == "chat"


def test_chat_agent_uses_fast_llm():
    from unittest.mock import patch

    from agents.chat import ChatAgent
    from models.ollama_client import OllamaClient

    with patch.object(
        OllamaClient,
        "generate",
        return_value=("Posso ajudar com estruturas e hidráulica.", "qwen3:8b"),
    ) as mock_gen:
        agent = ChatAgent()
        response = agent.handle(
            "preciso de um resumo técnico sobre impermeabilização de lajes em edifícios"
        )

    mock_gen.assert_called_once()
    assert response["extra"]["response_source"] == "llm"
    assert response["extra"]["model"] == "qwen3:8b"
    assert response["extra"]["domain"] == "chat"


def test_chat_not_triggered_with_technical_content():
    result = route("oi, preciso dimensionar viga de concreto")
    assert result["discipline"] != "CHAT"
    assert result["discipline"] == "ESTRUTURAL"


def test_chat_agent_handle():
    from agents.chat import ChatAgent, TEMPLATE_GREETING

    agent = ChatAgent(use_llm=False)
    response = agent.handle("olá")

    assert response["agent"] == "chat_agent"
    assert response["discipline"] == "CHAT"
    assert response["result"] == TEMPLATE_GREETING
    assert response["extra"]["domain"] == "chat"
    assert response["extra"]["mode"] == "conversational"
    assert "normas_base" not in response.get("extra", {})


def test_dispatcher_has_chat_agent():
    from core.dispatcher import AGENTS

    assert "CHAT" in AGENTS
    assert AGENTS["CHAT"].name == "chat_agent"


if __name__ == "__main__":
    test_estrutural_viga_concreto()
    test_hidrossanitario()
    test_eletrica()
    test_geotecnia()
    test_drenagem()
    test_incendio()
    test_normalize_discipline()
    test_rules_priority_over_generic()
    test_chat_greeting_routes_to_chat_agent()
    test_chat_identity_questions()
    test_chat_agent_capabilities_response()
    test_chat_agent_uses_fast_llm()
    test_chat_not_triggered_with_technical_content()
    test_chat_agent_handle()
    test_dispatcher_has_chat_agent()
    print("OK: testes router passaram")
