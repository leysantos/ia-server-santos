import re
from pathlib import Path
from typing import Optional

# Mapeamento NBR → disciplina (normas dos agentes do projeto)
NBR_DISCIPLINE_MAP: dict[str, str] = {
    "9050": "ARQUITETURA",
    "15575": "ARQUITETURA",
    "6118": "ESTRUTURAL",
    "8681": "ESTRUTURAL",
    "5626": "HIDROSSANITÁRIO",
    "8160": "HIDROSSANITÁRIO",
    "10844": "DRENAGEM",
    "9575": "DRENAGEM",
    "5410": "ELÉTRICA",
    "14039": "ELÉTRICA",
    "14567": "TELECOM",
    "17240": "INCÊNDIO",
    "10898": "INCÊNDIO",
    "9077": "INCÊNDIO",
    "6122": "GEOTECNIA",
    "7185": "GEOTECNIA",
    "7188": "TRANSPORTES",
    "7200": "TRANSPORTES",
    "9649": "SANEAMENTO",
    "9814": "SANEAMENTO",
    "13133": "TOPOGRAFIA",
    "14166": "TOPOGRAFIA",
}

NBR_PATTERN = re.compile(r"NBR[\s\-_]?(\d{4,5})", re.IGNORECASE)


def parse_nbr_code(filename: str) -> Optional[str]:
    """
    Extrai código NBR do nome do arquivo.
    Ex.: NBR-6118.pdf → 6118, nbr_8160.pdf → 8160
    """
    match = NBR_PATTERN.search(filename)
    if match:
        return match.group(1)

    stem_match = re.search(r"(?<![\d.])(\d{4,5})(?![\d.])", Path(filename).stem)
    if stem_match:
        return stem_match.group(1)

    return None


def infer_discipline(nbr_code: Optional[str]) -> str:
    if not nbr_code:
        return ""
    return NBR_DISCIPLINE_MAP.get(nbr_code, "")


def nbr_label(nbr_code: Optional[str]) -> str:
    if not nbr_code:
        return ""
    return f"NBR {nbr_code}"
