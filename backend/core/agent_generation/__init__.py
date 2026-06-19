"""Agent Generation Loop v1 (controlled) — proposta, sandbox, avaliação, promotion gate."""

from core.agent_generation.agent_generation_engine import (
    AgentGenerationEngine,
    emit_agent_generation_signal,
    get_agent_generation_engine,
)
from core.agent_generation.agent_proposer import AgentProposal, AgentProposer
from core.agent_generation.constants import ONLY_ALLOWED_DOMAINS

__all__ = [
    "AgentGenerationEngine",
    "AgentProposal",
    "AgentProposer",
    "ONLY_ALLOWED_DOMAINS",
    "emit_agent_generation_signal",
    "get_agent_generation_engine",
]
