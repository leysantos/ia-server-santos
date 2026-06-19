"""
Escopos de conhecimento por agente — alinhado a backend/agents/*.py.

Cada agente define: índices FAISS, content_types permitidos/bloqueados,
tipos de fonte e prioridades de ranking.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.agents.base_agent_intelligent import DISCIPLINE_NBRS
from core.knowledge.disciplines import DISCIPLINE_TO_SLUG, SLUG_TO_DISCIPLINE

SOURCE_NORMATIVE = "normative"
SOURCE_PRICING = "pricing"
SOURCE_DOCUMENTATION = "documentation"

# Módulos em backend/agents/ (exceto base_agent)
AGENT_MODULES: tuple[str, ...] = (
    "arquitetura",
    "drenagem",
    "eletrica",
    "estruturas",
    "geoprocessamento",
    "geotecnia",
    "hidrossanitario",
    "incendio",
    "infraestrutura",
    "meio_ambiente",
    "orcamento",
    "saneamento",
    "telecom",
    "topografia",
    "transportes",
    "chat",
)


@dataclass(frozen=True)
class AgentScope:
    agent_slug: str
    discipline: str
    base_keys: tuple[str, ...]
    allowed_content_types: frozenset[str]
    blocked_content_types: frozenset[str]
    source_types: tuple[str, ...]
    priority_keywords: tuple[str, ...] = ()
    priority_nbrs: tuple[str, ...] = ()
    uses_technical_rag: bool = True


def _norm_keywords(*words: str) -> tuple[str, ...]:
    return tuple(w.lower() for w in words if w)


def _scope(
    slug: str,
    *,
    base_keys: tuple[str, ...],
    allowed: frozenset[str],
    blocked: frozenset[str],
    sources: tuple[str, ...],
    keywords: tuple[str, ...] = (),
    extra_nbrs: tuple[str, ...] = (),
    uses_rag: bool = True,
) -> AgentScope:
    discipline = SLUG_TO_DISCIPLINE.get(slug, "GERAL")
    nbrs = tuple(
        n.replace("NBR ", "").replace("NBR", "").strip()
        for n in DISCIPLINE_NBRS.get(discipline, [])
        if n and not n.startswith(("SINAPI", "ISO", "OGC", "Resolu"))
    )
    nbrs = nbrs + extra_nbrs
    return AgentScope(
        agent_slug=slug,
        discipline=discipline,
        base_keys=base_keys,
        allowed_content_types=allowed,
        blocked_content_types=blocked,
        source_types=sources,
        priority_keywords=keywords,
        priority_nbrs=nbrs,
        uses_technical_rag=uses_rag,
    )


_PRICING_BLOCKED = frozenset({"nbrs", "nbr"})
_NORM_BLOCKED = frozenset({"sinapi", "tcpo"})

# Tipos técnicos (para bloqueio total no agente chat)
_ALL_CONTENT_TYPES = frozenset({
    "nbrs", "nbr", "sinapi", "tcpo", "tdrs", "tdr",
    "catalogos", "catalog", "manuais", "projetos", "project", "regional",
    "cost", "composition",
})

AGENT_SCOPES: dict[str, AgentScope] = {
    "estruturas": _scope(
        "estruturas",
        base_keys=("nbr",),
        allowed=frozenset({"nbrs", "nbr"}),
        blocked=_NORM_BLOCKED,
        sources=(SOURCE_NORMATIVE,),
        keywords=_norm_keywords(
            "concreto", "armadura", "viga", "laje", "pilar", "dimensionamento",
            "estrutural", "6118", "8681", "8800", "7480",
        ),
    ),
    "orcamento": _scope(
        "orcamento",
        base_keys=("sinapi", "tcpo"),
        allowed=frozenset({"sinapi", "tcpo", "cost", "composition"}),
        blocked=_PRICING_BLOCKED,
        sources=(SOURCE_PRICING,),
        keywords=_norm_keywords(
            "sinapi", "tcpo", "sicro", "composição", "composicao", "insumo",
            "custo", "orçamento", "orcamento", "bdi", "unitário", "unitario",
        ),
    ),
    "eletrica": _scope(
        "eletrica",
        base_keys=("nbr",),
        allowed=frozenset({"nbrs", "nbr"}),
        blocked=_NORM_BLOCKED,
        sources=(SOURCE_NORMATIVE,),
        keywords=_norm_keywords(
            "elétric", "eletric", "5410", "carga", "disjuntor", "circuito",
            "quadro elétrico", "tomada",
        ),
    ),
    "hidrossanitario": _scope(
        "hidrossanitario",
        base_keys=("nbr",),
        allowed=frozenset({"nbrs", "nbr"}),
        blocked=_NORM_BLOCKED,
        sources=(SOURCE_NORMATIVE,),
        keywords=_norm_keywords(
            "hidráulic", "hidraulic", "5626", "8160", "esgoto", "água", "agua",
            "reservatório", "reservatorio",
        ),
    ),
    "drenagem": _scope(
        "drenagem",
        base_keys=("nbr",),
        allowed=frozenset({"nbrs", "nbr"}),
        blocked=_NORM_BLOCKED,
        sources=(SOURCE_NORMATIVE,),
        keywords=_norm_keywords("drenagem", "10844", "9575", "pluvial", "bocas de lobo"),
    ),
    "geotecnia": _scope(
        "geotecnia",
        base_keys=("nbr",),
        allowed=frozenset({"nbrs", "nbr"}),
        blocked=_NORM_BLOCKED,
        sources=(SOURCE_NORMATIVE,),
        keywords=_norm_keywords("geotecnia", "fundação", "fundacao", "solo", "spt", "6122", "7185"),
    ),
    "incendio": _scope(
        "incendio",
        base_keys=("nbr",),
        allowed=frozenset({"nbrs", "nbr"}),
        blocked=_NORM_BLOCKED,
        sources=(SOURCE_NORMATIVE,),
        keywords=_norm_keywords("incêndio", "incendio", "17240", "10898", "sprinkler"),
    ),
    "telecom": _scope(
        "telecom",
        base_keys=("nbr",),
        allowed=frozenset({"nbrs", "nbr"}),
        blocked=_NORM_BLOCKED,
        sources=(SOURCE_NORMATIVE,),
        keywords=_norm_keywords("telecom", "cabeamento", "14567", "11801", "datacenter"),
    ),
    "transportes": _scope(
        "transportes",
        base_keys=("nbr",),
        allowed=frozenset({"nbrs", "nbr"}),
        blocked=_NORM_BLOCKED,
        sources=(SOURCE_NORMATIVE,),
        keywords=_norm_keywords("transporte", "pavimento", "7188", "7200", "rodovia"),
    ),
    "infraestrutura": _scope(
        "infraestrutura",
        base_keys=("nbr",),
        allowed=frozenset({"nbrs", "nbr"}),
        blocked=_NORM_BLOCKED,
        sources=(SOURCE_NORMATIVE,),
        keywords=_norm_keywords("infraestrutura", "obra civil", "ponte", "viaduto"),
    ),
    "saneamento": _scope(
        "saneamento",
        base_keys=("nbr",),
        allowed=frozenset({"nbrs", "nbr"}),
        blocked=_NORM_BLOCKED,
        sources=(SOURCE_NORMATIVE,),
        keywords=_norm_keywords("saneamento", "9649", "9814", "ete", "esgoto"),
    ),
    "arquitetura": _scope(
        "arquitetura",
        base_keys=("catalogos", "nbr"),
        allowed=frozenset({"catalogos", "manuais", "nbrs", "nbr", "catalog"}),
        blocked=_NORM_BLOCKED,
        sources=(SOURCE_NORMATIVE, SOURCE_DOCUMENTATION),
        keywords=_norm_keywords("arquitetura", "acessibilidade", "9050", "15575", "catálogo", "catalogo"),
    ),
    "meio_ambiente": _scope(
        "meio_ambiente",
        base_keys=("regional", "tdr"),
        allowed=frozenset({"regional", "tdrs", "tdr"}),
        blocked=frozenset({"sinapi", "tcpo", "nbrs"}),
        sources=(SOURCE_DOCUMENTATION,),
        keywords=_norm_keywords("ambiental", "conama", "licenciamento", "14001", "impacto"),
    ),
    "geoprocessamento": _scope(
        "geoprocessamento",
        base_keys=("tdr",),
        allowed=frozenset({"tdrs", "tdr", "projetos", "project"}),
        blocked=frozenset({"sinapi", "tcpo", "nbrs"}),
        sources=(SOURCE_DOCUMENTATION,),
        keywords=_norm_keywords("geoprocessamento", "gis", "shapefile", "coordenadas", "ogc"),
    ),
    "topografia": _scope(
        "topografia",
        base_keys=("tdr",),
        allowed=frozenset({"tdrs", "tdr", "projetos", "project"}),
        blocked=frozenset({"sinapi", "tcpo", "nbrs"}),
        sources=(SOURCE_DOCUMENTATION,),
        keywords=_norm_keywords("topografia", "13133", "nivelamento", "altimetria", "planialtimetrico"),
    ),
    "chat": AgentScope(
        agent_slug="chat",
        discipline="CHAT",
        base_keys=(),
        allowed_content_types=frozenset(),
        blocked_content_types=_ALL_CONTENT_TYPES,
        source_types=(),
        uses_technical_rag=False,
    ),
}

# Disciplina do dispatcher → agent slug
DISCIPLINE_TO_AGENT_SLUG: dict[str, str] = {
    disc: slug for disc, slug in DISCIPLINE_TO_SLUG.items()
}
DISCIPLINE_TO_AGENT_SLUG["CHAT"] = "chat"


def get_agent_scope(agent_slug: str) -> AgentScope:
    slug = agent_slug.strip().lower().replace(" ", "_")
    if slug.endswith("_agent"):
        slug = slug.removesuffix("_agent")
    return AGENT_SCOPES.get(slug, AGENT_SCOPES["estruturas"])


def chunk_content_type(chunk) -> str:
    meta = chunk.metadata or {}
    raw = meta.get("content_type") or chunk.doc_type or ""
    return raw.strip().lower().replace("nbr", "nbrs") if raw == "nbr" else raw.strip().lower()


def is_blocked_for_agent(chunk, scope: AgentScope) -> bool:
    ct = chunk_content_type(chunk)
    if not ct:
        return False
    if ct in scope.blocked_content_types:
        return True
    if scope.allowed_content_types and ct not in scope.allowed_content_types:
        # tipos desconhecidos: permitir se não estiver bloqueado
        normalized_allowed = {a.replace("nbr", "nbrs") for a in scope.allowed_content_types}
        if ct not in normalized_allowed and ct not in scope.allowed_content_types:
            return ct in ("sinapi", "tcpo", "nbrs", "nbr")
    return False


def filter_hits_by_agent_scope(
    hits: list[tuple],
    scope: AgentScope,
) -> list[tuple]:
    """Remove contaminação cross-agent (hard block)."""
    if not scope.uses_technical_rag:
        return []
    return [(c, s) for c, s in hits if not is_blocked_for_agent(c, scope)]
