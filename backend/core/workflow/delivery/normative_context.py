"""Recuperação normativa NBR — desenho técnico e pranchas (Workflow Projetos)."""

from __future__ import annotations

import logging
import re
from typing import Any

from core.knowledge.norm_packs.legal import (
    STAMP_LEGAL_FILTER_NOTICE,
    is_stamp_eligible,
    resolve_legal_source,
)

logger = logging.getLogger(__name__)

# NBRs centrais para produção documental (desenho técnico / pranchas)
DRAWING_NBR_CATALOG: dict[str, str] = {
    "10067": "Princípios gerais de representação em desenho técnico",
    "8196": "Folha de desenho — formatos, margens, carimbo, escala",
    "10126": "Cotagem em desenho técnico",
    "13142": "Dobramento de cópia (pranchas)",
    "6492": "Representação de projetos de arquitetura",
    "9441": "Representação de projetos arquitetônicos (complementar)",
    "7191": "Execução de desenhos — concreto armado",
    "5261": "Símbolos gráficos — eletricidade",
    "8809": "Representação de instalações prediais",
    "13531": "Elaboração de projetos de edificações",
    "10520": "Citações em documentos técnicos",
}

# Consultas RAG por disciplina (prioridade desenho técnico)
_DRAWING_RAG_QUERIES: dict[str, tuple[str, ...]] = {
    "arquitetura": (
        "NBR 6492 representação projetos arquitetura planta corte fachada escala",
        "NBR 10126 cotagem desenho técnico dimensões tolerâncias",
        "NBR 8196 folha desenho carimbo margens formato prancha",
        "NBR 13142 dobramento cópia prancha entrega",
    ),
    "estrutural": (
        "NBR 7191 execução desenhos concreto armado planta forma armadura",
        "NBR 10126 cotagem desenho técnico estrutural",
        "NBR 8196 folha desenho carimbo escala",
    ),
    "incendio": (
        "NBR 6492 representação planta PCI saídas emergência escala",
        "NBR 10126 cotagem desenho técnico",
        "NBR 9077 saídas emergência representação gráfica",
    ),
    "eletrica": (
        "NBR 5261 símbolos gráficos instalações elétricas desenho",
        "NBR 8809 representação instalações prediais elétricas",
        "NBR 10126 cotagem desenho técnico",
    ),
    "hidraulica": (
        "NBR 8809 representação instalações prediais hidráulicas",
        "NBR 10126 cotagem desenho técnico",
    ),
    "geral": (
        "NBR 8196 folha desenho técnico carimbo margens",
        "NBR 10126 cotagem desenho técnico",
        "NBR 13531 elaboração projetos edificações documentação",
    ),
}

_AGENT_BY_DISCIPLINE: dict[str, str] = {
    "arquitetura": "arquitetura",
    "estrutural": "estrutural",
    "incendio": "incendio",
    "eletrica": "eletrica",
    "hidraulica": "hidraulica",
    "geotecnia": "geotecnia",
}


