"""Métricas de performance do pipeline RAG."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Any, Iterator, Optional


@dataclass
class RAGMetrics:
    """Timings de uma operação de retrieval (ms)."""

    embedding_time_ms: float = 0.0
    retrieval_time_ms: float = 0.0
    rerank_time_ms: float = 0.0
    total_rag_latency_ms: float = 0.0
    cache_hit: bool = False
    embedding_cache_hit: bool = False
    hits_count: int = 0
    top_k: int = 0
    discipline: Optional[str] = None
    domain: Optional[str] = None
    bases_used: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def log_summary(self) -> dict[str, Any]:
        return {
            "embedding_time_ms": round(self.embedding_time_ms, 2),
            "retrieval_time_ms": round(self.retrieval_time_ms, 2),
            "rerank_time_ms": round(self.rerank_time_ms, 2),
            "total_rag_latency_ms": round(self.total_rag_latency_ms, 2),
            "cache_hit": self.cache_hit,
            "embedding_cache_hit": self.embedding_cache_hit,
            "hits_count": self.hits_count,
            "top_k": self.top_k,
            "discipline": self.discipline,
            "domain": self.domain,
            "bases_used": self.bases_used,
        }


@contextmanager
def timed_section(metrics: RAGMetrics, field_name: str) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        setattr(metrics, field_name, getattr(metrics, field_name) + elapsed_ms)
