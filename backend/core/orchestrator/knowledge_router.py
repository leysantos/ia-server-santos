"""
Knowledge Router (Orquestrador) — regras de base e rerank por domínio.

Separação obrigatória:
  A) ENGINEERING → NBR (nunca SINAPI)
  B) COST → SINAPI/TCPO (nunca NBR como fonte de preço)
  C) DOCUMENTATION → TDR, projetos, catálogos
"""

from __future__ import annotations

from dataclasses import dataclass

from memory.models import DocumentChunk

from core.orchestrator.domain_classifier import (
    KNOWLEDGE_COST,
    KNOWLEDGE_DOCUMENTATION,
    KNOWLEDGE_ENGINEERING,
    DomainClassification,
    KnowledgeDomain,
)

# Rerank weights (spec)
ENG_BOOST_NBR_OFFICIAL = 0.5
ENG_BOOST_CRITICAL = 0.3
ENG_BOOST_COMPLEMENTARY = 0.2
ENG_PENALTY_GENERIC = 0.2

COST_BOOST_SINAPI = 0.5
COST_BOOST_TCPO = 0.4
COST_PENALTY_NBR = 0.3

CRITICAL_NBRS = frozenset({"6118", "8681", "5410", "5626", "6122"})
COMPLEMENTARY_NBRS = frozenset({"8800", "8160", "7480", "9050", "15575"})


@dataclass(frozen=True)
class KnowledgeRouteConfig:
    knowledge_type: str
    base_keys: tuple[str, ...]
    allowed_content_types: frozenset[str]
    blocked_content_types: frozenset[str]
    rerank_profile: str  # engineering | cost | documentation


def resolve_knowledge_route(classification: DomainClassification) -> KnowledgeRouteConfig:
    """Escolhe base FAISS e tipos permitidos conforme domínio."""
    domain = classification.primary_domain

    if domain == KnowledgeDomain.COST or classification.is_cost_query:
        return KnowledgeRouteConfig(
            knowledge_type=KNOWLEDGE_COST,
            base_keys=("sinapi", "tcpo"),
            allowed_content_types=frozenset({"sinapi", "tcpo", "cost", "composition"}),
            blocked_content_types=frozenset({"nbrs", "nbr"}),
            rerank_profile="cost",
        )

    if domain == KnowledgeDomain.DOCUMENTATION:
        return KnowledgeRouteConfig(
            knowledge_type=KNOWLEDGE_DOCUMENTATION,
            base_keys=("tdr", "catalogos"),
            allowed_content_types=frozenset(
                {"tdrs", "tdr", "projetos", "project", "catalogos", "catalog", "manuais"}
            ),
            blocked_content_types=frozenset({"sinapi", "tcpo"}),
            rerank_profile="documentation",
        )

    # ENGINEERING (default) — NBR only, zero SINAPI
    return KnowledgeRouteConfig(
        knowledge_type=KNOWLEDGE_ENGINEERING,
        base_keys=("nbr",),
        allowed_content_types=frozenset({"nbrs", "nbr"}),
        blocked_content_types=frozenset({"sinapi", "tcpo", "cost", "composition"}),
        rerank_profile="engineering",
    )


def _chunk_content_type(chunk: DocumentChunk) -> str:
    meta = chunk.metadata or {}
    return (meta.get("content_type") or chunk.doc_type or "").lower()


def _is_sinapi(chunk: DocumentChunk) -> bool:
    ct = _chunk_content_type(chunk)
    text = chunk.text.lower()
    return ct in ("sinapi", "cost") or "sinapi" in text or "sicro" in text


def _is_tcpo(chunk: DocumentChunk) -> bool:
    ct = _chunk_content_type(chunk)
    return ct in ("tcpo", "composition") or "tcpo" in chunk.text.lower()


def _is_nbr(chunk: DocumentChunk) -> bool:
    ct = _chunk_content_type(chunk)
    meta = chunk.metadata or {}
    return (
        ct in ("nbrs", "nbr")
        or bool(meta.get("nbr_code"))
        or bool(meta.get("norma"))
        or "nbr" in chunk.source.lower()
    )


def apply_knowledge_priority_rerank(
    hits: list[tuple[DocumentChunk, float]],
    route: KnowledgeRouteConfig,
) -> list[tuple[DocumentChunk, float]]:
    """
    Rerank por perfil de conhecimento (engenharia vs orçamento).

    ENGINEERING: +NBR oficial, +críticas, -genéricos; penaliza SINAPI
    COST: +SINAPI, +TCPO, -NBR
    """
    if not hits:
        return []

    reranked: list[tuple[DocumentChunk, float]] = []

    for chunk, base_score in hits:
        score = float(base_score)
        meta = chunk.metadata or {}
        nbr_code = str(meta.get("nbr_code", ""))

        if route.rerank_profile == "cost":
            if _is_sinapi(chunk):
                score += COST_BOOST_SINAPI
            elif _is_tcpo(chunk):
                score += COST_BOOST_TCPO
            if _is_nbr(chunk):
                score -= COST_PENALTY_NBR
            if _chunk_content_type(chunk) in route.blocked_content_types:
                score -= 1.0

        elif route.rerank_profile == "engineering":
            if _is_sinapi(chunk) or _is_tcpo(chunk):
                score -= 1.0  # hard penalty — contaminação
            if _is_nbr(chunk):
                score += ENG_BOOST_NBR_OFFICIAL
                if nbr_code in CRITICAL_NBRS:
                    score += ENG_BOOST_CRITICAL
                elif nbr_code in COMPLEMENTARY_NBRS:
                    score += ENG_BOOST_COMPLEMENTARY
            elif _chunk_content_type(chunk) in ("tdrs", "projetos", "manuais"):
                score -= ENG_PENALTY_GENERIC

        else:  # documentation
            ct = _chunk_content_type(chunk)
            if ct in route.allowed_content_types:
                score += 0.3
            if _is_sinapi(chunk) or _is_nbr(chunk):
                score -= 0.15

        reranked.append((chunk, score))

    reranked.sort(key=lambda x: x[1], reverse=True)
    return reranked


def filter_hits_by_route(
    hits: list[tuple[DocumentChunk, float]],
    route: KnowledgeRouteConfig,
) -> list[tuple[DocumentChunk, float]]:
    """Hard block — impede mistura SINAPI ↔ NBR."""
    filtered: list[tuple[DocumentChunk, float]] = []
    for chunk, score in hits:
        ct = _chunk_content_type(chunk)
        if ct and ct in route.blocked_content_types:
            continue
        if route.rerank_profile == "engineering" and (_is_sinapi(chunk) or _is_tcpo(chunk)):
            continue
        if route.rerank_profile == "cost" and _is_nbr(chunk):
            continue
        filtered.append((chunk, score))
    return filtered
