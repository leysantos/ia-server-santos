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
    # Desenho técnico / documentação de projetos
    "10067": "DOCUMENTACAO",
    "8196": "DOCUMENTACAO",
    "10126": "DOCUMENTACAO",
    "13142": "DOCUMENTACAO",
    "6492": "ARQUITETURA",
    "9441": "ARQUITETURA",
    "7191": "ESTRUTURAL",
    "5261": "ELÉTRICA",
    "8809": "DOCUMENTACAO",
    "13531": "DOCUMENTACAO",
    "10520": "DOCUMENTACAO",
}

NBR_PATTERN = re.compile(r"NBR[\s\-_]?(\d{4,5})", re.IGNORECASE)
NR_PATTERN = re.compile(r"\bNR[\s\-_]?(\d{1,3})\b", re.IGNORECASE)
EB_PATTERN = re.compile(r"\bEB[\s\-_]?(\d{3,5})\b", re.IGNORECASE)


def parse_nbr_code(filename: str) -> Optional[str]:
    """
    Extrai código NBR do nome do arquivo.
    Ex.: NBR-6118.pdf → 6118, nbr_8160.pdf → 8160
    """
    match = NBR_PATTERN.search(filename)
    if match:
        return normalize_nbr_code(match.group(1))

    nr_match = NR_PATTERN.search(filename)
    if nr_match:
        return f"NR-{nr_match.group(1)}"

    eb_match = EB_PATTERN.search(filename)
    if eb_match:
        return f"EB-{eb_match.group(1)}"

    stem_match = re.search(r"(?<![\d.])(\d{4,5})(?![\d.])", Path(filename).stem)
    if stem_match:
        return normalize_nbr_code(stem_match.group(1))

    return None


def normalize_nbr_code(code: Optional[str]) -> Optional[str]:
    """Forma canônica para comparação e metadata (6118, não 06118)."""
    if not code:
        return None
    text = str(code).strip()
    upper = text.upper()
    if upper.startswith("NR-"):
        num = upper[3:].lstrip("0") or "0"
        return f"NR-{num}"
    if upper.startswith("EB-"):
        return upper
    if text.isdigit():
        return text.lstrip("0") or "0"
    return text


def nbr_codes_match(a: Optional[str], b: Optional[str]) -> bool:
    na, nb = normalize_nbr_code(a), normalize_nbr_code(b)
    return bool(na and nb and na == nb)


def resolve_norm_code(filename: str, meta: dict | None = None) -> Optional[str]:
    """Código normativo unificado: sidecar → parse do filename."""
    meta = meta or {}
    kind = str(meta.get("norm_kind") or "").upper()
    sidecar_code = meta.get("nbr_code") or meta.get("norm_code")
    if sidecar_code:
        code = str(sidecar_code).strip()
        if kind == "NR" and not code.upper().startswith("NR"):
            return normalize_nbr_code(f"NR-{code.lstrip('0') or code}")
        return normalize_nbr_code(code)
    return parse_nbr_code(filename)


def infer_discipline(nbr_code: Optional[str]) -> str:
    if not nbr_code:
        return ""
    return NBR_DISCIPLINE_MAP.get(nbr_code, "")


def nbr_label(nbr_code: Optional[str]) -> str:
    if not nbr_code:
        return ""
    return f"NBR {nbr_code}"
