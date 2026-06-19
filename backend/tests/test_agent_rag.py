"""Testes RAG orientado por agente."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.knowledge.rag.agent_reranker import agent_rerank
from core.knowledge.rag.agent_router import route_query_to_agent
from core.knowledge.rag.agent_scopes import (
    filter_hits_by_agent_scope,
    get_agent_scope,
)
from memory.models import DocumentChunk


def test_route_estrutural_by_discipline():
    assert route_query_to_agent("dimensionar viga", discipline_hint="ESTRUTURAL") == "estruturas"


def test_route_orcamento_by_discipline():
    assert route_query_to_agent("custo sinapi", discipline_hint="ORÇAMENTO") == "orcamento"


def test_route_orcamento_by_query():
    assert route_query_to_agent("composição sinapi concreto") == "orcamento"


def test_route_chat_conversational():
    assert route_query_to_agent("olá, tudo bem?") == "chat"


def test_route_eletrica_nbr():
    assert route_query_to_agent("dimensionamento NBR 5410 circuito") == "eletrica"


def test_orcamento_blocks_nbr_chunks():
    scope = get_agent_scope("orcamento")
    hits = [
        (DocumentChunk(text="NBR 6118 concreto", metadata={"content_type": "nbrs"}), 0.9),
        (DocumentChunk(text="SINAPI concreto", metadata={"content_type": "sinapi"}), 0.8),
    ]
    filtered = filter_hits_by_agent_scope(hits, scope)
    assert len(filtered) == 1
    assert filtered[0][0].metadata["content_type"] == "sinapi"


def test_estruturas_blocks_sinapi():
    scope = get_agent_scope("estruturas")
    hits = [
        (DocumentChunk(text="SINAPI", metadata={"content_type": "sinapi"}), 0.95),
        (DocumentChunk(text="NBR 6118", metadata={"content_type": "nbrs"}, discipline="ESTRUTURAL"), 0.7),
    ]
    filtered = filter_hits_by_agent_scope(hits, scope)
    assert len(filtered) == 1
    assert "6118" in filtered[0][0].text or filtered[0][0].metadata["content_type"] == "nbrs"


def test_agent_rerank_prefers_aligned_discipline():
    scope = get_agent_scope("estruturas")
    hits = [
        (DocumentChunk(text="concreto armado", discipline="ELÉTRICA", metadata={"content_type": "nbrs"}), 0.9),
        (DocumentChunk(text="viga concreto", discipline="ESTRUTURAL", metadata={"content_type": "nbrs", "nbr_code": "6118"}), 0.75),
    ]
    reranked = agent_rerank(hits, "dimensionar viga NBR 6118", scope)
    assert reranked[0][0].discipline == "ESTRUTURAL"


def test_orcamento_scope_base_keys():
    scope = get_agent_scope("orcamento")
    assert scope.base_keys == ("sinapi", "tcpo")
    assert "sinapi" in scope.allowed_content_types
    assert "nbrs" in scope.blocked_content_types


def test_all_engineering_agents_have_scope():
    from core.knowledge.rag.agent_scopes import AGENT_MODULES

    for agent in AGENT_MODULES:
        scope = get_agent_scope(agent)
        assert scope.agent_slug == agent


def test_chat_agent_no_rag():
    scope = get_agent_scope("chat")
    assert scope.uses_technical_rag is False
    assert scope.base_keys == ()


def test_parse_edition_year_from_filename():
    from memory.nbr_edition import parse_edition_year

    assert parse_edition_year("NBR 6118 - 2014 - Projeto de Estruturas.pdf", "6118") == 2014
    assert parse_edition_year("NBR 6118 - 2001 - Projeto De Estruturas.pdf", "6118") == 2001
    assert parse_edition_year("NBR 6118:2014 dimensionamento vigas", "6118") == 2014


def test_edition_rerank_prefers_2014_when_query_specifies():
    from memory.nbr_edition import apply_edition_rerank

    hits = [
        (
            DocumentChunk(
                text="viga 2001",
                source="NBR 6118 - 2001 - Projeto.pdf",
                metadata={"nbr_code": "6118", "filename": "NBR 6118 - 2001 - Projeto.pdf"},
            ),
            0.95,
        ),
        (
            DocumentChunk(
                text="viga 2014",
                source="NBR 6118 - 2014 - Projeto.pdf",
                metadata={"nbr_code": "6118", "filename": "NBR 6118 - 2014 - Projeto.pdf"},
            ),
            0.90,
        ),
    ]
    reranked = apply_edition_rerank(hits, "requisitos NBR 6118:2014 vigas")
    assert "2014" in reranked[0][0].source


def test_edition_rerank_prefers_newer_without_year_in_query():
    from memory.nbr_edition import apply_edition_rerank

    hits = [
        (
            DocumentChunk(
                text="viga 2001",
                source="NBR 6118 - 2001 - Projeto.pdf",
                metadata={"nbr_code": "6118", "filename": "NBR 6118 - 2001 - Projeto.pdf"},
            ),
            0.92,
        ),
        (
            DocumentChunk(
                text="viga 2014",
                source="NBR 6118 - 2014 - Projeto.pdf",
                metadata={"nbr_code": "6118", "filename": "NBR 6118 - 2014 - Projeto.pdf"},
            ),
            0.88,
        ),
    ]
    reranked = apply_edition_rerank(hits, "dimensionamento viga NBR 6118")
    assert "2014" in reranked[0][0].source


if __name__ == "__main__":
    test_route_estrutural_by_discipline()
    test_route_orcamento_by_discipline()
    test_route_orcamento_by_query()
    test_route_chat_conversational()
    test_route_eletrica_nbr()
    test_orcamento_blocks_nbr_chunks()
    test_estruturas_blocks_sinapi()
    test_agent_rerank_prefers_aligned_discipline()
    test_orcamento_scope_base_keys()
    test_all_engineering_agents_have_scope()
    test_chat_agent_no_rag()
    test_parse_edition_year_from_filename()
    test_edition_rerank_prefers_2014_when_query_specifies()
    test_edition_rerank_prefers_newer_without_year_in_query()
    print("OK — test_agent_rag")
