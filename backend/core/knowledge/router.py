"""
Discipline Knowledge Router — roteamento por disciplina (evolução paralela).

Opt-in via USE_DISCIPLINE_KNOWLEDGE_ROUTER=false (default).
Não altera dispatcher, agentes, /chat ou /orchestrate quando desligado.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from config import settings
from core.knowledge.domain_detector import detect_domain
from core.knowledge.knowledge_base_router import get_knowledge_router
from core.knowledge.resolver import (
    DISCIPLINE_LAYERS,
    get_discipline_read_paths_for_base,
    get_knowledge_path,
    normalize_discipline_slug,
)

logger = logging.getLogger(__name__)

# Mapeamento domínio técnico → slug (alinhado a backend/agents/)
DOMAIN_TO_DISCIPLINE_SLUG: dict[str, str] = {
    "structural": "estruturas",
    "cost": "orcamento",
    "budget": "orcamento",
    "norm": "estruturas",
    "geotechnical": "geotecnia",
    "hydraulic": "hidrossanitario",
    "electrical": "eletrica",
    "catalog": "arquitetura",
    "general": "geral",
}

# slug → base FAISS legada (para retrieve quando USE_KNOWLEDGE_ROUTER)
DISCIPLINE_TO_LEGACY_BASE: dict[str, str] = {
    "estruturas": "nbr",
    "geotecnia": "nbr",
    "hidrossanitario": "nbr",
    "saneamento": "nbr",
    "drenagem": "nbr",
    "eletrica": "nbr",
    "telecom": "nbr",
    "incendio": "nbr",
    "arquitetura": "catalogos",
    "transportes": "nbr",
    "infraestrutura": "nbr",
    "geoprocessamento": "tdr",
    "topografia": "tdr",
    "orcamento": "sinapi",
    "meio_ambiente": "tdr",
    "geral": "tdr",
}


@dataclass
class DisciplineKnowledgeRoute:
    query: str
    discipline_slug: str
    layer: str
    paths: list[Path] = field(default_factory=list)
    context_text: str = ""
    domain: str = ""
    used_discipline_router: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "discipline_slug": self.discipline_slug,
            "layer": self.layer,
            "paths": [str(p) for p in self.paths],
            "context_length": len(self.context_text),
            "domain": self.domain,
            "used_discipline_router": self.used_discipline_router,
        }


def _resolve_discipline_slug(query: str, discipline_hint: Optional[str]) -> str:
    if discipline_hint:
        return normalize_discipline_slug(discipline_hint)
    domain = detect_domain(query)
    return DOMAIN_TO_DISCIPLINE_SLUG.get(domain, "geral")


def _collect_paths(slug: str) -> list[Path]:
    paths: list[Path] = []
    for layer in DISCIPLINE_LAYERS:
        path = get_knowledge_path(slug, layer)
        if path.exists():
            paths.append(path)
    return paths


def route_knowledge(
    query: str,
    discipline_hint: Optional[str] = None,
) -> DisciplineKnowledgeRoute:
    """
    Detecta disciplina → escolhe paths → retorna contexto RAG (se flags ativas).

    Com USE_DISCIPLINE_KNOWLEDGE_ROUTER=false: retorna metadados sem alterar RAG.
    """
    slug = _resolve_discipline_slug(query, discipline_hint)
    domain = detect_domain(query, discipline=discipline_hint)

    route = DisciplineKnowledgeRoute(
        query=query,
        discipline_slug=slug,
        layer="canonical",
        domain=domain,
        used_discipline_router=settings.USE_DISCIPLINE_KNOWLEDGE_ROUTER,
    )

    if not settings.USE_DISCIPLINE_KNOWLEDGE_ROUTER:
        return route

    route.paths = _collect_paths(slug)

    if settings.USE_KNOWLEDGE_ROUTER:
        legacy_base = DISCIPLINE_TO_LEGACY_BASE.get(slug, "nbr")
        try:
            kc = get_knowledge_router().retrieve_context(
                query=query,
                discipline=discipline_hint,
            )
            route.context_text = kc.context_text
        except Exception as exc:
            logger.debug("route_knowledge RAG fallback: %s", exc)

    logger.info(
        "discipline_knowledge_route slug=%s paths=%d context_len=%d",
        slug,
        len(route.paths),
        len(route.context_text),
    )
    return route


def get_index_paths_for_base(base_key: str) -> list[tuple[Path, str]]:
    """Paths extras de indexação disciplinar (somente se flag ativa)."""
    if not settings.USE_DISCIPLINE_KNOWLEDGE_ROUTER:
        return []
    return get_discipline_read_paths_for_base(base_key)
