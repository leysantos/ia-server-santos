"""
Agent Proposer — detecta gaps de performance e sugere novos agentes (proposta only).
Nunca ativa agentes automaticamente.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from core.agent_generation.constants import (
    ONLY_ALLOWED_DOMAINS,
    PROPOSAL_STATUS_PROPOSED,
    is_allowed_domain,
    normalize_domain,
    resolve_discipline,
)
from core.agent_registry import DISCIPLINE_TO_AGENT, get_agent_name

logger = logging.getLogger(__name__)

_SPECIALIZATION_TEMPLATES: dict[str, list[dict[str, str]]] = {
    "ESTRUTURAL": [
        {
            "suffix": "prestress",
            "purpose": "Dimensionamento e verificação de estruturas protendidas (NBR 6118 cap. pré-tração).",
            "keywords": ("protend", "prestress", "cabo", "ancoragem"),
        },
        {
            "suffix": "steel",
            "purpose": "Dimensionamento de estruturas metálicas conforme NBR 8800.",
            "keywords": ("metálic", "metalic", "aço", "aco", "nbr 8800"),
        },
    ],
    "HIDROSSANITARIO": [
        {
            "suffix": "fire_water",
            "purpose": "Reservatórios e redes de combate a incêndio integradas (NBR 13714).",
            "keywords": ("reservatório incêndio", "recalque", "hidrante"),
        },
    ],
    "GEOTECNIA": [
        {
            "suffix": "foundations",
            "purpose": "Projeto de fundações profundas e estacas (NBR 6122).",
            "keywords": ("estaca", "fundação profunda", "recalque"),
        },
    ],
    "DRENAGEM": [
        {
            "suffix": "urban",
            "purpose": "Drenagem urbana pluvial e microdrenagem (NBR 10844).",
            "keywords": ("microdrenagem", "boca de lobo", "galeria pluvial"),
        },
    ],
}


@dataclass
class AgentProposal:
    name: str
    discipline: str
    purpose: str
    expected_improvement: float
    dependencies: list[str] = field(default_factory=list)
    risk_score: float = 0.35
    domain_key: str = ""
    baseline_agent: str = ""
    specialization: str = ""
    gap_reason: str = ""
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "discipline": self.discipline,
            "purpose": self.purpose,
            "expected_improvement": self.expected_improvement,
            "dependencies": self.dependencies,
            "risk_score": self.risk_score,
            "domain_key": self.domain_key,
            "baseline_agent": self.baseline_agent,
            "specialization": self.specialization,
            "gap_reason": self.gap_reason,
            "version": self.version,
            "status": PROPOSAL_STATUS_PROPOSED,
        }


class AgentProposer:
    """Analisa sinais de performance e gera propostas auditáveis."""

    GAP_SCORE_THRESHOLD = 0.55
    GAP_FAILURE_RATE = 0.25

    def propose_from_gaps(
        self,
        *,
        evolution_insight: Optional[dict[str, Any]] = None,
        discipline: Optional[str] = None,
        agent_name: Optional[str] = None,
        feedback_samples: Optional[list[dict[str, Any]]] = None,
    ) -> list[AgentProposal]:
        proposals: list[AgentProposal] = []
        targets = self._resolve_gap_targets(evolution_insight, discipline, agent_name)

        for disc, baseline, reason in targets:
            if not is_allowed_domain(disc):
                logger.info("Agent proposer: domínio %s fora do permitido — ignorado", disc)
                continue

            resolved = resolve_discipline(disc)
            domain_key = normalize_domain(disc)
            templates = _SPECIALIZATION_TEMPLATES.get(domain_key, [])

            if templates:
                for tpl in templates:
                    if self._matches_gap(tpl["keywords"], feedback_samples, reason):
                        prop = self._build_specialization_proposal(
                            resolved, domain_key, baseline, tpl, reason
                        )
                        if prop and not self._duplicate_proposal(proposals, prop.name):
                            proposals.append(prop)
            else:
                prop = self._build_generic_subagent_proposal(resolved, domain_key, baseline, reason)
                if prop and not self._duplicate_proposal(proposals, prop.name):
                    proposals.append(prop)

        return proposals

    def propose_from_evolution_signal(self, signal: dict[str, Any]) -> list[AgentProposal]:
        insight = signal.get("extra", {}).get("insight") or signal.get("insight") or {}
        return self.propose_from_gaps(
            evolution_insight=insight,
            discipline=signal.get("discipline"),
            agent_name=signal.get("agent_name"),
        )

    @staticmethod
    def _resolve_gap_targets(
        evolution_insight: Optional[dict[str, Any]],
        discipline: Optional[str],
        agent_name: Optional[str],
    ) -> list[tuple[str, str, str]]:
        targets: list[tuple[str, str, str]] = []

        if discipline and is_allowed_domain(discipline):
            baseline = agent_name or get_agent_name(resolve_discipline(discipline))
            reason = "manual_gap_review"
            if evolution_insight:
                if evolution_insight.get("degradation_detected"):
                    reason = evolution_insight.get("degradation_reason") or "degradation_detected"
                elif float(evolution_insight.get("avg_score") or 1.0) < AgentProposer.GAP_SCORE_THRESHOLD:
                    reason = "low_avg_score"
            targets.append((discipline, baseline, reason))

        if not targets:
            for domain in ONLY_ALLOWED_DOMAINS:
                disc = resolve_discipline(domain)
                targets.append((disc, get_agent_name(disc), "periodic_scan"))

        return targets

    def _build_specialization_proposal(
        self,
        discipline: str,
        domain_key: str,
        baseline: str,
        template: dict[str, str],
        reason: str,
    ) -> Optional[AgentProposal]:
        base_slug = re.sub(r"_agent$", "", baseline)
        name = f"{base_slug}_{template['suffix']}_agent"
        if self._agent_name_exists(name):
            return None

        return AgentProposal(
            name=name,
            discipline=discipline,
            purpose=template["purpose"],
            expected_improvement=0.12,
            dependencies=[baseline, discipline],
            risk_score=0.40,
            domain_key=domain_key,
            baseline_agent=baseline,
            specialization=template["suffix"],
            gap_reason=reason,
        )

    def _build_generic_subagent_proposal(
        self,
        discipline: str,
        domain_key: str,
        baseline: str,
        reason: str,
    ) -> Optional[AgentProposal]:
        base_slug = re.sub(r"_agent$", "", baseline)
        name = f"{base_slug}_specialist_agent"
        if self._agent_name_exists(name):
            return None

        return AgentProposal(
            name=name,
            discipline=discipline,
            purpose=f"Sub-especialista em {discipline} para casos com baixa performance do agente baseline.",
            expected_improvement=0.10,
            dependencies=[baseline, discipline],
            risk_score=0.45,
            domain_key=domain_key,
            baseline_agent=baseline,
            specialization="specialist",
            gap_reason=reason,
        )

    @staticmethod
    def _matches_gap(
        keywords: tuple[str, ...],
        feedback_samples: Optional[list[dict[str, Any]]],
        reason: str,
    ) -> bool:
        if reason in ("degradation_detected", "output_quality_below_recent_average", "low_avg_score"):
            return True
        if not feedback_samples:
            return reason != "periodic_scan"
        text = " ".join(
            (s.get("input_text") or "") + " " + (s.get("feedback_text") or "")
            for s in feedback_samples
        ).lower()
        return any(kw in text for kw in keywords)

    @staticmethod
    def _duplicate_proposal(proposals: list[AgentProposal], name: str) -> bool:
        return any(p.name == name for p in proposals)

    @staticmethod
    def _agent_name_exists(name: str) -> bool:
        existing = set(DISCIPLINE_TO_AGENT.values())
        try:
            from core.agent_generation.agent_registry_candidate import get_candidate_registry

            existing.update(get_candidate_registry().list_all_names())
        except Exception:
            pass
        return name in existing
