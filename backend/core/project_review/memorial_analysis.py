"""Análise de memorial vs projeto (Módulo K)."""

from __future__ import annotations

import re
from typing import Any


def analyze_memorial(
    extraction_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compara memorial descritivo com elementos projetados."""
    memorial_text = ""
    projeto_text = ""

    for item in extraction_items:
        name = (item.get("filename") or "").lower()
        ext = item.get("extraction_json") or {}
        text = ext.get("texto") or ""
        disc = (item.get("discipline") or "").lower()

        if "memorial" in name or disc == "documentacao":
            memorial_text += "\n" + text
        else:
            projeto_text += "\n" + text
            for el in ext.get("elementos_detectados") or []:
                projeto_text += "\n" + str(el)

    report = {
        "descritos_nao_projetados": [],
        "projetados_nao_descritos": [],
        "divergencias_tecnicas": [],
        "divergencias_quantitativos": [],
        "divergencias_normativas": [],
    }

    if not memorial_text.strip():
        report["divergencias_tecnicas"].append("Memorial descritivo não identificado no acervo")
        return report

    memorial_terms = _extract_terms(memorial_text)
    projeto_terms = _extract_terms(projeto_text)

    for term in memorial_terms:
        if term not in projeto_terms:
            report["descritos_nao_projetados"].append(term)

    for term in projeto_terms:
        if term not in memorial_terms:
            report["projetados_nao_descritos"].append(term)

    mem_qty = re.findall(r"(\d+[,.]?\d*)\s*(m²|m2|m³|m3|un)", memorial_text, re.I)
    proj_qty = re.findall(r"(\d+[,.]?\d*)\s*(m²|m2|m³|m3|un)", projeto_text, re.I)
    if mem_qty and proj_qty and mem_qty != proj_qty[: len(mem_qty)]:
        report["divergencias_quantitativos"].append(
            {"memorial": mem_qty[:5], "projeto": proj_qty[:5]}
        )

    return report


def _extract_terms(text: str) -> set[str]:
    keywords = re.findall(
        r"\b(viga|pilar|laje|sapata|escada|porta|janela|hidrante|extintor|"
        r"tubulação|eletroduto|concreto|aço|alvenaria)\b",
        text.lower(),
    )
    return set(keywords)
