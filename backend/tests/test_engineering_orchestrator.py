"""Testes do orquestrador inteligente engenharia vs orçamento."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.orchestrator.domain_classifier import KnowledgeDomain, classify_domain
from core.orchestrator.engineering_orchestrator import (
    filter_disciplines_by_domain,
    orchestrate,
    prepare_agent_execution,
)
from core.orchestrator.knowledge_router import (
    apply_knowledge_priority_rerank,
    filter_hits_by_route,
    resolve_knowledge_route,
)
from memory.models import DocumentChunk


def test_classify_engineering_query():
    c = classify_domain("dimensionar viga NBR 6118", discipline_hint="ESTRUTURAL")
    assert c.primary_domain == KnowledgeDomain.ENGINEERING
    assert c.is_engineering_query
    assert not c.is_cost_query


def test_classify_cost_query():
    c = classify_domain("custo unitário sinapi concreto m³")
    assert c.primary_domain == KnowledgeDomain.COST
    assert c.agent_slug == "orcamento"
    assert c.is_cost_query


def test_engineering_route_blocks_sinapi():
    c = classify_domain("viga concreto", discipline_hint="ESTRUTURAL")
    route = resolve_knowledge_route(c)
    assert route.base_keys == ("nbr",)
    assert "sinapi" in route.blocked_content_types
    assert route.rerank_profile == "engineering"


def test_cost_route_blocks_nbr():
    c = classify_domain("planilha sinapi", discipline_hint="ORÇAMENTO")
    route = resolve_knowledge_route(c)
    assert "sinapi" in route.base_keys
    assert "nbrs" in route.blocked_content_types
    assert route.rerank_profile == "cost"


def test_filter_disciplines_removes_orcamento_from_structural():
    result = filter_disciplines_by_domain(
        "dimensionar viga de concreto",
        ["ESTRUTURAL", "ORÇAMENTO", "INCÊNDIO"],
    )
    assert "ORÇAMENTO" not in result
    assert "ESTRUTURAL" in result


def test_filter_disciplines_cost_only():
    result = filter_disciplines_by_domain(
        "composição sinapi alvenaria",
        ["ESTRUTURAL", "ORÇAMENTO"],
    )
    assert result == ["ORÇAMENTO"]


def test_orchestrate_plan():
    plan = orchestrate("custo sinapi laje", discipline_hint="ORÇAMENTO")
    assert plan.agent_slug == "orcamento"
    assert plan.knowledge_route["knowledge_type"] == "cost"
    assert "sinapi" in plan.knowledge_route["base_keys"]


def test_prepare_agent_blocks_cost_on_structural():
    route = prepare_agent_execution(
        {"discipline": "ESTRUTURAL", "input": "dimensionar viga"},
        "dimensionar viga NBR 6118",
    )
    assert route["_knowledge_type"] == "engineering"
    assert route["_orchestrator"]["agent_slug"] != "orcamento"


def test_rerank_cost_penalizes_nbr():
    c = classify_domain("sinapi concreto", discipline_hint="ORÇAMENTO")
    route = resolve_knowledge_route(c)
    hits = [
        (DocumentChunk(text="NBR 6118", metadata={"content_type": "nbrs", "nbr_code": "6118"}), 0.9),
        (DocumentChunk(text="SINAPI concreto", metadata={"content_type": "sinapi"}), 0.7),
    ]
    filtered = filter_hits_by_route(hits, route)
    assert len(filtered) == 1
    reranked = apply_knowledge_priority_rerank(filtered, route)
    assert "sinapi" in reranked[0][0].metadata.get("content_type", "")


def test_rerank_engineering_penalizes_sinapi():
    c = classify_domain("viga concreto", discipline_hint="ESTRUTURAL")
    route = resolve_knowledge_route(c)
    hits = [
        (DocumentChunk(text="SINAPI", metadata={"content_type": "sinapi"}), 0.95),
        (DocumentChunk(text="NBR 6118 armadura", metadata={"content_type": "nbrs", "nbr_code": "6118"}), 0.7),
    ]
    filtered = filter_hits_by_route(hits, route)
    assert len(filtered) == 1
    assert filtered[0][0].metadata["content_type"] == "nbrs"


if __name__ == "__main__":
    test_classify_engineering_query()
    test_classify_cost_query()
    test_engineering_route_blocks_sinapi()
    test_cost_route_blocks_nbr()
    test_filter_disciplines_removes_orcamento_from_structural()
    test_filter_disciplines_cost_only()
    test_orchestrate_plan()
    test_prepare_agent_blocks_cost_on_structural()
    test_rerank_cost_penalizes_nbr()
    test_rerank_engineering_penalizes_sinapi()
    print("OK — test_engineering_orchestrator")
