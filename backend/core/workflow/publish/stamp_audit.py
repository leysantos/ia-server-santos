"""Metadados de auditoria IA/normas para o carimbo da prancha."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.knowledge.norm_packs.legal import STAMP_LEGAL_FILTER_NOTICE, is_stamp_eligible


def _licensed_nbrs_from_normative(normative: dict[str, Any]) -> list[str]:
    """NBRs elegíveis para o carimbo — somente PDF licenciado."""
    cited = normative.get("nbrs_cited") or []
    if cited:
        return sorted({str(n) for n in cited})

    seen: set[str] = set()
    for src in normative.get("sources") or []:
        if not isinstance(src, dict):
            continue
        if not src.get("stamp_eligible") and not is_stamp_eligible(src.get("legal_source")):
            continue
        if src.get("norma"):
            seen.add(str(src["norma"]))
    return sorted(seen)


def build_stamp_audit(
    *,
    analysis_json: dict[str, Any] | None = None,
    pipeline: str = "workflow_wizard",
    ai_model: str | None = None,
) -> dict[str, Any]:
    """Monta bloco de rastreabilidade exibido no carimbo."""
    from config.settings import get_settings

    settings = get_settings()
    analysis = analysis_json or {}
    model = ai_model or analysis.get("ai_model") or settings.ollama_chat_model
    normative = analysis.get("normative_rag") if isinstance(analysis.get("normative_rag"), dict) else {}

    nbrs = _licensed_nbrs_from_normative(normative)
    excluded = int(normative.get("hits_excluded_unlicensed") or 0)

    return {
        "generated_by": "IA Server Santos — Workflow Projetos",
        "pipeline": pipeline,
        "ai_model": model,
        "llm_refined": bool(analysis.get("llm_refined")),
        "rag_available": bool(normative.get("rag_available")),
        "rag_hits": int(normative.get("hits_count") or 0),
        "rag_hits_total": int(normative.get("hits_total") or normative.get("hits_count") or 0),
        "nbrs_consultadas": nbrs,
        "nbrs_excluded_unlicensed": excluded,
        "legal_filter": normative.get("legal_filter") or "abnt_licensed_pdf_only",
        "legal_filter_notice": normative.get("legal_filter_notice") or STAMP_LEGAL_FILTER_NOTICE,
        "observacao_normativa": str(analysis.get("observacao_normativa") or "")[:200],
        "generated_at": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
    }


def format_stamp_audit_lines(audit: dict[str, Any]) -> list[str]:
    """Linhas compactas para desenho no carimbo."""
    lines = [
        f"IA: {audit.get('ai_model', '—')}",
        f"Pipeline: {audit.get('pipeline', '—')}",
    ]
    nbrs = audit.get("nbrs_consultadas") or []
    if nbrs:
        nbr_text = ", ".join(str(n) for n in nbrs[:4])
        if len(nbrs) > 4:
            nbr_text += f" +{len(nbrs) - 4}"
        lines.append(f"NBRs (PDF lic.): {nbr_text}")
    elif audit.get("rag_available") is False:
        lines.append("NBRs: (sem PDF licenciado indexado)")
    else:
        lines.append("NBRs: —")

    rag_hits = audit.get("rag_hits", 0)
    excluded = audit.get("nbrs_excluded_unlicensed", 0)
    refined = "sim" if audit.get("llm_refined") else "não"
    rag_line = f"RAG: {rag_hits} trecho(s) lic."
    if excluded:
        rag_line += f" · {excluded} excl."
    rag_line += f" · LLM: {refined}"
    lines.append(rag_line)
    lines.append(f"Gerado: {audit.get('generated_at', '—')}")
    obs = audit.get("observacao_normativa")
    if obs:
        lines.append(f"Norma: {obs[:80]}")
    return lines
