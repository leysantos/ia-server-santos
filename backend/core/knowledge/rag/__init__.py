"""RAG orientado por agente — routing, escopo e rerank especializado."""

from core.knowledge.rag.agent_retriever import (
    AgentRAGResult,
    retrieve_context_for_route,
    retrieve_for_agent,
)
from core.knowledge.rag.agent_router import agent_from_discipline, route_query_to_agent
from core.knowledge.rag.agent_reranker import agent_rerank
from core.knowledge.rag.agent_scopes import AGENT_SCOPES, get_agent_scope

__all__ = [
    "AGENT_SCOPES",
    "AgentRAGResult",
    "agent_from_discipline",
    "agent_rerank",
    "get_agent_scope",
    "retrieve_context_for_route",
    "retrieve_for_agent",
    "route_query_to_agent",
]
