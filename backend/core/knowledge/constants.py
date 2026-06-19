"""
Knowledge Layer — bases técnicas imutáveis (NBR, SINAPI, TCPO, TDR, catálogos).

Storage: backend/knowledge/raw/documents/ (disciplina/tipo → metadata sidecar)
"""

from __future__ import annotations

from config.settings import FAISS_INDEX_DIR, KNOWLEDGE_DIR
from core.knowledge.resolver import canonical_base_paths, get_legacy_read_paths

KNOWLEDGE_PATHS = canonical_base_paths()

LEGACY_SOURCE_PATHS: dict[str, list] = {
    base: get_legacy_read_paths(base) for base in KNOWLEDGE_PATHS
}

KNOWLEDGE_INDEX_NAMES: dict[str, str] = {
    "nbr": "nbr_index",
    "sinapi": "cost_index",
    "tcpo": "composition_index",
    "tdr": "tdr_index",
    "catalogos": "catalog_index",
    "regional": "regional_index",
    "budget_models": "budget_models_index",
}

KNOWLEDGE_INDEX_DIR = FAISS_INDEX_DIR / "knowledge"

# doc_type gravado nos chunks FAISS (≠ content_type do metadata sidecar)
BASE_DOC_TYPES: dict[str, str] = {
    "nbr": "nbr",
    "sinapi": "cost",
    "tcpo": "composition",
    "tdr": "tdr",
    "catalogos": "catalog",
    "regional": "regional",
    "budget_models": "budget_model",
}

DOMAIN_STRUCTURAL = "structural"
DOMAIN_COST = "cost"
DOMAIN_BUDGET = "budget"
DOMAIN_NORM = "norm"
DOMAIN_GEOTECHNICAL = "geotechnical"
DOMAIN_HYDRAULIC = "hydraulic"
DOMAIN_ELECTRICAL = "electrical"
DOMAIN_CATALOG = "catalog"
DOMAIN_GENERAL = "general"

DOMAIN_TO_BASES: dict[str, list[str]] = {
    DOMAIN_STRUCTURAL: ["nbr"],
    DOMAIN_COST: ["sinapi"],
    DOMAIN_BUDGET: ["sinapi", "tcpo"],
    DOMAIN_NORM: ["nbr"],
    DOMAIN_GEOTECHNICAL: ["nbr", "catalogos"],
    DOMAIN_HYDRAULIC: ["nbr"],
    DOMAIN_ELECTRICAL: ["nbr"],
    DOMAIN_CATALOG: ["catalogos"],
    DOMAIN_GENERAL: ["nbr", "tdr", "sinapi"],
}

DOMAIN_NBR_HINTS: dict[str, list[str]] = {
    DOMAIN_STRUCTURAL: ["NBR 6118", "NBR 8681", "NBR 8800"],
    DOMAIN_GEOTECHNICAL: ["NBR 6122", "NBR 7185"],
    DOMAIN_HYDRAULIC: ["NBR 5626", "NBR 8160", "NBR 10844"],
    DOMAIN_ELECTRICAL: ["NBR 5410"],
    DOMAIN_NORM: ["NBR 9050", "NBR 15575"],
    DOMAIN_BUDGET: ["SINAPI"],
}

IMMUTABLE_KNOWLEDGE_BASES = True
