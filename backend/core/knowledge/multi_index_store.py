"""
Multi-Index Store — um índice FAISS por base de conhecimento (imutável em runtime).

Otimização: embed da query UMA vez, busca em N bases com mesmo vetor.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from config import settings
from config.settings import RAG_TOP_K, RAG_TOP_K_MAX
from core.knowledge.constants import KNOWLEDGE_INDEX_DIR, KNOWLEDGE_INDEX_NAMES, BASE_DOC_TYPES
from core.knowledge.content_types import BASE_KEY_TO_CONTENT_TYPE
from memory.embeddings import NomicEmbedder
from memory.faiss_store import FaissVectorStore
from memory.models import DocumentChunk
from memory.rag_metrics import RAGMetrics, timed_section
from memory.rag_runtime import rag_query_context
from memory.reranker import light_rerank
from memory.semantic_cache import SemanticQueryCache

logger = logging.getLogger(__name__)

_store: Optional["MultiIndexKnowledgeStore"] = None
_lock = threading.Lock()


class MultiIndexKnowledgeStore:
    """Gerencia múltiplos FaissVectorStore — somente leitura via retrieve (indexação via script)."""

    def __init__(self, embedder: Optional[NomicEmbedder] = None) -> None:
        self.embedder = embedder or NomicEmbedder()
        self.semantic_cache = (
            SemanticQueryCache() if settings.USE_RAG_SEMANTIC_CACHE else None
        )
        self.last_metrics = RAGMetrics()
        self._stores: dict[str, FaissVectorStore] = {}
        KNOWLEDGE_INDEX_DIR.mkdir(parents=True, exist_ok=True)
        for base_key, index_name in KNOWLEDGE_INDEX_NAMES.items():
            path = KNOWLEDGE_INDEX_DIR / index_name
            path.mkdir(parents=True, exist_ok=True)
            self._stores[base_key] = FaissVectorStore(index_dir=path)

    def get_store(self, base_key: str) -> FaissVectorStore:
        if base_key not in self._stores:
            raise KeyError(f"Base de conhecimento desconhecida: {base_key}")
        return self._stores[base_key]

    def _clamp_top_k(self, top_k: int) -> int:
        return max(settings.RAG_TOP_K_MIN, min(top_k, RAG_TOP_K_MAX))

    def search(
        self,
        base_key: str,
        query: str,
        *,
        discipline: Optional[str] = None,
        doc_type: Optional[str] = None,
        top_k: int = RAG_TOP_K,
        query_embedding: Optional[list[float]] = None,
    ) -> list[tuple[DocumentChunk, float]]:
        return self.search_many(
            [base_key],
            query,
            discipline=discipline,
            top_k=top_k,
            query_embedding=query_embedding,
        )

    def search_many(
        self,
        base_keys: list[str],
        query: str,
        *,
        discipline: Optional[str] = None,
        top_k: int = RAG_TOP_K,
        query_embedding: Optional[list[float]] = None,
        agent_slug: Optional[str] = None,
    ) -> list[tuple[DocumentChunk, float]]:
        scope = None
        if agent_slug and settings.USE_AGENT_SCOPED_RAG:
            from core.knowledge.rag.agent_scopes import get_agent_scope

            scope = get_agent_scope(agent_slug)
            base_keys = list(scope.base_keys)
            discipline = scope.discipline
        else:
            base_keys = list(base_keys)

        k = self._clamp_top_k(top_k)
        metrics = RAGMetrics(top_k=k, discipline=discipline, bases_used=base_keys)
        content_type = BASE_KEY_TO_CONTENT_TYPE.get(base_keys[0]) if base_keys else None

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
                cache_key_ct = content_type
                cached = self.semantic_cache.lookup(
                    query,
                    query_embedding,
                    discipline=discipline,
                    content_type=cache_key_ct,
                )
                if cached:
                    metrics.cache_hit = True
                    metrics.hits_count = len(cached[:k])
                    metrics.total_rag_latency_ms = (
                        metrics.embedding_time_ms + metrics.retrieval_time_ms
                    )
                    self.last_metrics = metrics
                    return cached[:k]

            per_base = max(2, k // max(len(base_keys), 1))
            merged: list[tuple[DocumentChunk, float]] = []

            with timed_section(metrics, "retrieval_time_ms"):
                for key in base_keys:
                    store = self.get_store(key)
                    if store.count() == 0:
                        continue
                    ct = BASE_KEY_TO_CONTENT_TYPE.get(key)
                    doc_type = BASE_DOC_TYPES.get(key, key)
                    hits = store.search(
                        query_embedding=query_embedding,
                        top_k=per_base,
                        discipline=discipline,
                        doc_type=doc_type,
                        content_type=ct,
                        min_score=settings.RAG_MIN_SCORE,
                    )
                    merged.extend(hits)

            with timed_section(metrics, "rerank_time_ms"):
                if scope and settings.USE_AGENT_SCOPED_RAG:
                    from core.knowledge.rag.agent_reranker import agent_rerank
                    from core.knowledge.rag.agent_scopes import filter_hits_by_agent_scope

                    merged = filter_hits_by_agent_scope(merged, scope)
                    merged = agent_rerank(merged, query, scope)
                else:
                    merged = light_rerank(
                        merged,
                        query=query,
                        discipline=discipline,
                        content_type=content_type,
                    )
                merged.sort(key=lambda x: x[1], reverse=True)
                merged = merged[:k]

            if self.semantic_cache and merged and settings.USE_RAG_SEMANTIC_CACHE:
                self.semantic_cache.store(
                    query,
                    query_embedding,
                    merged,
                    discipline=discipline,
                    content_type=content_type,
                )

        metrics.hits_count = len(merged)
        metrics.total_rag_latency_ms = (
            metrics.embedding_time_ms
            + metrics.retrieval_time_ms
            + metrics.rerank_time_ms
        )
        self.last_metrics = metrics
        return merged

    def stats(self) -> dict[str, int]:
        return {key: store.count() for key, store in self._stores.items()}

    def reload_from_disk(self) -> None:
        for store in self._stores.values():
            store.reload()

    def total_chunks(self) -> int:
        return sum(self.stats().values())


def get_multi_index_store() -> MultiIndexKnowledgeStore:
    global _store
    with _lock:
        if _store is None:
            _store = MultiIndexKnowledgeStore()
        return _store
