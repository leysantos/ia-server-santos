"""
Tipos de conteúdo — metadata (sidecar JSON), não subpastas.

Filesystem: knowledge/raw/documents/arquivo.pdf
Sidecar:    knowledge/raw/documents/arquivo.pdf.knowledge.json
"""

from __future__ import annotations

KNOWLEDGE_CONTENT_TYPES: tuple[str, ...] = (
    "nbrs",
    "sinapi",
    "tcpo",
    "tdrs",
    "catalogos",
    "manuais",
    "projetos",
    "regional",
    "modelos_orcamento",
)

CONTENT_TYPE_ALIASES: dict[str, str] = {
    "nbr": "nbrs",
    "cost": "sinapi",
    "composition": "tcpo",
    "tdr": "tdrs",
    "catalog": "catalogos",
    "catalogo": "catalogos",
    "manual": "manuais",
    "project": "projetos",
    "projeto": "projetos",
    "regional": "regional",
    "modelo_orcamento": "modelos_orcamento",
    "modelos_orcamento": "modelos_orcamento",
    "ppd_modelo": "modelos_orcamento",
    "wbs": "modelos_orcamento",
}

BASE_KEY_TO_CONTENT_TYPE: dict[str, str] = {
    "nbr": "nbrs",
    "sinapi": "sinapi",
    "tcpo": "tcpo",
    "tdr": "tdrs",
    "catalogos": "catalogos",
    "regional": "regional",
    "budget_models": "modelos_orcamento",
}

# Quais tipos (metadata) alimentam cada índice FAISS
BASE_KEY_ACCEPTS_CONTENT_TYPES: dict[str, frozenset[str]] = {
    "nbr": frozenset({"nbrs"}),
    "sinapi": frozenset({"sinapi"}),
    "tcpo": frozenset({"tcpo"}),
    "tdr": frozenset({"tdrs", "projetos"}),
    "catalogos": frozenset({"catalogos", "manuais"}),
    "regional": frozenset({"regional"}),
    "budget_models": frozenset({"modelos_orcamento"}),
}

CONTENT_TYPE_TO_BASE_KEY: dict[str, str] = {
    ct: base
    for base, types in BASE_KEY_ACCEPTS_CONTENT_TYPES.items()
    for ct in types
}

# Path primário por tipo (discipline, layer) — sem subpasta de tipo
KB_SUBDIR_TO_PRIMARY_PATH: dict[str, tuple[str, str]] = {
    "nbrs": ("estruturas", "raw"),
    "sinapi": ("orcamento", "raw"),
    "tcpo": ("orcamento", "raw"),
    "tdrs": ("geral", "raw"),
    "projetos": ("geral", "raw"),
    "manuais": ("geral", "canonical"),
    "catalogos": ("arquitetura", "raw"),
    "regional": ("meio_ambiente", "raw"),
    "modelos_orcamento": ("orcamento", "raw"),
}

# Compat legado (migrate scripts)
KB_SUBDIR_TO_DISCIPLINE_PATH: dict[str, tuple[str, str, str]] = {
    subdir: (*path, subdir)
    for subdir, path in KB_SUBDIR_TO_PRIMARY_PATH.items()
}

DISCIPLINE_DEFAULT_CONTENT_TYPE: dict[str, str] = {
    "estruturas": "nbrs",
    "geotecnia": "nbrs",
    "eletrica": "nbrs",
    "telecom": "nbrs",
    "hidrossanitario": "nbrs",
    "saneamento": "nbrs",
    "drenagem": "nbrs",
    "incendio": "nbrs",
    "transportes": "nbrs",
    "infraestrutura": "nbrs",
    "arquitetura": "catalogos",
    "orcamento": "sinapi",
    "geoprocessamento": "projetos",
    "topografia": "projetos",
    "meio_ambiente": "regional",
    "geral": "tdrs",
}


def normalize_content_type(raw: str) -> str:
    key = (raw or "").strip().lower()
    if key in KNOWLEDGE_CONTENT_TYPES:
        return key
    if key in CONTENT_TYPE_ALIASES:
        return CONTENT_TYPE_ALIASES[key]
    raise KeyError(
        f"Tipo de conteúdo desconhecido: {raw}. "
        f"Use: {', '.join(KNOWLEDGE_CONTENT_TYPES)}"
    )


def infer_content_type_from_filename(filename: str) -> str | None:
    name = filename.lower()
    if parse_nbr_hint(name):
        return "nbrs"
    if any(k in name for k in ("sinapi", "sicro")):
        return "sinapi"
    if "tcpo" in name:
        return "tcpo"
    if any(k in name for k in ("tdr", "termo_de_referencia", "memorial")):
        return "tdrs"
    if any(k in name for k in ("catalogo", "catalog", "fabricante")):
        return "catalogos"
    if "manual" in name:
        return "manuais"
    if any(k in name for k in ("projeto", "planta", "dwg")):
        return "projetos"
    if any(k in name for k in ("regional", "manaus", "amazonas")):
        return "regional"
    if any(k in name for k in ("ppd", "modelo_orc", "modelo orc", "wbs orc")):
        return "modelos_orcamento"
    return None


def parse_nbr_hint(name: str) -> bool:
    from memory.nbr_catalog import parse_nbr_code

    return parse_nbr_code(name) is not None


def default_content_type_for_discipline(slug: str) -> str:
    return DISCIPLINE_DEFAULT_CONTENT_TYPE.get(slug, "tdrs")
