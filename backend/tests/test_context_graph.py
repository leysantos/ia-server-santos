"""Testes do ContextGraph (Orchestrator V2)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.context_graph import ContextGraph


def test_add_result_and_get():
    graph = ContextGraph()
    entry = graph.add_result(
        "ESTRUTURAL",
        {"result": "Vigas dimensionadas", "normas": ["NBR 6118"]},
    )

    assert entry["version"] == 1
    assert graph.get("ESTRUTURAL")["data"]["result"] == "Vigas dimensionadas"
    assert graph.get_data("ESTRUTURAL")["normas"] == ["NBR 6118"]


def test_incremental_history():
    graph = ContextGraph()
    graph.add_result("ESTRUTURAL", {"result": "v1"})
    graph.add_result("ESTRUTURAL", {"result": "v2"})

    history = graph.get_history("ESTRUTURAL")
    assert len(history) == 2
    assert history[0]["version"] == 1
    assert history[1]["version"] == 2
    assert graph.get("ESTRUTURAL")["version"] == 2


def test_dependencies_and_cross_query():
    graph = ContextGraph()
    graph.add_result("ESTRUTURAL", {"result": "Estrutura OK"}, depends_on=["GEOTECNIA"])
    graph.add_result("GEOTECNIA", {"result": "Solo classe A"})

    related = graph.get_related("ESTRUTURAL")
    assert "ESTRUTURAL" in related
    assert "GEOTECNIA" in related

    queried = graph.query(["ESTRUTURAL", "HIDROSSANITÁRIO"])
    assert "ESTRUTURAL" in queried
    assert "HIDROSSANITÁRIO" not in queried


def test_merge_contexts():
    graph = ContextGraph()
    graph.add_result("ESTRUTURAL", {"premissas": {"carga": 10}, "tags": ["concreto"]})
    graph.add_result("ORÇAMENTO", {"premissas": {"prazo": 30}, "tags": ["sinapi"]})

    merged = graph.merge_contexts(["ESTRUTURAL", "ORÇAMENTO"])
    assert merged["merged"]["premissas"]["carga"] == 10
    assert merged["merged"]["premissas"]["prazo"] == 30
    assert len(merged["merged"]["tags"]) == 2


def test_merge_contexts_with_other_graph():
    a = ContextGraph()
    a.add_result("ESTRUTURAL", {"result": "A"})

    b = ContextGraph()
    b.add_result("ESTRUTURAL", {"extra": "B"})

    merged = a.merge_contexts(other=b)
    assert merged["merged"]["result"] == "A"
    assert merged["merged"]["extra"] == "B"


def test_build_global_context():
    graph = ContextGraph()
    graph.add_result("ESTRUTURAL", {"result": "Análise estrutural"})
    graph.add_result("ORÇAMENTO", {"summary": "Custo estimado"})

    ctx = graph.build_global_context()
    assert "ESTRUTURAL" in ctx
    assert "ORÇAMENTO" in ctx
    assert "Análise estrutural" in ctx


def test_json_roundtrip():
    graph = ContextGraph()
    graph.add_result("INCÊNDIO", {"result": "Sprinklers OK"}, depends_on=["HIDROSSANITÁRIO"])
    graph.add_dependency("ELÉTRICA", ["ARQUITETURA"])

    raw = graph.to_json()
    restored = ContextGraph.from_json(raw)

    assert restored.nodes == graph.nodes
    assert restored.dependencies == graph.dependencies
    assert len(restored.history) == 1
    assert json.loads(raw)["nodes"]["INCÊNDIO"]["data"]["result"] == "Sprinklers OK"


if __name__ == "__main__":
    test_add_result_and_get()
    test_incremental_history()
    test_dependencies_and_cross_query()
    test_merge_contexts()
    test_merge_contexts_with_other_graph()
    test_build_global_context()
    test_json_roundtrip()
    print("OK: testes ContextGraph passaram")