def retrieve_drawing_normative_context(
    *,
    filename: str = "",
    disciplina: str = "geral",
    tipo_desenho: str = "",
    role: str = "prancha",
    top_k: int = 6,
) -> dict[str, Any]:
    """
    Busca trechos NBR de desenho técnico na Knowledge Layer.
    Usado pelo wizard de entrega antes de propor nomenclatura / prancha.
    """
    if role != "prancha":
        queries = (
            "NBR 10520 citações documentos técnicos memorial projeto",
            "NBR 13531 elaboração projetos edificações documentação complementar",
        )
        agent = "arquitetura"
    else:
        disc = (disciplina or "geral").lower()
        queries = _DRAWING_RAG_QUERIES.get(disc, _DRAWING_RAG_QUERIES["geral"])
        agent = _AGENT_BY_DISCIPLINE.get(disc, "arquitetura")

    seed = " ".join(p for p in (filename, tipo_desenho, "desenho técnico prancha") if p)

    hits: list[dict[str, Any]] = []
    bases_used: set[str] = set()
    rag_available = False
    seen: set[str] = set()

    try:
        from core.knowledge.rag.agent_retriever import retrieve_for_agent

        per_query = max(2, top_k // len(queries) + 1)
        for query in queries:
            q = f"{query} {seed[:100]}".strip()
            result = retrieve_for_agent(
                q,
                agent_slug=agent,
                discipline_hint=disciplina.upper() if disciplina else None,
                top_k=per_query,
            )
            if result.hits:
                rag_available = True
            for base in result.bases_used:
                bases_used.add(str(base))
            for chunk, score in result.hits:
                meta = chunk.metadata or {}
                file_ref = meta.get("path") or meta.get("filename") or chunk.source or ""
                legal_source = resolve_legal_source(
                    meta,
                    file_path=str(file_ref) if file_ref else None,
                    doc_type=chunk.doc_type,
                ).value
                norma = (
                    meta.get("norma")
                    or meta.get("nbr_code")
                    or _norma_from_path(meta.get("filename") or meta.get("path") or "")
                    or chunk.source
                    or "NBR"
                )
                trecho = (chunk.text or "")[:900]
                sig = re.sub(r"\s+", " ", trecho[:160].lower())
                if sig in seen:
                    continue
                seen.add(sig)
                hits.append(
                    {
                        "norma": norma,
                        "trecho": trecho,
                        "score": round(float(score), 4),
                        "source": meta.get("filename") or chunk.source,
                        "legal_source": legal_source,
                        "stamp_eligible": is_stamp_eligible(legal_source),
                    }
                )
    except Exception as exc:
        logger.warning("RAG desenho técnico indisponível: %s", exc)

    hits = hits[:top_k]
    licensed_hits = [h for h in hits if h.get("stamp_eligible")]
    excluded_hits = [h for h in hits if not h.get("stamp_eligible")]
    nbrs_cited = sorted({h["norma"] for h in licensed_hits if h.get("norma")})

    context_text = ""
    if licensed_hits:
        lines = [
            "CONTEXTO NORMATIVO — Desenho técnico / pranchas (NBR, PDF licenciado):",
            "Aplique escala, cotagem, carimbo e representação conforme trechos abaixo.",
        ]
        for h in licensed_hits:
            lines.append(f"[{h.get('norma')} | score={h.get('score')}]\n{h.get('trecho', '')[:700]}")
        context_text = "\n\n".join(lines)

    return {
        "rag_available": rag_available and bool(licensed_hits),
        "hits_count": len(licensed_hits),
        "hits_total": len(hits),
        "hits_excluded_unlicensed": len(excluded_hits),
        "legal_filter": "abnt_licensed_pdf_only",
        "legal_filter_notice": STAMP_LEGAL_FILTER_NOTICE,
        "bases_used": sorted(bases_used),
        "sources": licensed_hits,
        "sources_excluded": excluded_hits,
        "nbrs_cited": nbrs_cited,
        "context_text": context_text,
        "queries_used": list(queries),
        "expected_nbrs": DRAWING_NBR_CATALOG,
        "missing_priority_nbrs": _missing_priority_nbrs(nbrs_cited),
    }


def _norma_from_path(path: str) -> str | None:
    match = re.search(r"NBR[\s\-]?(\d{4,5})", path, re.I)
    return f"NBR {match.group(1)}" if match else None


def _missing_priority_nbrs(cited: list[str]) -> list[str]:
    """NBRs prioritárias ausentes nos hits (para orientar ingestão)."""
    priority = ("8196", "10067", "6492", "10126", "13142")
    cited_codes = {re.sub(r"\D", "", c) for c in cited}
    return [f"NBR {code} — {DRAWING_NBR_CATALOG[code]}" for code in priority if code not in cited_codes]


def refine_sheet_proposal_with_llm(
    proposal: dict[str, Any],
    normative: dict[str, Any],
) -> dict[str, Any]:
    """
    Refina escala/título/observações com LLM + contexto NBR (opcional).
    Falha silenciosa — retorna proposal original.
    """
    if not normative.get("rag_available"):
        return {**proposal, "llm_refined": False, "llm_note": "RAG normativo indisponível"}

    try:
        from core.workflow.llm.provider import get_default_llm

        llm = get_default_llm()
        prompt = f"""Com base nas NBRs de desenho técnico abaixo, sugira ajustes MÍNIMOS para esta prancha.
Responda APENAS JSON válido com keys: escala (ex 1:100), titulo (curto), observacao_normativa (1 frase).

Arquivo: {proposal.get('filename', '')}
Código proposto: {proposal.get('codigo_sugerido', '')}
Tipo: {proposal.get('tipo_desenho', '')}
Disciplina: {proposal.get('disciplina', '')}

{normative.get('context_text', '')[:3500]}
"""
        raw = llm.complete(
            prompt,
            system="Você é projetista sênior. Responda só JSON, sem markdown.",
        )
        import json

        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(raw[start:end])
            if data.get("escala"):
                proposal["escala"] = str(data["escala"])
            if data.get("titulo"):
                proposal["titulo"] = str(data["titulo"])[:300]
            proposal["observacao_normativa"] = str(data.get("observacao_normativa", ""))[:500]
            proposal["llm_refined"] = True
            return proposal
    except Exception as exc:
        logger.debug("LLM refine prancha skip: %s", exc)

    return {**proposal, "llm_refined": False}
