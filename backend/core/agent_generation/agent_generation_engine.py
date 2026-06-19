"""
Agent Generation Engine — orquestrador do loop controlado v1.

Pipeline: gaps → proposta → sandbox → avaliação → promotion gate
Nunca ativa agentes no dispatcher automaticamente.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from config import settings
from core.agent_generation.agent_evaluator import AgentEvaluator
from core.agent_generation.agent_promotion_gate import AgentPromotionGate
from core.agent_generation.agent_proposer import AgentProposal, AgentProposer
from core.agent_generation.agent_registry_candidate import (
    CandidateRegistry,
    get_candidate_registry,
)
from core.agent_generation.agent_simulator import AgentSimulator
from core.agent_generation.audit import (
    save_agent_proposal,
    save_agent_simulation,
    update_agent_proposal_status,
)
from core.agent_generation.constants import (
    PROPOSAL_STATUS_APPROVED,
    PROPOSAL_STATUS_EVALUATED,
    PROPOSAL_STATUS_REJECTED,
    PROPOSAL_STATUS_SIMULATING,
)

logger = logging.getLogger(__name__)

_engine: Optional["AgentGenerationEngine"] = None


class AgentGenerationEngine:
    """Loop controlado de geração de agentes."""

    def __init__(self) -> None:
        self.proposer = AgentProposer()
        self.simulator = AgentSimulator()
        self.evaluator = AgentEvaluator()
        self.promotion_gate = AgentPromotionGate()
        self.registry: CandidateRegistry = get_candidate_registry()

    @staticmethod
    def enabled() -> bool:
        return settings.USE_AGENT_GENERATION

    def process_gap_signal(self, signal: dict[str, Any]) -> dict[str, Any]:
        """Chamado pelo Evolution Loop ou manualmente quando há gap de performance."""
        if not self.enabled():
            return {"status": "disabled"}

        proposals = self.proposer.propose_from_evolution_signal(signal)
        saved: list[dict[str, Any]] = []
        for prop in proposals:
            record = self._persist_proposal(prop)
            if record:
                saved.append(record)

        return {
            "status": "proposed",
            "proposals_count": len(saved),
            "proposals": saved,
        }

    def run_full_pipeline(
        self,
        proposal: dict[str, Any],
        *,
        n_runs: Optional[int] = None,
        use_llm: bool = False,
    ) -> dict[str, Any]:
        """Proposta → sandbox → avaliação → promotion gate."""
        if not self.enabled():
            return {"status": "disabled"}

        from core.agent_generation.constants import is_allowed_domain

        if not is_allowed_domain(proposal.get("discipline") or ""):
            return {"status": "rejected", "reason": "domain_not_allowed"}

        proposal_id = proposal.get("id")
        if proposal_id:
            update_agent_proposal_status(proposal_id, PROPOSAL_STATUS_SIMULATING)

        candidate = self.registry.build_from_proposal(proposal)
        self.registry.register_candidate(candidate)

        report = self.simulator.run_sandbox(
            proposal,
            candidate,
            n_runs=n_runs,
            use_llm=use_llm,
        )
        sim_record = save_agent_simulation(
            {
                "proposal_id": proposal_id,
                "proposal_name": proposal.get("name"),
                "discipline": candidate.discipline,
                "run_count": report.run_count,
                "mode": report.mode,
                "report": report.to_dict(),
            }
        )

        evaluation = self.evaluator.evaluate(report)
        decision = self.promotion_gate.evaluate(proposal, evaluation)

        final_status = PROPOSAL_STATUS_APPROVED if decision.approved else PROPOSAL_STATUS_REJECTED
        if proposal_id:
            update_agent_proposal_status(
                proposal_id,
                final_status,
                evaluation=evaluation.to_dict(),
                promotion=decision.to_dict(),
            )

        if decision.approved:
            promoted = self.registry.promote_candidate(
                candidate.name,
                proposal_id=proposal_id,
            )
            logger.info("Agent promoted (registry only): %s", candidate.name)
        else:
            self.registry.reject_candidate(candidate.name, "; ".join(decision.reasons))
            promoted = None

        return {
            "status": final_status,
            "proposal": proposal,
            "simulation_id": sim_record.get("id") if sim_record else None,
            "evaluation": evaluation.to_dict(),
            "promotion": decision.to_dict(),
            "candidate": promoted.to_dict() if promoted else candidate.to_dict(),
        }

    def propose_and_pipeline(
        self,
        *,
        discipline: Optional[str] = None,
        evolution_insight: Optional[dict[str, Any]] = None,
        n_runs: Optional[int] = None,
        use_llm: bool = False,
    ) -> dict[str, Any]:
        proposals = self.proposer.propose_from_gaps(
            evolution_insight=evolution_insight,
            discipline=discipline,
        )
        results = []
        for prop in proposals:
            record = self._persist_proposal(prop)
            payload = {**prop.to_dict(), **(record or {})}
            results.append(self.run_full_pipeline(payload, n_runs=n_runs, use_llm=use_llm))
        return {"status": "completed", "results": results}

    def _persist_proposal(self, prop: AgentProposal) -> Optional[dict[str, Any]]:
        payload = prop.to_dict()
        saved = save_agent_proposal(payload)
        if saved:
            payload["id"] = saved.get("id")
        return payload


def get_agent_generation_engine() -> AgentGenerationEngine:
    global _engine
    if _engine is None:
        _engine = AgentGenerationEngine()
    return _engine


def emit_agent_generation_signal(signal: dict[str, Any]) -> None:
    """Fire-and-forget — acionado por Evolution Loop em gaps de agente."""
    if not settings.USE_AGENT_GENERATION:
        return
    try:
        insight = signal.get("extra", {}).get("insight") or {}
        if not (
            signal.get("source") == "agent"
            or insight.get("degradation_detected")
            or float(signal.get("output_quality") or 1.0) < 0.55
        ):
            return
        get_agent_generation_engine().process_gap_signal(signal)
    except Exception as exc:
        logger.warning("Agent Generation Loop ignorado: %s", exc)
