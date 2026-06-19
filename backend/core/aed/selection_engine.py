"""
Selection Engine — seleciona melhor solução com weighted scoring e penalidades de risco.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from core.aed.comparison_engine import ComparisonEntry, ComparisonMatrix
from core.aed.design_generator import DesignOption
from core.aed.engineering_simulator import SimulationResult
from core.aed.project_understanding import ProjectUnderstanding

DEFAULT_WEIGHTS = {
    "safety": 0.30,
    "cost": 0.20,
    "execution": 0.20,
    "maintenance": 0.10,
    "compliance": 0.20,
}

CONSTRAINT_WEIGHT_BOOST = {
    "custo": {"cost": 0.15},
    "prazo": {"execution": 0.15},
    "normativo": {"compliance": 0.15, "safety": 0.10},
    "sustentabilidade": {"maintenance": 0.10, "cost": 0.05},
}

RISK_PENALTIES = {
    "optimized": 0.05,
    "value_engineering": 0.06,
    "alternative": 0.04,
    "enhanced": 0.03,
}


@dataclass
class SelectionResult:
    selected_option_id: str
    discipline: str
    name: str
    weighted_score: float
    risk_penalty: float
    final_selection_score: float
    justification: str
    alternatives: list[str] = field(default_factory=list)
    per_discipline_winners: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_option_id": self.selected_option_id,
            "discipline": self.discipline,
            "name": self.name,
            "weighted_score": round(self.weighted_score, 3),
            "risk_penalty": round(self.risk_penalty, 3),
            "final_selection_score": round(self.final_selection_score, 3),
            "justification": self.justification,
            "alternatives": self.alternatives,
            "per_discipline_winners": self.per_discipline_winners,
        }


def select_best_solution(
    understanding: ProjectUnderstanding,
    designs: list[DesignOption],
    comparison: ComparisonMatrix,
    simulations: list[SimulationResult],
) -> SelectionResult:
    """Seleciona solução global e vencedores por disciplina."""
    weights = _adjust_weights(understanding.constraints)
    design_map = {d.option_id: d for d in designs}
    sim_map = {s.option_id: s for s in simulations}

    scored: list[tuple[ComparisonEntry, float, float]] = []
    for entry in comparison.entries:
        design = design_map.get(entry.option_id)
        wscore = (
            weights["safety"] * entry.safety
            + weights["cost"] * entry.cost
            + weights["execution"] * entry.execution
            + weights["maintenance"] * entry.maintenance
            + weights["compliance"] * entry.compliance
        )
        penalty = RISK_PENALTIES.get(design.variant, 0.0) if design else 0.0
        final = max(0.0, wscore - penalty)
        scored.append((entry, wscore, penalty, final))

    scored.sort(key=lambda x: x[3], reverse=True)
    winner_entry, wscore, penalty, final = scored[0]

    per_discipline: dict[str, str] = {}
    for disc, entries in comparison.by_discipline.items():
        if entries:
            per_discipline[disc] = entries[0].option_id

    alternatives = [e.option_id for e, _, _, _ in scored[1:4]]
    winner_design = design_map[winner_entry.option_id]
    winner_sim = sim_map.get(winner_entry.option_id)

    justification = _build_justification(
        winner_design, winner_entry, winner_sim, understanding, weights
    )

    return SelectionResult(
        selected_option_id=winner_entry.option_id,
        discipline=winner_entry.discipline,
        name=winner_entry.name,
        weighted_score=wscore,
        risk_penalty=penalty,
        final_selection_score=final,
        justification=justification,
        alternatives=alternatives,
        per_discipline_winners=per_discipline,
    )


def _adjust_weights(constraints: list[str]) -> dict[str, float]:
    weights = dict(DEFAULT_WEIGHTS)
    for constraint in constraints:
        boosts = CONSTRAINT_WEIGHT_BOOST.get(constraint, {})
        for key, delta in boosts.items():
            weights[key] = weights.get(key, 0) + delta
    total = sum(weights.values())
    return {k: v / total for k, v in weights.items()}


def _build_justification(
    design: DesignOption,
    entry: ComparisonEntry,
    sim: Optional[SimulationResult],
    understanding: ProjectUnderstanding,
    weights: dict[str, float],
) -> str:
    parts = [
        f"Solução '{design.name}' selecionada para {design.discipline}.",
        f"Abordagem: {design.approach}.",
        f"Scores — segurança: {entry.safety:.2f}, custo: {entry.cost:.2f}, "
        f"execução: {entry.execution:.2f}, compliance: {entry.compliance:.2f}.",
    ]
    if sim and sim.normas_cited:
        parts.append(f"Normas referenciadas: {', '.join(sim.normas_cited[:5])}.")
    if understanding.constraints:
        parts.append(f"Pesos ajustados para restrições: {', '.join(understanding.constraints)}.")
    return " ".join(parts)
