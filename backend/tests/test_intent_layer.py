"""Testes da Intent Layer v2."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.intent_layer import (
    analyze_intent,
    execute_intent,
    merge_segment_results,
    try_split_mixed,
)


def test_try_split_mixed():
    result = try_split_mixed("oi, preciso dimensionar viga de concreto")
    assert result is not None
    chat, tech = result
    assert "oi" in chat.lower()
    assert "dimensionar viga" in tech


def test_try_split_mixed_compound_greeting():
    result = try_split_mixed(
        "oi boa noite! preciso dimensionar uma viga de concreto com sessão 14x40 cm"
    )
    assert result is not None
    chat, tech = result
    assert "oi" in chat.lower()
    assert "boa noite" in chat.lower()
    assert "dimensionar" in tech
    assert "boa noite" not in tech.lower()


def test_try_split_mixed_no_technical():
    assert try_split_mixed("oi, tudo bem?") is None


def test_analyze_intent_chat_only():
    analysis = analyze_intent("bom dia")
    assert analysis.mode == "chat_only"
    assert len(analysis.execution_plan) == 1
    assert analysis.execution_plan[0].domain == "chat"


def test_analyze_intent_engineering_only():
    analysis = analyze_intent("dimensionar viga de concreto armado")
    assert analysis.mode == "engineering_only"
    assert analysis.technical_discipline == "ESTRUTURAL"


def test_analyze_intent_mixed():
    analysis = analyze_intent("oi, preciso dimensionar viga de concreto")
    assert analysis.mode == "mixed"
    assert analysis.technical_discipline == "ESTRUTURAL"
    assert len(analysis.execution_plan) == 2
    assert analysis.execution_plan[0].domain == "chat"
    assert analysis.execution_plan[1].domain == "engineering"


def test_analyze_intent_capabilities_chat_only():
    analysis = analyze_intent("o que vc sabe fazer de melhor?")
    assert analysis.mode == "chat_only"
    assert analysis.chat_intent is not None
    assert analysis.chat_intent.name == "capabilities"


def test_merge_segment_results_mixed():
    merged = merge_segment_results(
        [
            {"discipline": "CHAT", "result": "Olá!"},
            {"discipline": "ESTRUTURAL", "result": "Análise da viga."},
        ],
        "mixed",
    )
    assert "ChatAgent" in merged
    assert "ESTRUTURAL" in merged
    assert "combinada" in merged.lower()


def test_execute_intent_mixed():
    analysis = analyze_intent("oi, preciso dimensionar viga de concreto")

    with patch.object(
        __import__("models.ollama_client", fromlist=["OllamaClient"]).OllamaClient,
        "generate",
        return_value=("Análise técnica da viga.", "qwen3:14b"),
    ):
        output = execute_intent(analysis, use_rag=False, persist=False)

    assert output["intent"]["mode"] == "mixed"
    assert len(output["segments"]) == 2
    assert output["segments"][0]["discipline"] == "CHAT"
    assert output["segments"][1]["discipline"] == "ESTRUTURAL"
    assert "ChatAgent" in output["result"]
    assert output["route"]["mode"] == "mixed"


def test_dispatch_survives_llm_timeout():
    from core.dispatcher import dispatch

    with patch.object(
        __import__("models.ollama_client", fromlist=["OllamaClient"]).OllamaClient,
        "generate",
        side_effect=RuntimeError("Read timed out"),
    ):
        response = dispatch(
            {
                "input": "dimensionar viga de concreto",
                "discipline": "ESTRUTURAL",
                "agent": "estruturas_agent",
                "_use_rag": False,
            },
            persist=False,
        )

    assert response.get("error") is True
    assert "Ollama" in response["result"]
    assert response["discipline"] == "ESTRUTURAL"


if __name__ == "__main__":
    test_try_split_mixed()
    test_try_split_mixed_compound_greeting()
    test_try_split_mixed_no_technical()
    test_analyze_intent_chat_only()
    test_analyze_intent_engineering_only()
    test_analyze_intent_mixed()
    test_analyze_intent_capabilities_chat_only()
    test_merge_segment_results_mixed()
    test_execute_intent_mixed()
    test_dispatch_survives_llm_timeout()
    print("OK: testes Intent Layer v2 passaram")
