"""
Disciplinas de conhecimento — fonte única alinhada a backend/agents/ e agent_registry.

Cada slug corresponde ao módulo em agents/ (ex.: estruturas.py → slug estruturas).
CHAT não possui pasta de conhecimento técnico.
"""

from __future__ import annotations

from core.agent_registry import DISCIPLINE_TO_AGENT

# Disciplina do sistema → slug (= nome do agente sem sufixo _agent)
DISCIPLINE_TO_SLUG: dict[str, str] = {
    discipline: agent_name.removesuffix("_agent")
    for discipline, agent_name in DISCIPLINE_TO_AGENT.items()
}

SLUG_TO_DISCIPLINE: dict[str, str] = {
    slug: discipline for discipline, slug in DISCIPLINE_TO_SLUG.items()
}

# Slugs com pasta em backend/knowledge/ (exclui CHAT — agente conversacional)
DISCIPLINE_SLUGS: tuple[str, ...] = tuple(sorted(DISCIPLINE_TO_SLUG.values()))

# Aliases legados → slug canônico (sem pasta no disco)
SLUG_ALIASES: dict[str, str] = {
    "estrutural": "estruturas",
    "ambiental": "meio_ambiente",
    "gis": "geoprocessamento",
    "cost": "orcamento",
    "nbr": "estruturas",
}

# Pastas que não devem existir no disco (removidas pelo scaffold --prune)
DEPRECATED_SLUG_DIRS: frozenset[str] = frozenset({"estrutural", "gis", "ambiental"})


def resolve_slug_alias(raw_slug: str) -> tuple[str, bool]:
    """
    Resolve alias → slug canônico.

    Returns:
        (canonical_slug, was_alias)
    """
    slug = raw_slug.strip().lower().replace(" ", "_")
    if slug in SLUG_ALIASES:
        return SLUG_ALIASES[slug], True
    return slug, False

# Disciplinas de engenharia (mesmo conjunto de DISCIPLINE_NBRS / legacy_factory)
ENGINEERING_DISCIPLINES: tuple[str, ...] = tuple(
    d for d in DISCIPLINE_TO_AGENT if d != "GERAL"
)


def normalize_slug(raw: str) -> str:
    """Normaliza slug ou disciplina do sistema para slug canônico."""
    if not raw:
        return "geral"
    token = raw.strip()
    upper = token.upper()
    if upper in DISCIPLINE_TO_SLUG:
        return DISCIPLINE_TO_SLUG[upper]
    slug = token.lower().replace(" ", "_")
    canonical, was_alias = resolve_slug_alias(slug)
    if was_alias:
        return canonical
    if canonical in SLUG_TO_DISCIPLINE:
        return canonical
    for known in DISCIPLINE_SLUGS:
        if known in slug or slug in known:
            return known
    return "geral"


def slug_for_discipline(discipline: str) -> str:
    """Disciplina do router/dispatcher → slug da pasta knowledge/."""
    return normalize_slug(discipline)
