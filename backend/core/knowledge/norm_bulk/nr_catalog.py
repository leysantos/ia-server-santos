"""Catálogo NR (Normas Regulamentadoras) — código → disciplina."""

from __future__ import annotations

import re
from typing import Optional

NR_PATTERN = re.compile(
    r"NR[\s\-_]?(\d{1,2})|norma[\s\-_]?regulamentadora[\s\-_]?(\d{1,2})",
    re.IGNORECASE,
)

# NR → disciplina de engenharia (alinhado aos agentes do projeto)
NR_DISCIPLINE_MAP: dict[str, str] = {
    "4": "SEGURANCA",
    "5": "SEGURANCA",
    "6": "SEGURANCA",
    "7": "SEGURANCA",
    "8": "SEGURANCA",
    "9": "SEGURANCA",
    "10": "ELÉTRICA",
    "11": "TRANSPORTES",
    "12": "SEGURANCA",
    "13": "HIDROSSANITÁRIO",
    "15": "SEGURANCA",
    "16": "SEGURANCA",
    "17": "GERAL",
    "18": "GERAL",
    "19": "SEGURANCA",
    "20": "SEGURANCA",
    "22": "SEGURANCA",
    "23": "SEGURANCA",
    "24": "SEGURANCA",
    "26": "SEGURANCA",
    "28": "SEGURANCA",
    "29": "SEGURANCA",
    "30": "SEGURANCA",
    "31": "SEGURANCA",
    "32": "SEGURANCA",
    "33": "SEGURANCA",
    "34": "SEGURANCA",
    "35": "SEGURANCA",
    "36": "SEGURANCA",
    "37": "SEGURANCA",
    "38": "SEGURANCA",
}


def parse_nr_code(text: str) -> Optional[str]:
    """Extrai número da NR de filename ou trecho de texto."""
    match = NR_PATTERN.search(text)
    if not match:
        return None
    code = match.group(1) or match.group(2)
    return code.lstrip("0") or "0"


def infer_nr_discipline(nr_code: Optional[str]) -> str:
    if not nr_code:
        return ""
    return NR_DISCIPLINE_MAP.get(nr_code, "SEGURANCA")


def nr_label(nr_code: Optional[str]) -> str:
    if not nr_code:
        return ""
    return f"NR-{nr_code}"
