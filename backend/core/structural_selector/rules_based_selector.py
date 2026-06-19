"""
Rules-based selector — heurísticas determinísticas para sistema estrutural.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.aed.project_understanding import ProjectUnderstanding
from core.structural_selector.system_registry import StructuralSystem

# (sistema, keywords, peso)
HEURISTIC_RULES: list[tuple[StructuralSystem, list[str], float]] = [
    # grandes vãos → steel
    (
        StructuralSystem.STEEL_STRUCTURE,
        ["grande vão", "grande vao", "vão livre", "vao livre", "long span", "vão longo", "vao longo"],
        2.5,
    ),
    # residencial → concrete
    (
        StructuralSystem.CONCRETE_ARMED,
        ["residencial", "habitacional", "apartamento", "prédio residencial", "predio residencial"],
        2.5,
    ),
    # industrial → steel / precast
    (
        StructuralSystem.STEEL_STRUCTURE,
        ["industrial", "galpão", "galpao", "fabrica", "fábrica"],
        1.8,
    ),
    (
        StructuralSystem.PRECAST_CONCRETE,
        ["industrial", "galpão", "galpao", "pré-moldado", "pre-moldado", "precast"],
        1.8,
    ),
    # baixa altura → concrete
    (
        StructuralSystem.CONCRETE_ARMED,
        ["baixa altura", "térreo", "terreo", "pavimento térreo", "2 pavimentos", "sobrado"],
        1.8,
    ),
    # leveza estrutural → steel / timber
    (
        StructuralSystem.STEEL_STRUCTURE,
        ["leveza", "estrutura leve", "leve", "peso reduzido"],
        1.5,
    ),
    (
        StructuralSystem.TIMBER_STRUCTURE,
        ["leveza", "estrutura leve", "madeira", "timber", "sustentável", "sustentavel"],
        1.5,
    ),
    # protensão
    (
        StructuralSystem.CONCRETE_PRESTRESSED,
        ["protensão", "protensao", "prestress", "cabos", "laje protendida"],
        2.0,
    ),
    # pré-moldado explícito
    (
        StructuralSystem.PRECAST_CONCRETE,
        ["pré-moldado", "pre-moldado", "precast", "painel pré-fabricado"],
        2.2,
    ),
    # aço explícito
    (
        StructuralSystem.STEEL_STRUCTURE,
        ["aço estrutural", "aco estrutural", "metálica", "metalica", "treliça", "trelica"],
        2.2,
    ),
    # madeira explícita
    (
        StructuralSystem.TIMBER_STRUCTURE,
        ["madeira", "clt", "estrutura de madeira"],
        2.2,
    ),
    # concreto armado explícito
    (
        StructuralSystem.CONCRETE_ARMED,
        ["concreto armado", "viga de concreto", "pilar de concreto"],
        2.0,
    ),
]

PROJECT_TYPE_BIAS: dict[str, list[tuple[StructuralSystem, float]]] = {
    "residencial": [(StructuralSystem.CONCRETE_ARMED, 2.0)],
    "industrial": [
        (StructuralSystem.STEEL_STRUCTURE, 1.5),
        (StructuralSystem.PRECAST_CONCRETE, 1.5),
    ],
    "comercial": [(StructuralSystem.CONCRETE_ARMED, 1.0), (StructuralSystem.STEEL_STRUCTURE, 0.8)],
    "infraestrutura": [
        (StructuralSystem.CONCRETE_PRESTRESSED, 1.5),
        (StructuralSystem.STEEL_STRUCTURE, 1.2),
    ],
}


@dataclass
class RulesSelectionResult:
    system: StructuralSystem
    confidence: float
    scores: dict[str, float] = field(default_factory=dict)
    rationale: list[str] = field(default_factory=list)
    ambiguous: bool = False


def select_by_rules(understanding: ProjectUnderstanding) -> RulesSelectionResult:
    """Aplica heurísticas sobre o entendimento do projeto."""
    text = understanding.input_text.lower()
    scores: dict[StructuralSystem, float] = {s: 0.0 for s in StructuralSystem if s != StructuralSystem.MIXED_SYSTEMS}
    rationale: list[str] = []

    for system, keywords, weight in HEURISTIC_RULES:
        for kw in keywords:
            if kw in text:
                scores[system] += weight
                rationale.append(f"Regra '{kw}' → {system.value} (+{weight})")
                break

    for system, weight in PROJECT_TYPE_BIAS.get(understanding.project_type, []):
        scores[system] += weight
        rationale.append(
            f"Tipo de projeto '{understanding.project_type}' → {system.value} (+{weight})"
        )

    if "ESTRUTURAL" in understanding.disciplines and max(scores.values()) == 0:
        scores[StructuralSystem.CONCRETE_ARMED] += 1.0
        rationale.append("Fallback disciplina estrutural sem sinais → CONCRETE_ARMED (+1.0)")

    sorted_systems = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_system, top_score = sorted_systems[0]
    second_score = sorted_systems[1][1] if len(sorted_systems) > 1 else 0.0

    ambiguous = top_score > 0 and (top_score - second_score) < 0.8
    if ambiguous:
        top_system = StructuralSystem.MIXED_SYSTEMS
        rationale.append(
            f"Sinais conflitantes (top={top_score:.1f}, second={second_score:.1f}) → MIXED_SYSTEMS"
        )

    total = sum(scores.values()) or 1.0
    confidence = min(1.0, top_score / total) if top_score > 0 else 0.4

    return RulesSelectionResult(
        system=top_system,
        confidence=round(confidence, 3),
        scores={s.value: round(v, 2) for s, v in scores.items()},
        rationale=rationale,
        ambiguous=ambiguous,
    )
