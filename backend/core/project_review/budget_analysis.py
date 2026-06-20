"""Análise orçamentária cruzada (Módulo J)."""

from __future__ import annotations

import re
from typing import Any


def analyze_budget(
    *,
    twin_payload: dict[str, Any],
    extraction_items: list[dict[str, Any]],
    budget_session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Cruza planilha, projeto e memorial — score e achados."""
    orcamento_texts: list[str] = []
    projeto_elements: list[str] = []
    memorial_texts: list[str] = []

    for item in extraction_items:
        disc = (item.get("discipline") or "").lower()
        ext = item.get("extraction_json") or {}
        text = ext.get("texto") or ""
        if disc == "orcamento" or item.get("format_key") in ("xlsx", "xls", "csv"):
            orcamento_texts.append(text)
        elif disc == "documentacao" or "memorial" in (item.get("filename") or "").lower():
            memorial_texts.append(text)
        else:
            for el in ext.get("elementos_detectados") or []:
                if isinstance(el, dict):
                    projeto_elements.append(str(el.get("tipo") or el))

    report: dict[str, Any] = {
        "itens_faltantes": [],
        "itens_duplicados": [],
        "quantitativos_incompativeis": [],
        "servicos_ausentes": [],
        "servicos_excedentes": [],
        "composicoes_incorretas": [],
        "bdi_inconsistente": False,
        "encargos_inconsistentes": False,
        "score": 100.0,
    }

    combined_orc = "\n".join(orcamento_texts)
    if budget_session:
        items = budget_session.get("items") or budget_session.get("composicoes") or []
        for it in items[:500]:
            desc = str(it.get("description") or it.get("descricao") or "")
            if desc and desc.lower() not in combined_orc.lower():
                report["itens_faltantes"].append(desc[:120])

    for el in projeto_elements:
        if el and el.lower() not in combined_orc.lower() and combined_orc:
            report["servicos_ausentes"].append(el)

    dupes = _find_duplicate_lines(combined_orc)
    report["itens_duplicados"] = dupes[:20]

    bdi_values = re.findall(r"BDI\s*[=:]?\s*([\d,.]+)\s*%?", combined_orc, re.I)
    if len(set(bdi_values)) > 1:
        report["bdi_inconsistente"] = True

    penalty = (
        len(report["itens_faltantes"]) * 3
        + len(report["servicos_ausentes"]) * 2
        + len(report["itens_duplicados"]) * 2
        + (10 if report["bdi_inconsistente"] else 0)
    )
    report["score"] = max(0.0, min(100.0, 100.0 - penalty))
    return report


def _find_duplicate_lines(text: str) -> list[str]:
    lines = [ln.strip() for ln in text.splitlines() if len(ln.strip()) > 10]
    seen: dict[str, int] = {}
    for ln in lines:
        seen[ln] = seen.get(ln, 0) + 1
    return [ln for ln, count in seen.items() if count > 1]
