"""
Factory de agentes inteligentes (RAG v2 + LLM) para o dispatcher.
"""

from core.agent_registry import get_agent_name
from core.agents.base_agent_intelligent import DISCIPLINE_NBRS, BaseAgentIntelligent


def build_intelligent_agents() -> dict:
    """Instancia um agente inteligente por disciplina."""
    agents = {}
    for discipline, normas in DISCIPLINE_NBRS.items():
        agents[discipline] = BaseAgentIntelligent(
            name=get_agent_name(discipline),
            discipline=discipline,
            normas_base=normas,
        )
    return agents
