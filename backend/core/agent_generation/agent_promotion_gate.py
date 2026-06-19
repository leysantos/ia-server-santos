"""
Agent Promotion Gate — validação rigorosa antes de qualquer promoção.
Promoção = registro versionado em candidate registry — NUNCA ativa no dispatcher.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from core.agent_generation.agent_evaluator import EvaluationResult
from core.agent_generation.agent_registry_candidate import get_candidate_registry
from core.agent_generation.constants import (
    IMPROVEMENT_THRESHOLD,
    RISK_SCORE_THRESHOLD,
    is_allowed_domain,
    resolve_discipline,
)
from core.agent_registry import DISCIPLINE_TO_AGENT, get_agent_name

logger = logging.getLogger(__name__)


@dataclass
class PromotionDecision:
    approved: bool
    reasons: list[str] = field(default_factory=list)
    proposal_name: str = ""
    candidate_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "reasons": self.reasons,
            "proposal_name": self.proposal_name,
            "candidate_name": self.candidate_name,
        }


class AgentPromotionGate:
    """
    Somente promove se:
    - improvement > 8%
    - risk_score < threshold
    - não duplica agente existente
    - domínio permitido
    - limites MAX_AGENTS_TOTAL / MAX_NEW_AGENTS_PER_WEEK
    """

    MIN_CONSISTENCY = 0.50

    def evaluate(
        self,
        proposal: dict[str, Any],
        evaluation: EvaluationResult,
    ) -> PromotionDecision:
        name = proposal.get("name") or ""
        decision = PromotionDecision(
            approved=True,
            proposal_name=name,
            candidate_name=name,
        )

        discipline = resolve_discipline(proposal.get("discipline") or "")
        if not is_allowed_domain(discipline):
            decision.approved = False
            decision.reasons.append(f"domínio não permitido: {discipline}")

        if self._is_duplicate(name, discipline, proposal.get("specialization")):
            decision.approved = False
            decision.reasons.append("agente duplicado (nome ou especialização existente)")

        risk = float(proposal.get("risk_score") or 0.5)
        if risk >= RISK_SCORE_THRESHOLD:
            decision.approved = False
            decision.reasons.append(
                f"risk_score {risk:.2f} >= threshold {RISK_SCORE_THRESHOLD}"
            )

        if not evaluation.passed_improvement_gate:
            decision.approved = False
            decision.reasons.append(
                f"improvement {evaluation.improvement_over_baseline:.2%} "
                f"< {IMPROVEMENT_THRESHOLD:.0%}"
            )

        if evaluation.consistency_score < self.MIN_CONSISTENCY:
            decision.approved = False
            decision.reasons.append(
                f"consistency {evaluation.consistency_score:.2f} < {self.MIN_CONSISTENCY}"
            )

        registry = get_candidate_registry()
        ok, limit_reason = registry.can_register_new()
        if not ok:
            decision.approved = False
            decision.reasons.append(limit_reason)

        if decision.approved:
            decision.reasons.append("approved_for_deployment — requer ativação manual")
        else:
            logger.info("Promotion gate REJECTED %s: %s", name, decision.reasons)

        return decision

    @staticmethod
    def _is_duplicate(name: str, discipline: str, specialization: Optional[str]) -> bool:
        if name in DISCIPLINE_TO_AGENT.values():
            return True
        if get_agent_name(discipline) == name:
            return True

        registry = get_candidate_registry()
        for candidate in registry.list_candidates():
            if candidate.name == name:
                return True
            if (
                candidate.discipline == discipline
                and candidate.specialization == (specialization or "")
                and candidate.status == "promoted"
            ):
                return True
        return False
