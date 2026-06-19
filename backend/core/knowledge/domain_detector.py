"""
Domain Detector — identifica tipo de pergunta técnica para roteamento de base.
"""

from __future__ import annotations

import re
import unicodedata

from core.knowledge.constants import (
    DOMAIN_BUDGET,
    DOMAIN_CATALOG,
    DOMAIN_COST,
    DOMAIN_ELECTRICAL,
    DOMAIN_GENERAL,
    DOMAIN_GEOTECHNICAL,
    DOMAIN_HYDRAULIC,
    DOMAIN_NORM,
    DOMAIN_STRUCTURAL,
)

_COST_MARKERS = (
    "sinapi", "custo", "custos", "preço", "preco", "orçamento", "orcamento",
    "bdi", "insumo", "insumos", "composição", "composicao", "r$/m", "r$/m²",
    "r$/m2", "valor m³", "valor m3", "mão de obra", "mao de obra",
)

_BUDGET_MARKERS = (
    "orçamento de obra", "orcamento de obra", "planilha orçamentária",
    "planilha orcamentaria", "tcpo", "sicro", "budget", "custo total",
    "custo da obra", "memorial de quantidades",
)

_STRUCTURAL_MARKERS = (
    "dimensionar", "dimensionamento", "viga", "laje", "pilar", "estrutura",
    "concreto armado", "protend", "nbr 6118", "nbr6118", "armadura",
)

_GEOTECH_MARKERS = (
    "fundação", "fundacao", "estaca", "solo", "spt", "recalque", "nbr 6122",
    "geotecnia", "terraplenagem",
)

_HYDRAULIC_MARKERS = (
    "hidráulic", "hidraulic", "esgoto", "água fria", "agua fria", "reservatório",
    "reservatorio", "nbr 5626", "nbr 8160",
)

_ELECTRICAL_MARKERS = (
    "elétric", "eletric", "disjuntor", "nbr 5410", "quadro elétrico",
    "tomada", "circuito",
)

_NORM_MARKERS = (
    "norma", "nbr ", "abnt", "acessibilidade", "nbr 9050", "conformidade normativa",
)

_CATALOG_MARKERS = (
    "catálogo", "catalogo", "fabricante", "produto", "especificação técnica",
)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def detect_domain(text: str, discipline: str | None = None) -> str:
    """
    Detecta domínio de conhecimento para roteamento multi-base.

    Exemplos:
      - "dimensionar viga" → structural
      - "custo concreto m³" → cost
      - "orçamento obra escola" → budget
      - "norma acessibilidade" → norm
      - "fundação solo fraco" → geotechnical
    """
    normalized = _normalize(text)

    if discipline:
        disc = discipline.upper()
        if disc == "ORÇAMENTO":
            return DOMAIN_BUDGET if any(m in normalized for m in _BUDGET_MARKERS) else DOMAIN_COST
        if disc == "ESTRUTURAL":
            return DOMAIN_STRUCTURAL
        if disc == "GEOTECNIA":
            return DOMAIN_GEOTECHNICAL
        if disc in ("HIDROSSANITÁRIO", "DRENAGEM", "SANEAMENTO"):
            return DOMAIN_HYDRAULIC
        if disc == "ELÉTRICA":
            return DOMAIN_ELECTRICAL

    if any(m in normalized for m in _BUDGET_MARKERS):
        return DOMAIN_BUDGET
    if any(m in normalized for m in _COST_MARKERS):
        return DOMAIN_COST
    if any(m in normalized for m in _GEOTECH_MARKERS):
        return DOMAIN_GEOTECHNICAL
    if any(m in normalized for m in _STRUCTURAL_MARKERS):
        return DOMAIN_STRUCTURAL
    if any(m in normalized for m in _HYDRAULIC_MARKERS):
        return DOMAIN_HYDRAULIC
    if any(m in normalized for m in _ELECTRICAL_MARKERS):
        return DOMAIN_ELECTRICAL
    if any(m in normalized for m in _CATALOG_MARKERS):
        return DOMAIN_CATALOG
    if any(m in normalized for m in _NORM_MARKERS) or re.search(r"nbr\s*\d", normalized):
        return DOMAIN_NORM

    return DOMAIN_GENERAL
