"""
Knowledge Base Router — cérebro de dados técnicos multi-base.

Detecta domínio → escolhe índice(s) → injeta contexto no pipeline de agentes.
Bases imutáveis: loops de evolução NUNCA escrevem aqui.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from config import settings
from core.knowledge.constants import DOMAIN_TO_BASES, KNOWLEDGE_INDEX_NAMES
from core.knowledge.domain_detector import detect_domain
from core.knowledge.multi_index_store import MultiIndexKnowledgeStore, get_multi_index_store
from memory.models import DocumentChunk
from memory.nbr_catalog import parse_nbr_code
from memory.rag_observer import get_rag_observer

logger = logging.getLogger(__name__)

_router: Optional["KnowledgeBaseRouter"] = None


@dataclass
class KnowledgeContext:
    query: str
    domain: str
    bases_used: list[str] = field(default_factory=list)
    hits_count: int = 0
    context_text: str = ""
    fallback_legacy: bool = False
    metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "bases_used": self.bases_used,
            "hits_count": self.hits_count,
            "fallback_legacy": self.fallback_legacy,
            "context_length": len(self.context_text),
            "metrics": self.metrics,
        }


class KnowledgeBaseRouter:
    """Roteamento read-only sobre índices FAISS versionados."""

    def detect_domain(self, text: str, discipline: Optional[str] = None) -> str:
        return detect_domain(text, discipline=discipline)

    def retrieve(
        self,
        query: str,
        domain: Optional[str] = None,
        discipline: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> list[tuple[DocumentChunk, float]]:
        resolved_domain = domain or self.detect_domain(query, discipline)
        base_keys = DOMAIN_TO_BASES.get(resolved_domain, DOMAIN_TO_BASES["general"])
        k = top_k or settings.RAG_TOP_K

        store = self._store
        hits = store.search_many(base_keys, query, discipline=discipline, top_k=k)

        if not hits:
            hits = self._legacy_fallback(query, discipline, k)

        return hits

    def retrieve_context(
        self,
        query: str,
        domain: Optional[str] = None,
        discipline: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> KnowledgeContext:
        from core.knowledge.rag.agent_router import route_query_to_agent
        from core.knowledge.rag.agent_retriever import retrieve_for_agent

        agent = route_query_to_agent(query, discipline_hint=discipline)

        if settings.USE_AGENT_SCOPED_RAG:
            result = retrieve_for_agent(
                query,
                agent_slug=agent,
                discipline_hint=discipline,
                top_k=top_k,
            )
            if result.agent_slug == "chat":
                return KnowledgeContext(
                    query=query,
                    domain="chat",
                    bases_used=[],
                    hits_count=0,
                    context_text="",
                    metrics=result.metrics,
                )

            resolved_domain = domain or self.detect_domain(query, discipline)
            bases_used = result.bases_used or [
                KNOWLEDGE_INDEX_NAMES.get(b, b) for b in result.bases_used
            ]

            logger.info(
                "knowledge_retrieval agent=%s domain=%s bases=%s hits=%d latency_ms=%.1f",
                result.agent_slug,
                resolved_domain,
                bases_used,
                len(result.hits),
                result.metrics.get("total_rag_latency_ms", 0),
            )

            return KnowledgeContext(
                query=query,
                domain=resolved_domain,
                bases_used=[KNOWLEDGE_INDEX_NAMES.get(b, b) for b in result.bases_used],
                hits_count=len(result.hits),
                context_text=result.context_text,
                fallback_legacy=False,
                metrics={**result.metrics, "agent_slug": result.agent_slug},
            )

        resolved_domain = domain or self.detect_domain(query, discipline)
        base_keys = DOMAIN_TO_BASES.get(resolved_domain, DOMAIN_TO_BASES["general"])
        k = top_k or settings.RAG_TOP_K

        hits = self._store.search_many(base_keys, query, discipline=discipline, top_k=k)
        fallback = False

        if not hits and self._store.total_chunks() == 0:
            hits = self._legacy_fallback(query, discipline, k)
            fallback = True
        elif not hits:
            hits = self._legacy_fallback(query, discipline, k)
            fallback = bool(hits)

        context_text = self._format_hits(hits, resolved_domain)
        bases_used = [KNOWLEDGE_INDEX_NAMES.get(b, b) for b in base_keys]
        metrics = self._store.last_metrics.log_summary()

        if settings.RAG_OBSERVABILITY_ENABLED:
            try:
                get_rag_observer().record(
                    query,
                    discipline=discipline,
                    domain=resolved_domain,
                    hits_count=len(hits),
                    metrics=self._store.last_metrics,
                )
            except Exception:
                pass

        logger.info(
            "knowledge_retrieval domain=%s bases=%s hits=%d latency_ms=%.1f cache_hit=%s",
            resolved_domain,
            bases_used,
            len(hits),
            metrics.get("total_rag_latency_ms", 0),
            metrics.get("cache_hit", False),
        )

        return KnowledgeContext(
            query=query,
            domain=resolved_domain,
            bases_used=bases_used,
            hits_count=len(hits),
            context_text=context_text,
            fallback_legacy=fallback,
            metrics=metrics,
        )

    @staticmethod
    def _format_hits(
        hits: list[tuple[DocumentChunk, float]],
        domain: str,
    ) -> str:
        if not hits:
            return ""

        blocks: list[str] = []
        seen: set[str] = set()

        for chunk, score in hits:
            sig = hashlib.sha256(chunk.text[:200].encode()).hexdigest()[:12]
            if sig in seen:
                continue
            seen.add(sig)

            kb = chunk.metadata.get("knowledge_base") or chunk.doc_type or "base"
            norma = chunk.metadata.get("norma") or chunk.metadata.get("nbr_code") or ""
            header = f"[{kb.upper()} | {chunk.source or 'doc'}"
            if norma:
                header += f" | {norma}"
            header += f" | score={score:.3f}]"
            blocks.append(f"{header}\n{chunk.text}")

        intro = f"CONTEXTO TÉCNICO ({domain.upper()}) — bases imutáveis versionadas:\n"
        return intro + "\n\n---\n\n".join(blocks)

    @staticmethod
    def _legacy_fallback(
        query: str,
        discipline: Optional[str],
        top_k: int,
    ) -> list[tuple[DocumentChunk, float]]:
        """Fallback para índice FAISS legado único quando multi-index vazio."""
        try:
            from memory.rag_engine import get_rag_engine

            engine = get_rag_engine()
            if engine.indexed_chunks == 0:
                return []
            nbr = parse_nbr_code(query)
            return engine.retrieve(
                query=query,
                discipline=discipline,
                nbr_code=nbr,
                top_k=top_k,
            )
        except Exception as exc:
            logger.debug("Knowledge legacy fallback falhou: %s", exc)
            return []

    @property
    def _store(self) -> MultiIndexKnowledgeStore:
        return get_multi_index_store()

    def stats(self) -> dict[str, Any]:
        return {
            "multi_index": self._store.stats(),
            "total_multi_chunks": self._store.total_chunks(),
            "index_names": KNOWLEDGE_INDEX_NAMES,
        }


def get_knowledge_router() -> KnowledgeBaseRouter:
    global _router
    if _router is None:
        _router = KnowledgeBaseRouter()
    return _router


def enrich_route_with_knowledge(route_result: dict) -> dict:
    """
    Enriquece route_result com contexto multi-base antes do dispatch.
    Opt-in via USE_KNOWLEDGE_ROUTER e/ou USE_DISCIPLINE_KNOWLEDGE_ROUTER.
    """
    use_knowledge = settings.USE_KNOWLEDGE_ROUTER
    use_discipline = settings.USE_DISCIPLINE_KNOWLEDGE_ROUTER

    if not use_knowledge and not use_discipline:
        return route_result

    if route_result.get("knowledge"):
        return route_result

    query = route_result.get("input") or ""
    discipline = route_result.get("discipline")
    use_rag = route_result.get("_use_rag", True)

    if not query or not use_rag or discipline in ("CHAT", "GERAL", None):
        return route_result

    try:
        enriched = dict(route_result)
        existing = enriched.get("context") or ""

        if use_discipline:
            from core.knowledge.router import route_knowledge

            dk = route_knowledge(query, discipline_hint=discipline)
            enriched["discipline_knowledge"] = dk.to_dict()
            if dk.context_text:
                existing = (
                    f"{existing}\n\n---\n\n{dk.context_text}" if existing else dk.context_text
                )

        if use_knowledge:
            router = get_knowledge_router()
            kc = router.retrieve_context(query, discipline=discipline)
            if kc.context_text:
                existing = (
                    f"{existing}\n\n---\n\n{kc.context_text}" if existing else kc.context_text
                )
            enriched["knowledge"] = kc.to_dict()
            logger.info(
                "knowledge_router domain=%s bases=%s hits=%d",
                kc.domain,
                kc.bases_used,
                kc.hits_count,
            )

        if existing:
            enriched["context"] = existing
            return enriched

        return route_result
    except Exception as exc:
        logger.warning("Knowledge router ignorado: %s", exc)
        return route_result
