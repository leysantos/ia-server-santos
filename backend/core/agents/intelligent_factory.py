"""
Factory de agentes inteligentes (RAG v2 + LLM) para o dispatcher.
"""

from core.agent_registry import get_agent_name
from core.agents.base_agent_intelligent import DISCIPLINE_NBRS, BaseAgentIntelligent
from core.agents.geotecnia_intelligent import GeotecniaIntelligentAgent

_AGENT_OVERRIDES: dict[str, type[BaseAgentIntelligent]] = {
    "GEOTECNIA": GeotecniaIntelligentAgent,
}


def build_intelligent_agents() -> dict:
    """Instancia um agente inteligente por disciplina."""
    agents = {}
    for discipline, normas in DISCIPLINE_NBRS.items():
        agent_cls = _AGENT_OVERRIDES.get(discipline, BaseAgentIntelligent)
        agents[discipline] = agent_cls(
            name=get_agent_name(discipline),
            discipline=discipline,
            normas_base=normas,
        )
    return agents
