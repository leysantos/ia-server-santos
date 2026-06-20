"""Detecção automática de disciplina por nome de arquivo e conteúdo."""

from __future__ import annotations

import re
from pathlib import Path

from core.project_review.constants import Discipline

_DISCIPLINE_PATTERNS: list[tuple[Discipline, re.Pattern[str]]] = [
    (Discipline.ESTRUTURA, re.compile(r"\b(est|estrut|fund|viga|pilar|laje|sapata|armad)\b", re.I)),
    (Discipline.ARQUITETURA, re.compile(r"\b(arq|arquit|planta|fachada|corte|implant)\b", re.I)),
    (Discipline.HIDRAULICA, re.compile(r"\b(hid|hidra|sanit|esgoto|agua|pluvial|hss)\b", re.I)),
    (Discipline.ELETRICA, re.compile(r"\b(ele|elet|lumin|forca|cabos|quadro)\b", re.I)),
    (Discipline.PCI, re.compile(r"\b(pci|incendio|cbm|sprinkler|extintor|fogo)\b", re.I)),
    (Discipline.URBANISMO, re.compile(r"\b(urb|loteam|viario|paisag)\b", re.I)),
    (Discipline.INFRAESTRUTURA, re.compile(r"\b(infra|pav|dren|terrap|ponte|viaduto)\b", re.I)),
    (Discipline.ORCAMENTO, re.compile(r"\b(orc|planilha|sinapi|sicro|bd[ií]|compos)\b", re.I)),
    (Discipline.DOCUMENTACAO, re.compile(r"\b(memorial|especific|tdr|termo|relatorio|parecer)\b", re.I)),
]

_EXT_HINTS: dict[str, Discipline] = {
    ".ifc": Discipline.ESTRUTURA,
    ".dxf": Discipline.ARQUITETURA,
    ".dwg": Discipline.ARQUITETURA,
}


def detect_discipline(
    filename: str,
    text_sample: str = "",
    format_key: str = "",
) -> str:
    """Retorna chave de disciplina (Discipline value)."""
    name = Path(filename).stem
    combined = f"{name} {text_sample[:4000]}".lower()

    for discipline, pattern in _DISCIPLINE_PATTERNS:
        if pattern.search(combined):
            return discipline.value

    ext = Path(filename).suffix.lower()
    if ext in _EXT_HINTS:
        return _EXT_HINTS[ext].value

    if format_key in ("xlsx", "xls", "csv"):
        return Discipline.ORCAMENTO.value
    if format_key in ("docx", "rtf"):
        return Discipline.DOCUMENTACAO.value

    return Discipline.DESCONHECIDA.value
