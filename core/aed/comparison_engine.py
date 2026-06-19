"""
Comparison Engine — compara soluções em segurança, custo, execução, manutenção e compliance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.aed.design_generator import DesignOption
from core.aed.engineering_simulator import SimulationResult

VARIANT_SCORES: dict[str, dict[str, float]] = {
    "conservative": {"safety": 0.95, "cost": 0.55, "execution": 0.75, "maintenance": 0.80},
    "minimum": {"safety": 0.85, "cost": 0.70, "execution": 0.85, "maintenance": 0.75},
    "basic": {"safety": 0.80, "cost": 0.75, "execution": 0.85, "maintenance": 0.70},
    "reference": {"safety": 0.75, "cost": 0.80, "execution": 0.80, "maintenance": 0.75},
    "standard": {"safety": 0.82, "cost": 0.72, "execution": 0.78, "maintenance": 0.78},
    "conventional": {"safety": 0.85, "cost": 0.70, "execution": 0.80, "maintenance": 0.75},
    "optimized": {"safety": 0.75, "cost": 0.90, "execution": 0.65, "maintenance": 0.70},
    "enhanced": {"safety": 0.90, "cost": 0.60, "execution": 0.70, "maintenance": 0.85},
    "alternative": {"safety": 0.78, "cost": 0.85, "execution": 0.72, "maintenance": 0.72},
    "value_engineering": {"safety": 0.72, "cost": 0.92, "execution": 0.68, "maintenance": 0.68},
    "flexible": {"safety": 0.78, "cost": 0.78, "execution": 0.75, "maintenance": 0.80},
}


@dataclass
class ComparisonEntry:
    option_id: str
    discipline: str
    name: str
    safety: float
    cost: float
    execution: float
    maintenance: float
    compliance: float
    simulation_score: float
    composite: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "option_id": self.option_id,
            "discipline": self.discipline,
            "name": self.name,
            "safety": round(self.safety, 3),
            "cost": round(self.cost, 3),
            "execution": round(self.execution, 3),
            "maintenance": round(self.maintenance, 3),
            "compliance": round(self.compliance, 3),
            "simulation_score": round(self.simulation_score, 3),
            "composite": round(self.composite, 3),
        }


@dataclass
class ComparisonMatrix:
    entries: list[ComparisonEntry] = field(default_factory=list)
    by_discipline: dict[str, list[ComparisonEntry]] = field(default_factory=dict)
    rankings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entries": [e.to_dict() for e in self.entries],
            "by_discipline": {
                d: [e.to_dict() for e in entries]
                for d, entries in self.by_discipline.items()
            },
            "rankings": self.rankings,
        }


def compare_solutions(
    designs: list[DesignOption],
    simulations: list[SimulationResult],
) -> ComparisonMatrix:
    """Compara todas as soluções em 5 dimensões + score de simulação."""
    sim_map = {s.option_id: s for s in simulations}
    entries: list[ComparisonEntry] = []

    for design in designs:
        sim = sim_map.get(design.option_id)
        if not sim:
            continue

        variant_scores = VARIANT_SCORES.get(design.variant, VARIANT_SCORES["standard"])
        safety = variant_scores["safety"] * 0.6 + sim.compliance_score * 0.4
        cost = variant_scores["cost"]
        execution = variant_scores["execution"] * 0.7 + sim.heuristic_score * 0.3
        maintenance = variant_scores["maintenance"]
        compliance = sim.compliance_score

        composite = (
            0.30 * safety
            + 0.20 * cost
            + 0.20 * execution
            + 0.15 * maintenance
            + 0.15 * compliance
        )

        entries.append(ComparisonEntry(
            option_id=design.option_id,
            discipline=design.discipline,
            name=design.name,
            safety=safety,
            cost=cost,
            execution=execution,
            maintenance=maintenance,
            compliance=compliance,
            simulation_score=sim.final_simulation_score,
            composite=composite,
        ))

    entries.sort(key=lambda e: e.composite, reverse=True)
    by_discipline: dict[str, list[ComparisonEntry]] = {}
    for entry in entries:
        by_discipline.setdefault(entry.discipline, []).append(entry)

    return ComparisonMatrix(
        entries=entries,
        by_discipline=by_discipline,
        rankings=[e.option_id for e in entries],
    )
