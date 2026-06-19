"""
Learning Strategy Engine — decide ajustes possíveis, impacto e risco.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from experimental.self_improving.meta_analyzer import MetaAnalysis, MetaFinding

# Mapeamento failure_type → estratégias de ajuste permitidas
STRATEGY_MAP: dict[str, list[dict[str, Any]]] = {
    "routing_low_performance": [
        {
            "target": "router_weights",
            "action": "boost_discipline_keywords",
            "impact": 0.45,
            "risk": 0.25,
            "requires_validation": False,
        },
    ],
    "execution_failure": [
        {
            "target": "agent_behavior",
            "action": "add_error_recovery_prompt",
            "impact": 0.35,
            "risk": 0.20,
            "requires_validation": False,
        },
    ],
    "rag_failure": [
        {
            "target": "rag_boosting",
            "action": "increase_discipline_boost",
            "impact": 0.40,
            "risk": 0.55,
            "requires_validation": True,
        },
    ],
    "response_quality_low": [
        {
            "target": "prompt_update",
            "action": "add_discipline_instructions",
            "impact": 0.50,
            "risk": 0.30,
            "requires_validation": False,
        },
    ],
    "agent_inconsistency": [
        {
            "target": "agent_behavior",
            "action": "align_output_structure",
            "impact": 0.35,
            "risk": 0.25,
            "requires_validation": False,
        },
    ],
    "recurring_discipline_error": [
        {
            "target": "prompt_update",
            "action": "discipline_specific_tuning",
            "impact": 0.55,
            "risk": 0.35,
            "requires_validation": False,
        },
        {
            "target": "router_weights",
            "action": "refine_routing_rules",
            "impact": 0.40,
            "risk": 0.30,
            "requires_validation": False,
        },
    ],
    "low_final_score": [
        {
            "target": "prompt_update",
            "action": "holistic_prompt_improvement",
            "impact": 0.45,
            "risk": 0.35,
            "requires_validation": False,
        },
    ],
}


@dataclass
class StrategyDecision:
    target: str
    action: str
    impact: float
    risk: float
    requires_validation: bool
    disciplines: list[str] = field(default_factory=list)
    source_finding: str = ""
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "action": self.action,
            "impact": self.impact,
            "risk": self.risk,
            "requires_validation": self.requires_validation,
            "disciplines": self.disciplines,
            "source_finding": self.source_finding,
            "rationale": self.rationale,
        }


def decide_strategies(
    analysis: MetaAnalysis,
    *,
    risk_threshold: float = 0.7,
) -> list[StrategyDecision]:
    """
    Decide o que pode ser ajustado com base nas findings.
    Filtra estratégias acima do limiar de risco configurável.
    """
    decisions: list[StrategyDecision] = []
    seen: set[tuple[str, str]] = set()

    for finding in analysis.findings:
        templates = STRATEGY_MAP.get(finding.failure_type, [])
        for tmpl in templates:
            if tmpl["risk"] > risk_threshold:
                continue
            key = (tmpl["target"], tmpl["action"])
            if key in seen:
                continue
            seen.add(key)

            decisions.append(StrategyDecision(
                target=tmpl["target"],
                action=tmpl["action"],
                impact=tmpl["impact"],
                risk=tmpl["risk"],
                requires_validation=tmpl.get("requires_validation", False),
                disciplines=finding.disciplines or analysis.disciplines,
                source_finding=finding.failure_type,
                rationale=finding.description,
            ))

    decisions.sort(key=lambda d: d.impact - d.risk, reverse=True)
    return decisions
