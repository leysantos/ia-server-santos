"""
System Classifier — ponto de entrada do Structural System Selector.

Identifica sistema estrutural, normas e módulo de simulação antes do Engineering Simulator.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from core.aed.project_understanding import ProjectUnderstanding
from core.structural_selector.llm_fallback_selector import (
    select_by_llm,
    should_use_llm_fallback,
)
from core.structural_selector.norms_mapper import get_norm_set, merge_with_discipline_norms
from core.structural_selector.rules_based_selector import select_by_rules
from core.structural_selector.system_registry import (
    StructuralSystem,
    get_system_info,
)

logger = logging.getLogger(__name__)

STRUCTURAL_DISCIPLINE = "ESTRUTURAL"


@dataclass
class StructuralSelection:
    structural_system: str
    norm_set: list[str]
    simulation_module: str
    confidence: float
    method: str  # "rules" | "llm_fallback" | "skipped"
    rationale: list[str] = field(default_factory=list)
    rules_scores: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "structural_system": self.structural_system,
            "norm_set": self.norm_set,
            "simulation_module": self.simulation_module,
            "confidence": self.confidence,
            "method": self.method,
            "rationale": self.rationale,
            "rules_scores": self.rules_scores,
        }


def select_structural_system(
    understanding: ProjectUnderstanding,
    *,
    use_llm_fallback: bool = True,
) -> StructuralSelection | None:
    """
    Seleciona sistema estrutural adequado quando a disciplina ESTRUTURAL está presente.

    Retorna None se o projeto não envolve estrutura — módulo permanece plugável.
    """
    if STRUCTURAL_DISCIPLINE not in understanding.disciplines:
        return None

    rules_result = select_by_rules(understanding)
    system = rules_result.system
    confidence = rules_result.confidence
    method = "rules"
    rationale = list(rules_result.rationale)

    if use_llm_fallback and should_use_llm_fallback(rules_result.confidence, rules_result.ambiguous):
        llm_system, llm_confidence, raw = select_by_llm(understanding)
        if llm_confidence >= rules_result.confidence:
            system = llm_system
            confidence = llm_confidence
            method = "llm_fallback"
            rationale.append(f"LLM fallback selecionou {system.value} (conf={llm_confidence})")
            if raw:
                rationale.append(f"Resposta LLM: {raw[:120]}")

    info = get_system_info(system)
    discipline_norms = understanding.normas.get(STRUCTURAL_DISCIPLINE, [])
    norm_set = merge_with_discipline_norms(system, discipline_norms)

    selection = StructuralSelection(
        structural_system=system.value,
        norm_set=norm_set,
        simulation_module=info["simulation_module"],
        confidence=confidence,
        method=method,
        rationale=rationale,
        rules_scores=rules_result.scores,
    )

    logger.info(
        "structural_selector system=%s module=%s method=%s conf=%.2f",
        selection.structural_system,
        selection.simulation_module,
        selection.method,
        selection.confidence,
    )

    return selection
