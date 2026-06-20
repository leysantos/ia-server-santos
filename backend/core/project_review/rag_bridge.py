"""Ponte RAG normativo híbrido para revisão (Módulo F)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def retrieve_normative_context(
    query: str,
    *,
    discipline: str | None = None,
    top_k: int = 8,
) -> list[dict[str, Any]]:
    """
    Busca híbrida vetorial + keyword + rerank via pipeline existente.
    Retorna norma, item, trecho e contexto.
    """
    hits: list[dict[str, Any]] = []

    try:
        from memory.rag_engine import RAGEngine

        engine = RAGEngine()
        scope_slug = _discipline_to_agent_slug(discipline)
        chunks = engine.retriever.retrieve(
            query,
            discipline=scope_slug,
            top_k=top_k,
        )
        for chunk, score in chunks:
            meta = chunk.metadata or {}
            hits.append(
                {
                    "norma": meta.get("source") or chunk.source or "NBR",
                    "item": meta.get("section") or meta.get("clause") or "",
                    "trecho": chunk.text[:1200],
                    "contexto": meta.get("title") or chunk.discipline or "",
                    "score": round(float(score), 4),
                }
            )
    except Exception as exc:
        logger.warning("RAG normativo indisponível: %s", exc)

    if not hits:
        hits.extend(_keyword_fallback(query, discipline))

    return hits[:top_k]


def _discipline_to_agent_slug(discipline: str | None) -> str | None:
    if not discipline:
        return None
    mapping = {
        "estrutura": "estrutural",
        "arquitetura": "arquitetura",
        "hidraulica": "hidraulica",
        "eletrica": "eletrica",
        "pci": "pci",
    }
    return mapping.get(discipline.lower())


def _discipline_to_scope(discipline: str | None) -> str | None:
    return _discipline_to_agent_slug(discipline)


def _keyword_fallback(query: str, discipline: str | None) -> list[dict[str, Any]]:
    """Fallback mínimo quando índice FAISS offline."""
    bases = ["NBR", "CBMAM", "DNIT"]
    if discipline == "orcamento":
        bases = ["SINAPI", "SICRO", "ORSE"]
    return [
        {
            "norma": base,
            "item": "",
            "trecho": f"Consulta normativa sugerida: {query[:200]}",
            "contexto": discipline or "geral",
            "score": 0.0,
        }
        for base in bases[:3]
    ]
