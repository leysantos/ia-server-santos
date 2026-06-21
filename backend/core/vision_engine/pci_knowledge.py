"""Recuperação normativa CBMAM/PCI para o Vision Engine."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_PCI_RAG_QUERIES = (
    "IT-11 população dimensionamento saídas emergência CBMAM Amazonas",
    "NT-03 porta portão correr rota fuga termo responsabilidade CBMAM",
    "NBR 9077 rotas de fuga sinalização emergência edificação",
    "projeto simplificado PSCIP edificação térrea CBMAM",
    "NBR 10898 sinalização segurança contra incêndio",
)


def retrieve_pci_normative_context(
    *,
    filename: str = "",
    ocr_text: str = "",
    extra_context: str = "",
    top_k: int = 6,
) -> dict[str, Any]:
    """
    Busca trechos normativos PCI/CBMAM na Knowledge Layer global.
    Retorna contexto formatado + metadados para auditoria (rag_sources).
    """
    seed = " ".join(
        p
        for p in (
            filename,
            ocr_text[:400],
            extra_context[:400],
            "PCI CBMAM incêndio saídas emergência",
        )
        if p
    )

    hits: list[dict[str, Any]] = []
    bases_used: set[str] = set()
    context_blocks: list[str] = []
    rag_available = False

    try:
        from core.knowledge.rag.agent_retriever import retrieve_for_agent

        seen: set[str] = set()
        for query in _PCI_RAG_QUERIES:
            q = f"{query} {seed[:120]}".strip()
            result = retrieve_for_agent(
                q,
                agent_slug="incendio",
                discipline_hint="INCÊNDIO",
                top_k=max(2, top_k // len(_PCI_RAG_QUERIES) + 1),
            )
            if result.hits:
                rag_available = True
            for base in result.bases_used:
                bases_used.add(str(base))
            for chunk, score in result.hits:
                meta = chunk.metadata or {}
                norma = (
                    meta.get("norma")
                    or meta.get("nbr_code")
                    or meta.get("source")
                    or chunk.source
                    or "CBMAM/NBR"
                )
                item = meta.get("section") or meta.get("clause") or ""
                trecho = (chunk.text or "")[:900]
                sig = re.sub(r"\s+", " ", trecho[:160].lower())
                if sig in seen:
                    continue
                seen.add(sig)
                hits.append(
                    {
                        "norma": norma,
                        "item": item,
                        "trecho": trecho,
                        "score": round(float(score), 4),
                        "contexto": meta.get("title") or chunk.discipline or "",
                    }
                )
            if result.context_text and result.context_text not in context_blocks:
                context_blocks.append(result.context_text[:2000])
    except Exception as exc:
        logger.warning("RAG PCI (agent incendio) indisponível: %s", exc)

    if len(hits) < 2:
        try:
            from core.project_review.rag_bridge import retrieve_normative_context

            bridge_hits = retrieve_normative_context(
                seed[:500],
                discipline="pci",
                top_k=top_k,
            )
            for h in bridge_hits:
                trecho = h.get("trecho") or ""
                if trecho.startswith("Consulta normativa sugerida"):
                    continue
                sig = re.sub(r"\s+", " ", trecho[:160].lower())
                if sig in {re.sub(r"\s+", " ", (x.get("trecho") or "")[:160].lower()) for x in hits}:
                    continue
                hits.append(h)
                rag_available = True
        except Exception as exc:
            logger.warning("RAG PCI (rag_bridge) indisponível: %s", exc)

    hits = hits[:top_k]

    context_text = ""
    if hits:
        lines = [
            "CONTEXTO NORMATIVO (Knowledge Layer — CBMAM/NBR PCI):",
            "Use estes trechos para citar ITs/NBRs por número ao avaliar conformidade.",
        ]
        for h in hits:
            norma = h.get("norma") or "?"
            item = h.get("item") or ""
            header = f"[{norma}"
            if item:
                header += f" §{item}"
            header += f" | score={h.get('score', 0)}]"
            lines.append(f"{header}\n{(h.get('trecho') or '')[:800]}")
        context_text = "\n\n".join(lines)
    elif context_blocks:
        context_text = context_blocks[0][:4000]

    return {
        "rag_available": rag_available and bool(hits),
        "hits_count": len(hits),
        "bases_used": sorted(bases_used),
        "sources": hits,
        "context_text": context_text,
        "queries_used": list(_PCI_RAG_QUERIES),
    }


def format_pci_knowledge_block(knowledge: dict[str, Any]) -> str:
    """Bloco curto para injetar no prompt de visão."""
    if not knowledge.get("context_text"):
        return (
            "[AVISO RAG] Base normativa PCI/CBMAM não retornou trechos indexados. "
            "Cite IT-11, NT-03, NBR 9077 e NBR 10898 com base no conhecimento geral."
        )
    return knowledge["context_text"]
