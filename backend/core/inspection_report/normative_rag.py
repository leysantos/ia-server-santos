"""L15 — RAG normativo por tipología + citações rastreáveis (laudos).

Recupera trechos NBR via ``retrieve_for_agent``, persiste
``content.normative_citations`` e monta o capítulo Referências tipado.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# NBRs prioritárias por tipología (códigos sem "NBR ")
TYPOLOGY_PRIORITY_NBRS: dict[str, tuple[str, ...]] = {
    "pontes": ("9452", "7187", "6118"),
    "viadutos": ("9452", "7187", "6118"),
    "edificacao": ("6118", "15575", "9575", "13755"),
    "erosao": ("11682",),
    "barragem": ("11682",),
    "drenagem": ("9649", "12266"),
    "pavimentacao": ("7181",),
    "muro_contencao": ("11682", "6122"),
    "geral": ("6118", "9452"),
}

_TYPOLOGY_RAG_QUERIES: dict[str, tuple[str, ...]] = {
    "pontes": (
        "NBR 9452 inspeção OAE pontes classificação anomalias",
        "DNIT 010/2004-PRO inspeção especial pontes viadutos",
        "NBR 7187 projeto de pontes de concreto armado e protendido",
        "NBR 6118 projeto estruturas concreto armado patologias",
    ),
    "viadutos": (
        "NBR 9452 inspeção OAE viadutos classificação",
        "NBR 7187 pontes concreto armado",
        "NBR 6118 concreto armado fissuração durabilidade",
    ),
    "edificacao": (
        "NBR 6118 concreto armado patologia fissuras",
        "NBR 15575 desempenho edificações habitacionais",
        "NBR 9575 impermeabilização sistemas",
        "NBR 13755 revestimento cerâmico fachadas",
    ),
    "erosao": (
        "NBR 11682 estabilidade de taludes erosão",
        "erosão superficial proteção taludes drenagem",
    ),
    "barragem": (
        "segurança de barragens inspeção instrumentação",
        "NBR 11682 estabilidade taludes barragem",
    ),
    "drenagem": (
        "drenagem urbana galerias inspeção patologias",
        "NBR 9649 tubo concreto drenagem",
    ),
    "pavimentacao": (
        "pavimentação flexível patologias DNIT inspeção",
        "NBR 7181 solo compactação pavimento",
    ),
    "muro_contencao": (
        "NBR 11682 muro de contenção estabilidade",
        "NBR 6122 fundações contenção",
    ),
    "geral": (
        "laudo vistoria engenharia civil patologias NBR",
        "NBR 6118 concreto armado inspeção",
        "NBR 9452 inspeção obras de arte especiais",
    ),
}

_AGENT_BY_SLUG: dict[str, str] = {
    "pontes": "infraestrutura",
    "viadutos": "infraestrutura",
    "edificacao": "estruturas",
    "erosao": "geotecnia",
    "barragem": "geotecnia",
    "drenagem": "drenagem",
    "pavimentacao": "transportes",
    "muro_contencao": "geotecnia",
    "geral": "estruturas",
}

_DISCIPLINE_TO_AGENT: dict[str, str] = {
    "INFRAESTRUTURA": "infraestrutura",
    "ESTRUTURAL": "estruturas",
    "GEOTECNIA": "geotecnia",
    "DRENAGEM": "drenagem",
    "TRANSPORTES": "transportes",
    "HIDRAULICA": "hidraulica",
    "ARQUITETURA": "arquitetura",
}


def slug_to_agent(slug: str | None, discipline_hint: str | None = None) -> str:
    s = (slug or "geral").strip().lower()
    if s in _AGENT_BY_SLUG:
        return _AGENT_BY_SLUG[s]
    disc = (discipline_hint or "").strip().upper()
    return _DISCIPLINE_TO_AGENT.get(disc, "estruturas")


def normative_prompt_block() -> str:
    """Instrução L15 para o Gemini — citar só normas do contexto RAG."""
    return (
        "L15 — CITAÇÕES NORMATIVAS RASTREÁVEIS:\n"
        "- Prefira citar normas e trechos presentes no CONTEXTO DA BASE DE CONHECIMENTO (RAG).\n"
        "- Em `references`, use o código da norma (ex.: NBR 9452) e, se possível, "
        "o tema do trecho recuperado — não invente cláusulas inexistentes.\n"
        "- Quando não houver contexto RAG, cite apenas normas amplamente aplicáveis "
        "à tipología, sem inventar numeração de itens."
    )


def retrieve_laudo_normative_context(
    *,
    slug: str | None = None,
    query: str = "",
    discipline_hint: str | None = None,
    top_k: int = 10,
) -> dict[str, Any]:
    """
    Busca trechos NBR alinhados à tipología do laudo.
    Retorna hits tipados + ``context_text`` para o prompt Gemini.
    """
    s = (slug or "geral").strip().lower() or "geral"
    queries = _TYPOLOGY_RAG_QUERIES.get(s, _TYPOLOGY_RAG_QUERIES["geral"])
    agent = slug_to_agent(s, discipline_hint)
    seed = (query or "").strip()[:160]

    hits: list[dict[str, Any]] = []
    bases_used: set[str] = set()
    rag_available = False
    seen: set[str] = set()

    try:
        from core.knowledge.rag.agent_retriever import retrieve_for_agent
        from core.knowledge.norm_packs.legal import resolve_legal_source, is_stamp_eligible

        per_query = max(2, top_k // max(1, len(queries)) + 1)
        for qbase in queries:
            q = f"{qbase} {seed}".strip()
            result = retrieve_for_agent(
                q,
                agent_slug=agent,
                discipline_hint=(discipline_hint or None),
                top_k=per_query,
            )
            if result.hits:
                rag_available = True
            for base in result.bases_used:
                bases_used.add(str(base))
            for chunk, score in result.hits:
                meta = chunk.metadata or {}
                file_ref = meta.get("path") or meta.get("filename") or chunk.source or ""
                try:
                    legal_source = resolve_legal_source(
                        meta,
                        file_path=str(file_ref) if file_ref else None,
                        doc_type=chunk.doc_type,
                    ).value
                except Exception:
                    legal_source = "unknown"
                norma = (
                    meta.get("norma")
                    or meta.get("nbr_code")
                    or _norma_from_text(meta.get("filename") or meta.get("path") or "")
                    or _norma_from_text(chunk.text or "")
                    or chunk.source
                    or "NBR"
                )
                clause = str(
                    meta.get("section")
                    or meta.get("clause")
                    or meta.get("item")
                    or ""
                ).strip()
                trecho = re.sub(r"\s+", " ", (chunk.text or "").strip())[:900]
                sig = trecho[:160].lower()
                if not trecho or sig in seen:
                    continue
                seen.add(sig)
                hits.append(
                    {
                        "norma": str(norma).strip(),
                        "clause": clause,
                        "excerpt": trecho,
                        "score": round(float(score), 4),
                        "source": meta.get("filename") or chunk.source or "",
                        "legal_source": legal_source,
                        "stamp_eligible": bool(is_stamp_eligible(legal_source)),
                        "query": qbase,
                    }
                )
    except Exception as exc:
        logger.warning("L15 RAG laudo indisponível: %s", exc)

    hits.sort(key=lambda h: (-int(bool(h.get("stamp_eligible"))), -float(h.get("score") or 0)))
    hits = hits[:top_k]

    licensed = [h for h in hits if h.get("stamp_eligible")]
    for_context = licensed or hits
    nbrs_cited = sorted({h["norma"] for h in for_context if h.get("norma")})

    context_text = ""
    if for_context:
        lines = [
            "CONTEXTO NORMATIVO L15 — Laudo de vistoria (NBR por tipología):",
            f"Tipología: {s} · agente RAG: {agent}",
            "Cite preferencialmente as normas e trechos abaixo (rastreáveis).",
        ]
        for h in for_context:
            clause = f" · item {h['clause']}" if h.get("clause") else ""
            lines.append(
                f"[{h.get('norma')}{clause} | score={h.get('score')} | fonte={h.get('source')}]\n"
                f"{h.get('excerpt', '')[:700]}"
            )
        context_text = "\n\n".join(lines)

    priority = TYPOLOGY_PRIORITY_NBRS.get(s, TYPOLOGY_PRIORITY_NBRS["geral"])
    cited_codes = {_nbr_code(n) for n in nbrs_cited}
    missing = [f"NBR {c}" for c in priority if c not in cited_codes]

    return {
        "rag_available": rag_available and bool(hits),
        "hits_count": len(hits),
        "bases_used": sorted(bases_used),
        "citations": hits,
        "nbrs_cited": nbrs_cited,
        "missing_priority_nbrs": missing,
        "context_text": context_text,
        "queries_used": list(queries),
        "agent_slug": agent,
        "typology_slug": s,
    }


def apply_normative_citations(
    content: dict[str, Any],
    *,
    normative: dict[str, Any] | None = None,
    slug: str | None = None,
) -> dict[str, Any]:
    """
    Persiste ``normative_citations`` e upsert do capítulo ``referencias`` (tabela).
    Se ``normative`` for None, reutiliza citations já no content.
    """
    out = dict(content or {})
    citations: list[dict[str, Any]] = []

    if isinstance(normative, dict) and normative.get("citations"):
        citations = [c for c in normative["citations"] if isinstance(c, dict)]
    elif isinstance(out.get("normative_citations"), list):
        citations = [c for c in out["normative_citations"] if isinstance(c, dict)]

    if citations:
        out["normative_citations"] = citations
        # Compat: lista de strings para Gemini / fallback export
        ref_strings: list[str] = []
        for c in citations:
            norma = str(c.get("norma") or "NBR").strip()
            clause = str(c.get("clause") or "").strip()
            src = str(c.get("source") or "").strip()
            excerpt = str(c.get("excerpt") or "").strip()
            bit = norma
            if clause:
                bit += f" — {clause}"
            if excerpt:
                bit += f": {excerpt[:180]}{'…' if len(excerpt) > 180 else ''}"
            if src:
                bit += f" (fonte: {src})"
            ref_strings.append(bit)
        existing = [str(r) for r in (out.get("references") or []) if str(r).strip()]
        # prioriza rastreáveis; mantém refs Gemini que não duplicam código
        codes = {_nbr_code(c.get("norma")) for c in citations}
        extras = [r for r in existing if _nbr_code(r) not in codes or not _nbr_code(r)]
        out["references"] = ref_strings + extras
        if isinstance(normative, dict):
            out["normative_rag"] = {
                "rag_available": bool(normative.get("rag_available")),
                "hits_count": len(citations),
                "bases_used": list(normative.get("bases_used") or []),
                "nbrs_cited": list(normative.get("nbrs_cited") or []),
                "missing_priority_nbrs": list(normative.get("missing_priority_nbrs") or []),
                "agent_slug": normative.get("agent_slug"),
                "typology_slug": normative.get("typology_slug") or slug,
            }

    out = _inject_referencias_chapter(out, citations)
    return out


def normative_citations_table(citations: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[list[str]] = []
    for c in citations:
        if not isinstance(c, dict):
            continue
        norma = str(c.get("norma") or "—")
        clause = str(c.get("clause") or "—") or "—"
        excerpt = str(c.get("excerpt") or "—")
        if len(excerpt) > 220:
            excerpt = excerpt[:217] + "…"
        src = str(c.get("source") or "—")
        score = c.get("score")
        score_s = f"{float(score):.2f}" if score is not None else "—"
        rows.append([norma, clause, excerpt, src, score_s])
    if not rows:
        rows = [["—", "—", "Sem trechos RAG recuperados para a tipología.", "—", "—"]]
    return {
        "caption": "Citações normativas rastreáveis (L15 — RAG por tipología)",
        "headers": ["Norma", "Item/cláusula", "Trecho", "Fonte", "Score"],
        "rows": rows,
    }


def _inject_referencias_chapter(
    content: dict[str, Any],
    citations: list[dict[str, Any]],
) -> dict[str, Any]:
    out = dict(content)
    chapters = list(out.get("chapters") or [])
    by_id = {
        str(c.get("id") or "").lower(): i
        for i, c in enumerate(chapters)
        if isinstance(c, dict)
    }

    paras: list[str] = []
    tables: list[dict[str, Any]] = []
    meta = out.get("normative_rag") if isinstance(out.get("normative_rag"), dict) else {}

    if citations:
        paras.append(
            "Referências normativas recuperadas da base de conhecimento (RAG) "
            "alinhadas à tipología do laudo, com trecho e fonte para rastreabilidade."
        )
        if meta.get("missing_priority_nbrs"):
            paras.append(
                "NBRs prioritárias da tipología ainda ausentes no índice FAISS: "
                + ", ".join(str(x) for x in meta["missing_priority_nbrs"])
                + "."
            )
        tables.append(normative_citations_table(citations))
    else:
        refs = [str(r) for r in (out.get("references") or []) if str(r).strip()]
        if not refs:
            return out
        paras = ["Referências normativas citadas no laudo."] + refs
        # mantém como parágrafos se não há tabela L15

    payload = {
        "id": "referencias",
        "title": "Referências",
        "paragraphs": paras,
        "tables": tables,
    }
    if "referencias" in by_id:
        # preserva parágrafos Gemini extras se já havia capítulo sem tabela L15
        old = chapters[by_id["referencias"]]
        if isinstance(old, dict) and not citations:
            return out
        chapters[by_id["referencias"]] = payload
    else:
        chapters.append(payload)

    out["chapters"] = chapters
    return out


def _norma_from_text(text: str) -> str | None:
    match = re.search(r"NBR[\s\-]?(\d{4,5})", text or "", re.I)
    return f"NBR {match.group(1)}" if match else None


def _nbr_code(value: Any) -> str:
    m = re.search(r"(\d{4,5})", str(value or ""))
    return m.group(1) if m else ""
