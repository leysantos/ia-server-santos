"""Testes Copilot v1 — intent, plan, execução, síntese e avaliação."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.copilot.intent_analyzer import analyze_intent
from core.copilot.task_planner import build_plan
from core.copilot.execution_graph import ExecutionGraph
from core.copilot.response_synthesizer import synthesize_response
from core.copilot.quality_evaluator import evaluate_quality
from core.copilot.copilot_engine import run_copilot


def test_intent_structural():
    result = analyze_intent("dimensionar viga de concreto armado")
    assert result.intent == "structural"
    assert "ESTRUTURAL" in result.disciplines_hint


def test_intent_multi_discipline_building():
    result = analyze_intent("dimensionar prédio residencial")
    assert result.intent == "multi_discipline"
    assert "ESTRUTURAL" in result.disciplines_hint
    assert "ORÇAMENTO" in result.disciplines_hint


def test_intent_cost():
    result = analyze_intent("planilha orçamentária sinapi")
    assert result.intent == "cost"
    assert result.disciplines_hint == ["ORÇAMENTO"]


def test_task_planner_generates_steps():
    intent = analyze_intent("dimensionar prédio residencial")
    plan = build_plan("dimensionar prédio residencial", intent)

    assert plan.intent == "multi_discipline"
    assert len(plan.steps) >= 3
    assert plan.steps[0].order == 1
    assert plan.steps[0].agent.endswith("_agent")
    assert plan.to_dict()[0]["step_id"] == "step_1"


def test_execution_graph_with_mock_dispatch():
    intent = analyze_intent("dimensionar viga de concreto")
    plan = build_plan("dimensionar viga de concreto", intent)

    mock_response = {
        "agent": "estruturas_agent",
        "discipline": "ESTRUTURAL",
        "input": "dimensionar viga de concreto",
        "result": "Análise estrutural com NBR 6118 aplicada ao dimensionamento.",
        "extra": {"intelligent": True},
    }

    with patch("core.copilot.execution_graph.dispatch", return_value=mock_response):
        executor = ExecutionGraph(use_rag=False, persist=False)
        execution = executor.execute_plan(plan, "dimensionar viga de concreto")

    assert execution.completed_count == 1
    assert "ESTRUTURAL" in executor.context_graph.nodes


def test_synthesizer_and_evaluator():
    intent = analyze_intent("dimensionar viga")
    plan = build_plan("dimensionar viga", intent)

    mock_response = {
        "agent": "estruturas_agent",
        "discipline": "ESTRUTURAL",
        "result": "Análise NBR 6118 " + ("x" * 100),
    }

    with patch("core.copilot.execution_graph.dispatch", return_value=mock_response):
        execution = ExecutionGraph(use_rag=False).execute_plan(plan, "dimensionar viga")

    synthesis = synthesize_response(plan, execution)
    evaluation = evaluate_quality(synthesis, execution, plan)

    assert "ESTRUTURAL" in synthesis["by_discipline"]
    assert "final_report" in synthesis
    assert 0.0 <= evaluation["score"] <= 1.0
    assert evaluation["grade"] in ("excelente", "bom", "aceitável", "insuficiente", "crítico")


def test_copilot_engine_pipeline():
    mock_response = {
        "agent": "estruturas_agent",
        "discipline": "ESTRUTURAL",
        "result": "Dimensionamento conforme NBR 6118 " + ("detalhe " * 20),
    }

    with patch("core.copilot.execution_graph.dispatch", return_value=mock_response):
        output = run_copilot("dimensionar prédio residencial", use_rag=False, persist=False)

    assert output["intent"] == "multi_discipline"
    assert len(output["plan"]) >= 3
    assert "result" in output
    assert "evaluation" in output
    assert 0.0 <= output["evaluation"]["score"] <= 1.0
    assert output["context_graph"]["nodes"]


if __name__ == "__main__":
    test_intent_structural()
    test_intent_multi_discipline_building()
    test_intent_cost()
    test_task_planner_generates_steps()
    test_execution_graph_with_mock_dispatch()
    test_synthesizer_and_evaluator()
    test_copilot_engine_pipeline()
    print("OK: testes Copilot v1 passaram")
