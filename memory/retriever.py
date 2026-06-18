import hashlib
import re
from typing import Optional

from config.settings import (
    AGENT_CONTEXT_LIMITS,
    RAG_MIN_SCORE,
    RAG_TOP_K,
)
from memory.embeddings import NomicEmbedder
from memory.faiss_store import FaissVectorStore
from memory.models import DocumentChunk
from memory.nbr_catalog import parse_nbr_code


class Retriever:
    """
    Hybrid Search RAG v2:
    - similaridade vetorial (FAISS)
    - filtro por metadata (disciplina, doc_type, NBR)
    - ranking final com boosts
    """

    def __init__(
        self,
        store: FaissVectorStore,
        embedder: Optional[NomicEmbedder] = None,
        top_k: int = RAG_TOP_K,
        min_score: float = RAG_MIN_SCORE,
    ):
        self.store = store
        self.embedder = embedder or NomicEmbedder()
        self.top_k = top_k
        self.min_score = min_score

    def _extract_nbr_from_query(self, query: str) -> Optional[str]:
        return parse_nbr_code(query)

    def retrieve(
        self,
        query: str,
        discipline: Optional[str] = None,
        doc_type: Optional[str] = None,
        nbr_code: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> list[tuple[DocumentChunk, float]]:
        query_embedding = self.embedder.embed_query(query)
        nbr_boost = self._extract_nbr_from_query(query)

        return self.store.search(
            query_embedding=query_embedding,
            top_k=top_k or self.top_k,
            discipline=discipline,
            doc_type=doc_type,
            nbr_code=nbr_code,
            nbr_boost=nbr_boost,
            min_score=self.min_score,
        )

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
    ) -> str:
        hits = self.retrieve(
            query=query,
            discipline=discipline,
            doc_type=doc_type,
            nbr_code=nbr_code,
            top_k=top_k,
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
