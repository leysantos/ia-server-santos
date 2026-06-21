"""
Agent Reranker — score final por alinhamento com agente especialista.

score =
  semantic_similarity * 0.6
+ agent_alignment_boost * 0.3
+ source_type_relevance * 0.1
- cross_agent_penalty
"""

from __future__ import annotations

import re
from typing import Optional

from memory.models import DocumentChunk
from memory.nbr_catalog import parse_nbr_code, nbr_codes_match

from core.knowledge.rag.agent_scopes import (
    SOURCE_DOCUMENTATION,
    SOURCE_NORMATIVE,
    SOURCE_PRICING,
    AgentScope,
    chunk_content_type,
    is_blocked_for_agent,
)

W_SEMANTIC = 0.6
W_ALIGNMENT = 0.3
W_SOURCE = 0.1
CROSS_AGENT_PENALTY = 0.5


def _agent_alignment_boost(
    chunk: DocumentChunk,
    scope: AgentScope,
    query: str,
) -> float:
    boost = 0.0
    meta = chunk.metadata or {}
    query_l = query.lower()

    disc = (chunk.discipline or "").upper()
    if disc and disc == scope.discipline:
        boost += 0.4

    slug_meta = meta.get("discipline_slug") or meta.get("discipline")
    if isinstance(slug_meta, list):
        slug_meta = slug_meta[0] if slug_meta else ""
    if slug_meta and str(slug_meta).lower() == scope.agent_slug:
        boost += 0.3

    text_l = chunk.text.lower()
    for kw in scope.priority_keywords:
        if kw in query_l and kw in text_l:
            boost += 0.05

    nbr_query = parse_nbr_code(query)
    nbr_chunk = meta.get("nbr_code") or parse_nbr_code(chunk.source or "")
    if nbr_query and nbr_codes_match(nbr_chunk, nbr_query):
        boost += 0.55
    elif nbr_chunk and nbr_chunk in scope.priority_nbrs:
        boost += 0.15

    return min(boost, 1.0)


def _source_type_relevance(chunk: DocumentChunk, scope: AgentScope) -> float:
    ct = chunk_content_type(chunk)
    if not ct:
        return 0.3

    if ct in scope.allowed_content_types or ct.replace("nbr", "nbrs") in scope.allowed_content_types:
        if SOURCE_PRICING in scope.source_types and ct in ("sinapi", "tcpo", "cost", "composition"):
            return 1.0
        if SOURCE_NORMATIVE in scope.source_types and ct in ("nbrs", "nbr"):
            return 1.0
        if SOURCE_DOCUMENTATION in scope.source_types and ct in ("tdrs", "tdr", "projetos", "project", "regional"):
            return 1.0
        if ct in ("catalogos", "catalog", "manuais"):
            return 0.9
        return 0.7
    return 0.0


def _cross_agent_penalty(chunk: DocumentChunk, scope: AgentScope) -> float:
    if is_blocked_for_agent(chunk, scope):
        return CROSS_AGENT_PENALTY
    return 0.0


def agent_rerank(
    hits: list[tuple[DocumentChunk, float]],
    query: str,
    scope: AgentScope,
) -> list[tuple[DocumentChunk, float]]:
    if not hits:
        return []

    reranked: list[tuple[DocumentChunk, float]] = []
    for chunk, semantic_score in hits:
        sem = max(0.0, min(float(semantic_score), 1.0))
        align = _agent_alignment_boost(chunk, scope, query)
        src = _source_type_relevance(chunk, scope)
        cross = _cross_agent_penalty(chunk, scope)

        final = sem * W_SEMANTIC + align * W_ALIGNMENT + src * W_SOURCE - cross
        reranked.append((chunk, final))

    reranked.sort(key=lambda x: x[1], reverse=True)
    return reranked
