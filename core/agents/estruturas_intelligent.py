"""Agente estrutural inteligente — exemplo de uso de BaseAgentIntelligent."""

from core.agent_registry import get_agent_name
from core.agents.base_agent_intelligent import BaseAgentIntelligent


class EstruturasIntelligentAgent(BaseAgentIntelligent):
    """
    Agente estrutural com RAG v2 + LLM.
    Novos agentes devem seguir este padrão de herança.
    """

    def __init__(self, **kwargs):
        super().__init__(
            name=get_agent_name("ESTRUTURAL"),
            discipline="ESTRUTURAL",
            normas_base=["NBR 6118", "NBR 8681"],
            **kwargs,
        )
