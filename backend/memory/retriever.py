import hashlib
import re
from typing import Optional

from config import settings
from config.settings import (
    AGENT_CONTEXT_LIMITS,
    RAG_MIN_SCORE,
    RAG_TOP_K,
    RAG_TOP_K_MAX,
)
from memory.embeddings import NomicEmbedder
from memory.faiss_store import FaissVectorStore
from memory.models import DocumentChunk
from memory.nbr_catalog import parse_nbr_code
from memory.rag_metrics import RAGMetrics, timed_section
from memory.rag_observer import get_rag_observer
from memory.rag_runtime import rag_query_context
from memory.reranker import light_rerank
from memory.semantic_cache import SemanticQueryCache

_UNSET = object()


class Retriever:
    """
    Hybrid Search RAG v2 (index-first, zero PDF I/O):
    - similaridade vetorial (FAISS)
    - filtro por metadata (disciplina, doc_type, content_type)
    - cache semântico de top-K
    - rerank leve opcional
    """

    def __init__(
        self,
        store: FaissVectorStore,
        embedder: Optional[NomicEmbedder] = None,
        top_k: int = RAG_TOP_K,
        min_score: float = RAG_MIN_SCORE,
        semantic_cache=_UNSET,
    ):
        self.store = store
        self.embedder = embedder or NomicEmbedder()
        self.top_k = min(top_k, RAG_TOP_K_MAX)
        self.min_score = min_score
        if semantic_cache is _UNSET:
            self.semantic_cache = (
                SemanticQueryCache() if settings.USE_RAG_SEMANTIC_CACHE else None
            )
        else:
            self.semantic_cache = semantic_cache
        self.last_metrics = RAGMetrics()

    def _extract_nbr_from_query(self, query: str) -> Optional[str]:
        return parse_nbr_code(query)

    def _clamp_top_k(self, top_k: Optional[int]) -> int:
        k = top_k or self.top_k
        return max(settings.RAG_TOP_K_MIN, min(k, RAG_TOP_K_MAX))

    def retrieve(
        self,
        query: str,
        discipline: Optional[str] = None,
        doc_type: Optional[str] = None,
        nbr_code: Optional[str] = None,
        top_k: Optional[int] = None,
        *,
        query_embedding: Optional[list[float]] = None,
        content_type: Optional[str] = None,
        agent_slug: Optional[str] = None,
    ) -> list[tuple[DocumentChunk, float]]:
        k = self._clamp_top_k(top_k)
        metrics = RAGMetrics(top_k=k, discipline=discipline)
        nbr_boost = nbr_code or self._extract_nbr_from_query(query)
        ct = content_type or doc_type

        scope = None
        if agent_slug and settings.USE_AGENT_SCOPED_RAG:
            from core.knowledge.rag.agent_scopes import get_agent_scope

            scope = get_agent_scope(agent_slug)
            discipline = scope.discipline
            ct = ct or (next(iter(scope.allowed_content_types), None) if scope.allowed_content_types else None)

        with rag_query_context():
            if query_embedding is None:
                with timed_section(metrics, "embedding_time_ms"):
                    query_embedding = self.embedder.embed_query(query)
                metrics.embedding_cache_hit = getattr(
                    self.embedder, "last_cache_hit", False
                )
            else:
                metrics.embedding_time_ms = 0.0
                metrics.embedding_cache_hit = True

            if self.semantic_cache and settings.USE_RAG_SEMANTIC_CACHE:
                cached = self.semantic_cache.lookup(
                    query,
                    query_embedding,
                    discipline=discipline,
                    content_type=ct,
                )
                if cached:
                    metrics.cache_hit = True
                    metrics.hits_count = len(cached[:k])
                    metrics.total_rag_latency_ms = (
                        metrics.embedding_time_ms + metrics.retrieval_time_ms
                    )
                    self.last_metrics = metrics
                    self._observe(query, discipline, metrics.hits_count, metrics)
                    return cached[:k]

            with timed_section(metrics, "retrieval_time_ms"):
                hits = self.store.search(
                    query_embedding=query_embedding,
                    top_k=k,
                    discipline=discipline,
                    doc_type=doc_type,
                    content_type=content_type,
                    nbr_code=nbr_code,
                    nbr_boost=nbr_boost,
                    min_score=self.min_score,
                )

            with timed_section(metrics, "rerank_time_ms"):
                if scope and settings.USE_AGENT_SCOPED_RAG:
                    from core.knowledge.rag.agent_reranker import agent_rerank
                    from core.knowledge.rag.agent_scopes import filter_hits_by_agent_scope

                    hits = filter_hits_by_agent_scope(hits, scope)
                    hits = agent_rerank(hits, query, scope)
                else:
                    hits = light_rerank(
                        hits,
                        query=query,
                        discipline=discipline,
                        content_type=ct,
                        nbr_code=nbr_boost,
                    )
                hits = self._apply_evolution_ranking(hits)
                hits = hits[:k]

            if self.semantic_cache and hits and settings.USE_RAG_SEMANTIC_CACHE:
                self.semantic_cache.store(
                    query,
                    query_embedding,
                    hits,
                    discipline=discipline,
                    content_type=ct,
                )

        metrics.hits_count = len(hits)
        metrics.total_rag_latency_ms = (
            metrics.embedding_time_ms
            + metrics.retrieval_time_ms
            + metrics.rerank_time_ms
        )
        self.last_metrics = metrics
        self._observe(query, discipline, metrics.hits_count, metrics)
        return hits

    @staticmethod
    def _observe(
        query: str,
        discipline: Optional[str],
        hits_count: int,
        metrics: RAGMetrics,
    ) -> None:
        if not settings.RAG_OBSERVABILITY_ENABLED:
            return
        try:
            get_rag_observer().record(
                query,
                discipline=discipline,
                hits_count=hits_count,
                metrics=metrics,
            )
        except Exception:
            pass

    def _apply_evolution_ranking(
        self, hits: list[tuple[DocumentChunk, float]]
    ) -> list[tuple[DocumentChunk, float]]:
        try:
            from core.evolution.rag_evolution import apply_rag_score_evolution

            return apply_rag_score_evolution(hits)
        except Exception:
            return hits

    @staticmethod
    def _dedupe_hits(
        hits: list[tuple[DocumentChunk, float]],
    ) -> list[tuple[DocumentChunk, float]]:
        seen: set[str] = set()
        deduped: list[tuple[DocumentChunk, float]] = []

        for chunk, score in hits:
            signature = hashlib.sha256(
                re.sub(r"\s+", " ", chunk.text.strip().lower()[:300]).encode()
            ).hexdigest()

            if signature in seen:
                continue

            seen.add(signature)
            deduped.append((chunk, score))

        return deduped

    @staticmethod
    def _context_limit_for(discipline: Optional[str]) -> int:
        if discipline and discipline in AGENT_CONTEXT_LIMITS:
            return AGENT_CONTEXT_LIMITS[discipline]
        return AGENT_CONTEXT_LIMITS["default"]

    def build_context(
        self,
        query: str,
        discipline: Optional[str] = None,
        doc_type: Optional[str] = None,
        nbr_code: Optional[str] = None,
        top_k: Optional[int] = None,
        *,
        query_embedding: Optional[list[float]] = None,
        content_type: Optional[str] = None,
        agent_slug: Optional[str] = None,
    ) -> str:
        hits = self.retrieve(
            query=query,
            discipline=discipline,
            doc_type=doc_type,
            nbr_code=nbr_code,
            top_k=top_k,
            query_embedding=query_embedding,
            content_type=content_type,
            agent_slug=agent_slug,
        )

        if not hits:
            return ""

        hits = self._dedupe_hits(hits)
        max_chars = self._context_limit_for(discipline)

        blocks: list[str] = []
        total_chars = 0

        for chunk, score in hits:
            nbr = chunk.metadata.get("norma", "")
            header = f"[{chunk.source or 'documento'}"
            if nbr:
                header += f" | {nbr}"
            header += f" | score={score:.3f}]"

            block = f"{header}\n{chunk.text}"
            if total_chars + len(block) > max_chars:
                remaining = max_chars - total_chars
                if remaining > 200:
                    blocks.append(block[:remaining] + "…")
                break

            blocks.append(block)
            total_chars += len(block)

        return "\n\n---\n\n".join(blocks)
