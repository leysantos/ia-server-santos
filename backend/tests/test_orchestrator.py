"""Testes do orquestrador multi-disciplinar."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.orchestrator import (
    decompose_problem,
    execute_agents,
    process_multi_domain_request,
    synthesize_results,
    _decompose_by_keywords,
)


def test_decompose_by_keywords_building():
    text = "projeto de prédio residencial com estrutura e hidráulica"
    disciplines = _decompose_by_keywords(text)

    assert "ESTRUTURAL" in disciplines
    assert "HIDROSSANITÁRIO" in disciplines
    assert "INCÊNDIO" in disciplines
    assert "ORÇAMENTO" in disciplines


def test_decompose_problem_fallback(monkeypatch=None):
    disciplines = _decompose_by_keywords(
        "dimensionar viga de concreto armado"
    )
    assert "ESTRUTURAL" in disciplines


def test_execute_agents():
    from unittest.mock import MagicMock, patch

    with patch.object(
        __import__("models.ollama_client", fromlist=["OllamaClient"]).OllamaClient,
        "generate",
        return_value=("Resposta técnica LLM", "qwen3:14b"),
    ):
        results = execute_agents(
            {
                "input": "dimensionar viga",
                "disciplines": ["ESTRUTURAL", "ORÇAMENTO"],
            },
            use_rag=False,
            persist=False,
        )

    assert len(results) == 2
    assert results[0]["discipline"] == "ESTRUTURAL"
    assert results[1]["discipline"] == "ORÇAMENTO"
    assert "result" in results[0]


def test_synthesize_results():
    results = [
        {
            "agent": "estruturas_agent",
            "discipline": "ESTRUTURAL",
            "input": "viga",
            "result": "Análise estrutural simulada",
            "extra": {"normas_base": ["NBR 6118"]},
        },
        {
            "agent": "orcamento_agent",
            "discipline": "ORÇAMENTO",
            "input": "viga",
            "result": "Análise de orçamento simulada",
            "extra": {"normas_base": ["SINAPI"]},
        },
    ]

    synthesis = synthesize_results(results)

    assert "ESTRUTURAL" in synthesis["technical_summary"]
    assert "ORÇAMENTO" in synthesis["technical_summary"]
    assert "NBR 6118" in synthesis["technical_summary"]
    assert "Conclusão geral" in synthesis["final_report"]
    assert len(synthesis["by_discipline"]) == 2


def test_synthesize_results_with_context():
    results = [
        {
            "agent": "estruturas_agent",
            "discipline": "ESTRUTURAL",
            "result": "OK",
        },
    ]
    synthesis = synthesize_results(results, context="Contexto compartilhado ESTRUTURAL")

    assert "CONTEXTO GLOBAL DO PROJETO" in synthesis["final_report"]
    assert "Contexto compartilhado ESTRUTURAL" in synthesis["final_report"]
    assert synthesis["global_context"] == "Contexto compartilhado ESTRUTURAL"


def test_process_multi_domain_request():
    from unittest.mock import patch

    with patch.object(
        __import__("models.ollama_client", fromlist=["OllamaClient"]).OllamaClient,
        "generate",
        return_value=("Relatório técnico LLM", "qwen3:14b"),
    ):
        output = process_multi_domain_request(
            "projeto de prédio residencial com estrutura e hidráulica",
            use_rag=False,
            persist=False,
        )

    assert output["input"]
    assert isinstance(output["disciplines"], list)
    assert len(output["disciplines"]) >= 2
    assert isinstance(output["results"], dict)
    assert output["final_report"]
    assert "synthesis" in output
    assert "context_graph" in output
    assert len(output["context_graph"]["nodes"]) >= 2
    assert "CONTEXTO GLOBAL DO PROJETO" in output["final_report"]
    assert output["synthesis"]["global_context"]


if __name__ == "__main__":
    test_decompose_by_keywords_building()
    test_decompose_problem_fallback()
    test_execute_agents()
    test_synthesize_results()
    test_synthesize_results_with_context()
    test_process_multi_domain_request()
    print("OK: testes do orchestrator passaram")
