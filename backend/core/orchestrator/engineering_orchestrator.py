"""
Engineering Orchestrator — engenheiro chefe digital.

Único ponto de decisão:
  classificar domínio → escolher agente → escolher knowledge type → RAG → rerank
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from config import settings
from core.knowledge.disciplines import DISCIPLINE_TO_SLUG
from core.orchestrator.domain_classifier import (
    KnowledgeDomain,
    classify_domain,
)
from core.orchestrator.knowledge_router import (
    KnowledgeRouteConfig,
    resolve_knowledge_route,
)

logger = logging.getLogger(__name__)

ENGINEERING_DISCIPLINES = frozenset(
    d for d in DISCIPLINE_TO_SLUG if d not in ("ORÇAMENTO", "GERAL", "CHAT")
)


@dataclass
class ExecutionPlan:
    query: str
    classification: dict
    knowledge_route: dict
    agent_slug: str
    discipline: str
    use_rag: bool = True
    disciplines: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_slug": self.agent_slug,
            "discipline": self.discipline,
            "classification": self.classification,
            "knowledge_route": self.knowledge_route,
            "use_rag": self.use_rag,
            "disciplines": self.disciplines,
        }


def orchestrate(
    query: str,
    discipline_hint: Optional[str] = None,
    *,
    use_rag: bool = True,
) -> ExecutionPlan:
    """
    Planeja execução: domínio + agente + knowledge type.

    Não executa agentes — apenas decide.
    """
    classification = classify_domain(query, discipline_hint=discipline_hint)
    route = resolve_knowledge_route(classification)

    # Forçar agente orçamento em queries de custo
    agent_slug = classification.agent_slug
    discipline = classification.discipline
    if route.knowledge_type == "cost":
        agent_slug = "orcamento"
        discipline = "ORÇAMENTO"
    elif route.knowledge_type == "engineering" and agent_slug == "orcamento":
        agent_slug = "estruturas"
        discipline = "ESTRUTURAL"

    rag_enabled = use_rag and agent_slug != "chat"

    return ExecutionPlan(
        query=query,
        classification=classification.to_dict(),
        knowledge_route={
            "knowledge_type": route.knowledge_type,
            "base_keys": list(route.base_keys),
            "allowed_content_types": sorted(route.allowed_content_types),
            "blocked_content_types": sorted(route.blocked_content_types),
            "rerank_profile": route.rerank_profile,
        },
        agent_slug=agent_slug,
        discipline=discipline,
        use_rag=rag_enabled,
    )


def filter_disciplines_by_domain(
    query: str,
    disciplines: list[str],
) -> list[str]:
    """
    Evita mistura indevida na decomposição multidisciplinar.

    - Query puramente de custo → só ORÇAMENTO
    - Query puramente de engenharia → remove ORÇAMENTO (salvo mixed explícito)
    """
    if not disciplines:
        return disciplines

    classification = classify_domain(query)
    domain = classification.primary_domain

    if domain == KnowledgeDomain.COST:
        return ["ORÇAMENTO"]

    if domain == KnowledgeDomain.ENGINEERING:
        filtered = [d for d in disciplines if d != "ORÇAMENTO"]
        return filtered or disciplines[:1]

    if domain == KnowledgeDomain.MIXED:
        if "ORÇAMENTO" not in disciplines and classification.is_cost_query:
            return disciplines + ["ORÇAMENTO"]
        return disciplines

    return disciplines


def prepare_agent_execution(
    agent_route: dict,
    query: str,
) -> dict:
    """
    Enriquece route antes do RAG/dispatch com plano do orquestrador.

    Valida: disciplina de engenharia nunca recebe knowledge_type=cost.
    """
    if not settings.USE_ENGINEERING_ORCHESTRATOR:
        return agent_route

    discipline = agent_route.get("discipline")
    plan = orchestrate(query, discipline_hint=discipline)

    enriched = dict(agent_route)
    enriched["_orchestrator"] = plan.to_dict()
    enriched["_knowledge_type"] = plan.knowledge_route["knowledge_type"]
    enriched["_agent_slug"] = plan.agent_slug

    # Bloqueio crítico: engenharia ≠ SINAPI
    disc = (discipline or "").upper()
    if disc in ENGINEERING_DISCIPLINES and plan.knowledge_route["knowledge_type"] == "cost":
        logger.warning(
            "orchestrator blocked cost knowledge for engineering discipline=%s",
            disc,
        )
        plan.knowledge_route["knowledge_type"] = "engineering"
        enriched["_knowledge_type"] = "engineering"

    if disc == "ORÇAMENTO":
        enriched["_knowledge_type"] = "cost"
        enriched["_agent_slug"] = "orcamento"

    if plan.agent_slug == "chat":
        enriched["_use_rag"] = False

    logger.info(
        "orchestrator plan agent=%s discipline=%s knowledge=%s domain=%s",
        plan.agent_slug,
        plan.discipline,
        enriched.get("_knowledge_type"),
        plan.classification.get("primary_domain"),
    )

    return enriched


def get_knowledge_route_for_discipline(
    query: str,
    discipline: Optional[str] = None,
) -> KnowledgeRouteConfig:
    """Atalho para RAG layer."""
    classification = classify_domain(query, discipline_hint=discipline)
    if (discipline or "").upper() == "ORÇAMENTO":
        classification.is_cost_query = True
        classification.primary_domain = KnowledgeDomain.COST
    elif discipline and discipline.upper() in ENGINEERING_DISCIPLINES:
        classification.is_engineering_query = True
        if classification.primary_domain == KnowledgeDomain.COST:
            classification.primary_domain = KnowledgeDomain.ENGINEERING
    return resolve_knowledge_route(classification)
