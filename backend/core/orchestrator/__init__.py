"""
Pacote orquestrador — multi-domínio + engenharia vs orçamento.

Re-exporta API legada de multi_domain.py para compatibilidade.
"""

from core.orchestrator.domain_classifier import (
    DomainClassification,
    KnowledgeDomain,
    classify_domain,
)
from core.orchestrator.engineering_orchestrator import (
    ExecutionPlan,
    filter_disciplines_by_domain,
    get_knowledge_route_for_discipline,
    orchestrate,
    prepare_agent_execution,
)
from core.orchestrator.knowledge_router import (
    KnowledgeRouteConfig,
    apply_knowledge_priority_rerank,
    filter_hits_by_route,
    resolve_knowledge_route,
)
from core.orchestrator.multi_domain import (
    BUILDING_DEFAULTS,
    BUILDING_TRIGGERS,
    KEYWORD_DISCIPLINES,
    VALID_DISCIPLINES,
    _decompose_by_keywords,
    decompose_problem,
    execute_agents,
    process_multi_domain_request,
    synthesize_results,
)

__all__ = [
    "BUILDING_DEFAULTS",
    "BUILDING_TRIGGERS",
    "DomainClassification",
    "ExecutionPlan",
    "KEYWORD_DISCIPLINES",
    "KnowledgeDomain",
    "KnowledgeRouteConfig",
    "VALID_DISCIPLINES",
    "_decompose_by_keywords",
    "apply_knowledge_priority_rerank",
    "classify_domain",
    "decompose_problem",
    "execute_agents",
    "filter_disciplines_by_domain",
    "filter_hits_by_route",
    "get_knowledge_route_for_discipline",
    "orchestrate",
    "prepare_agent_execution",
    "process_multi_domain_request",
    "resolve_knowledge_route",
    "synthesize_results",
]
