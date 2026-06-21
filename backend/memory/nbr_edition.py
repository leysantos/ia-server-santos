"""
Boost de rerank por edição/ano da NBR.

Prioriza a edição citada na query (ex.: NBR 6118:2014) ou, se omitida,
a revisão mais recente indexada (2014 > 2004 > 2001).
"""

from __future__ import annotations

import re
from typing import Optional

from config import settings
from memory.models import DocumentChunk
from memory.nbr_catalog import parse_nbr_code, nbr_codes_match

_YEAR_PATTERN = re.compile(r"(?<![\d])(19\d{2}|20\d{2})(?![\d])")
_MIN_YEAR = 1950
_MAX_YEAR = 2035


def parse_edition_year(text: str, nbr_code: Optional[str] = None) -> Optional[int]:
    """Extrai ano de revisão de query ou nome de arquivo."""
    if not text:
        return None

    if nbr_code:
        anchored = re.search(
            rf"(?:NBR[\s\-_]*)?{re.escape(nbr_code)}[^\d]{{0,40}}(\d{{4}})",
            text,
            re.IGNORECASE,
        )
        if anchored:
            year = int(anchored.group(1))
            if _MIN_YEAR <= year <= _MAX_YEAR:
                return year

        colon = re.search(
            rf"{re.escape(nbr_code)}\s*[/:\-]\s*(\d{{4}})",
            text,
            re.IGNORECASE,
        )
        if colon:
            year = int(colon.group(1))
            if _MIN_YEAR <= year <= _MAX_YEAR:
                return year

    for match in _YEAR_PATTERN.finditer(text):
        year = int(match.group(1))
        if _MIN_YEAR <= year <= _MAX_YEAR:
            return year

    return None


def chunk_edition_year(chunk: DocumentChunk) -> Optional[int]:
    meta = chunk.metadata or {}
    if meta.get("edition_year"):
        try:
            return int(meta["edition_year"])
        except (TypeError, ValueError):
            pass
    for field in ("filename", "source", "path", "norma"):
        val = meta.get(field) or (chunk.source if field == "source" else "")
        if not val:
            continue
        nbr = meta.get("nbr_code") or parse_nbr_code(str(val))
        year = parse_edition_year(str(val), nbr)
        if year:
            return year
    if chunk.source:
        nbr = meta.get("nbr_code") or parse_nbr_code(chunk.source)
        return parse_edition_year(chunk.source, nbr)
    return None


def compute_edition_boost(
    query: str,
    chunk: DocumentChunk,
    *,
    nbr_query: Optional[str] = None,
    query_year: Optional[int] = None,
) -> float:
    """Ajuste de score por alinhamento de edição da norma."""
    if not settings.USE_NBR_EDITION_RERANK:
        return 0.0

    meta = chunk.metadata or {}
    nbr_chunk = meta.get("nbr_code") or parse_nbr_code(chunk.source or "")
    if not nbr_chunk:
        return 0.0

    nbr_q = nbr_query or parse_nbr_code(query)
    if nbr_q and not nbr_codes_match(nbr_chunk, nbr_q):
        return 0.0

    chunk_year = chunk_edition_year(chunk)
    if chunk_year is None:
        return 0.0

    q_year = query_year if query_year is not None else parse_edition_year(query, nbr_q or nbr_chunk)

    if q_year is not None:
        if chunk_year == q_year:
            return settings.RAG_BOOST_NBR_EDITION_MATCH
        diff = abs(chunk_year - q_year)
        return max(-settings.RAG_PENALTY_NBR_EDITION_MISMATCH, -0.02 * diff)

    # Query sem ano — favorece revisão mais recente
    recency = (chunk_year - 1990) * settings.RAG_BOOST_NBR_EDITION_RECENCY
    return min(settings.RAG_BOOST_NBR_EDITION_MAX, max(0.0, recency))


def apply_edition_rerank(
    hits: list[tuple[DocumentChunk, float]],
    query: str,
) -> list[tuple[DocumentChunk, float]]:
    if not hits or not settings.USE_NBR_EDITION_RERANK:
        return hits

    nbr_query = parse_nbr_code(query)
    query_year = parse_edition_year(query, nbr_query)

    adjusted: list[tuple[DocumentChunk, float]] = []
    for chunk, score in hits:
        boost = compute_edition_boost(
            query,
            chunk,
            nbr_query=nbr_query,
            query_year=query_year,
        )
        adjusted.append((chunk, float(score) + boost))

    adjusted.sort(key=lambda x: x[1], reverse=True)
    return adjusted


def supplement_edition_hits(
    hits: list[tuple[DocumentChunk, float]],
    query: str,
    multi_store,
    base_keys: list[str],
    *,
    max_extra: int = 5,
) -> list[tuple[DocumentChunk, float]]:
    """
    Garante chunks da edição alvo no pool (ex.: 6118:2014) mesmo fora do top-K vetorial.
    """
    if not settings.USE_NBR_EDITION_RERANK:
        return hits

    nbr_query = parse_nbr_code(query)
    if not nbr_query:
        return hits

    query_year = parse_edition_year(query, nbr_query)
    target_year = query_year

    if target_year is None:
        available: list[int] = []
        for key in base_keys:
            for chunk in multi_store.get_store(key).chunks:
                if not nbr_codes_match((chunk.metadata or {}).get("nbr_code"), nbr_query):
                    continue
                y = chunk_edition_year(chunk)
                if y:
                    available.append(y)
        if not available:
            return hits
        target_year = max(available)

    seen: set[str] = set()
    for chunk, _ in hits:
        sig = (chunk.metadata or {}).get("path") or chunk.source or chunk.text[:80]
        seen.add(sig)

    embedder = multi_store.embedder
    query_embedding = embedder.embed_query(query)
    extra: list[tuple[DocumentChunk, float]] = []

    for key in base_keys:
        for chunk in multi_store.get_store(key).chunks:
            meta = chunk.metadata or {}
            if not nbr_codes_match(meta.get("nbr_code"), nbr_query):
                continue
            if chunk_edition_year(chunk) != target_year:
                continue
            sig = meta.get("path") or chunk.source or chunk.text[:80]
            if sig in seen:
                continue
            if not chunk.embedding:
                if not multi_store.get_store(key).index:
                    continue
                try:
                    import faiss
                    import numpy as np

                    chunk_idx = multi_store.get_store(key).chunks.index(chunk)
                    if chunk_idx >= multi_store.get_store(key).index.ntotal:
                        continue
                    chunk_vec = multi_store.get_store(key).index.reconstruct(chunk_idx)
                except (ValueError, RuntimeError):
                    continue
            else:
                import numpy as np

                chunk_vec = np.array(chunk.embedding, dtype=np.float32)
            import faiss
            import numpy as np

            vec = np.array([query_embedding], dtype=np.float32)
            emb = np.array([chunk_vec], dtype=np.float32)
            faiss.normalize_L2(vec)
            faiss.normalize_L2(emb)
            sim = float(np.dot(vec, emb.T)[0][0])
            boost = settings.RAG_BOOST_NBR_EDITION_MATCH if query_year else settings.RAG_BOOST_NBR_EDITION_MAX
            extra.append((chunk, sim + boost))
            seen.add(sig)

    if not extra:
        return hits

    extra.sort(key=lambda x: x[1], reverse=True)
    merged = extra[:max_extra] + list(hits)
    merged.sort(key=lambda x: x[1], reverse=True)
    return merged
