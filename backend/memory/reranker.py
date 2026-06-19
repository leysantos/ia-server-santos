"""Rerank leve por metadata — sem modelos pesados."""

from __future__ import annotations

from typing import Optional

from config import settings
from memory.models import DocumentChunk
from memory.nbr_catalog import parse_nbr_code
from memory.nbr_edition import compute_edition_boost


def light_rerank(
    hits: list[tuple[DocumentChunk, float]],
    *,
    query: str = "",
    discipline: Optional[str] = None,
    content_type: Optional[str] = None,
    nbr_code: Optional[str] = None,
) -> list[tuple[DocumentChunk, float]]:
    """
    Reordena hits com boosts baratos (metadata + NBR na query).
    Fallback: score vetorial original.
    """
    if not hits or not settings.USE_RAG_LIGHT_RERANK:
        return hits

    boost_nbr = nbr_code or parse_nbr_code(query)
    disc_upper = (discipline or "").upper()
    ct = (content_type or "").lower()

    reranked: list[tuple[DocumentChunk, float]] = []
    for chunk, score in hits:
        s = float(score)
        meta = chunk.metadata or {}

        if disc_upper and chunk.discipline and chunk.discipline.upper() == disc_upper:
            s += settings.RAG_BOOST_DISCIPLINE
        if ct and meta.get("content_type", "").lower() == ct:
            s += settings.RAG_BOOST_DOC_TYPE
        if boost_nbr and meta.get("nbr_code") == boost_nbr:
            s += settings.RAG_BOOST_NBR
        s += compute_edition_boost(query, chunk, nbr_query=boost_nbr)
        if meta.get("confidence") and float(meta["confidence"]) >= 0.85:
            s += 0.02

        reranked.append((chunk, s))

    reranked.sort(key=lambda x: x[1], reverse=True)
    return reranked
