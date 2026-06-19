"""
Agent Retriever — pipeline RAG por agente.

1. route_query_to_agent
2. filter knowledge by agent scope
3. retrieve via FAISS (somente índices do agente)
4. agent-aware rerank
5. top-K (3–8)
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from config import settings
from config.settings import AGENT_CONTEXT_LIMITS, RAG_TOP_K
from core.knowledge.rag.agent_reranker import agent_rerank
from core.knowledge.rag.agent_router import route_query_to_agent
from core.knowledge.rag.agent_scopes import (
    AgentScope,
    filter_hits_by_agent_scope,
    get_agent_scope,
)
from memory.models import DocumentChunk
from memory.nbr_catalog import parse_nbr_code

logger = logging.getLogger(__name__)


@dataclass
class AgentRAGResult:
    query: str
    agent_slug: str
    discipline: str
    hits: list[tuple[DocumentChunk, float]] = field(default_factory=list)
    context_text: str = ""
    bases_used: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_slug": self.agent_slug,
            "discipline": self.discipline,
            "hits_count": len(self.hits),
            "context_length": len(self.context_text),
            "bases_used": self.bases_used,
            "metrics": self.metrics,
        }


def _format_context(
    hits: list[tuple[DocumentChunk, float]],
    scope: AgentScope,
) -> str:
    if not hits:
        return ""

    limit = AGENT_CONTEXT_LIMITS.get(scope.discipline, AGENT_CONTEXT_LIMITS["default"])
    blocks: list[str] = []
    seen: set[str] = set()
    total = 0

    intro = f"CONTEXTO TÉCNICO — Agente {scope.agent_slug.upper()} ({scope.discipline}):\n"
    blocks.append(intro)
    total += len(intro)

    for chunk, score in hits:
        sig = hashlib.sha256(chunk.text[:200].encode()).hexdigest()[:12]
        if sig in seen:
            continue
        seen.add(sig)

        kb = chunk.metadata.get("knowledge_base") or chunk.doc_type or scope.agent_slug
        norma = chunk.metadata.get("norma") or chunk.metadata.get("nbr_code") or ""
        header = f"[{kb.upper()} | {chunk.source or 'doc'}"
        if norma:
            header += f" | {norma}"
        header += f" | score={score:.3f}]"
        block = f"{header}\n{chunk.text}"

        if total + len(block) > limit:
            remaining = limit - total
            if remaining > 200:
                blocks.append(block[:remaining] + "…")
            break
        blocks.append(block)
        total += len(block)

    return "\n\n---\n\n".join(blocks)


def retrieve_for_agent(
    query: str,
    *,
    discipline_hint: Optional[str] = None,
    agent_slug: Optional[str] = None,
    top_k: Optional[int] = None,
) -> AgentRAGResult:
    agent = agent_slug or route_query_to_agent(query, discipline_hint=discipline_hint)
    scope = get_agent_scope(agent)
    k = top_k or settings.RAG_TOP_K

    orch_route = None
    if settings.USE_ENGINEERING_ORCHESTRATOR:
        from core.orchestrator.engineering_orchestrator import get_knowledge_route_for_discipline

        orch_route = get_knowledge_route_for_discipline(query, discipline_hint)
        if orch_route.knowledge_type == "cost":
            agent = "orcamento"
            scope = get_agent_scope("orcamento")

    if agent == "chat" or not scope.uses_technical_rag:
        return AgentRAGResult(
            query=query,
            agent_slug="chat",
            discipline="CHAT",
        )

    oversample_k = min(settings.RAG_TOP_K_MAX, max(k * 2, k))
    hits: list[tuple[DocumentChunk, float]] = []
    search_keys = list(orch_route.base_keys) if orch_route else list(scope.base_keys)
    bases_used: list[str] = search_keys
    metrics: dict[str, Any] = {}

    if search_keys:
        from core.knowledge.multi_index_store import get_multi_index_store

        store = get_multi_index_store()
        store.reload_from_disk()
        raw = store.search_many(
            search_keys,
            query,
            discipline=scope.discipline,
            top_k=oversample_k,
            agent_slug=agent,
        )
        metrics = store.last_metrics.log_summary()
        hits = raw
        from memory.nbr_edition import supplement_edition_hits

        hits = supplement_edition_hits(hits, query, store, search_keys)
    else:
        from memory.rag_engine import get_rag_engine

        engine = get_rag_engine()
        nbr = parse_nbr_code(query)
        primary_doc = "nbr"
        if scope.allowed_content_types & frozenset({"sinapi", "tcpo"}):
            primary_doc = "sinapi"
        raw = engine.retrieve(
            query=query,
            discipline=scope.discipline,
            doc_type=primary_doc,
            nbr_code=nbr,
            top_k=oversample_k,
            agent_slug=agent,
        )
        metrics = engine.retriever.last_metrics.log_summary()
        hits = raw

    hits = filter_hits_by_agent_scope(hits, scope)
    if orch_route and settings.USE_ENGINEERING_ORCHESTRATOR:
        from core.orchestrator.knowledge_router import (
            apply_knowledge_priority_rerank,
            filter_hits_by_route,
        )

        hits = filter_hits_by_route(hits, orch_route)
        hits = apply_knowledge_priority_rerank(hits, orch_route)
    else:
        hits = agent_rerank(hits, query, scope)

    from memory.nbr_edition import apply_edition_rerank

    hits = apply_edition_rerank(hits, query)
    hits = hits[:k]

    context = _format_context(hits, scope)

    logger.info(
        "agent_rag agent=%s discipline=%s bases=%s hits=%d",
        agent,
        scope.discipline,
        bases_used,
        len(hits),
    )

    return AgentRAGResult(
        query=query,
        agent_slug=agent,
        discipline=scope.discipline,
        hits=hits,
        context_text=context,
        bases_used=bases_used,
        metrics=metrics,
    )


def retrieve_context_for_route(
    query: str,
    discipline: Optional[str] = None,
    top_k: Optional[int] = None,
) -> AgentRAGResult:
    """Entry point para enrich_route_result — respeita USE_AGENT_SCOPED_RAG."""
    if not settings.USE_AGENT_SCOPED_RAG:
        return AgentRAGResult(
            query=query,
            agent_slug=route_query_to_agent(query, discipline_hint=discipline),
            discipline=discipline or "",
        )
    return retrieve_for_agent(
        query,
        discipline_hint=discipline,
        top_k=top_k,
    )
