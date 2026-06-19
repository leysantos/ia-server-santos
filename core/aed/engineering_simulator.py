"""
Engineering Simulator — avalia soluções via RAG v2, heurísticas e histórico PostgreSQL.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from core.aed.design_generator import DesignOption
from core.aed.project_understanding import ProjectUnderstanding
from memory.rag_engine import get_rag_engine

if TYPE_CHECKING:
    from core.structural_selector.system_classifier import StructuralSelection

logger = logging.getLogger(__name__)

NBR_PATTERN = re.compile(r"NBR\s*\d+", re.IGNORECASE)


@dataclass
class SimulationResult:
    option_id: str
    discipline: str
    technical_score: float
    rag_score: float
    heuristic_score: float
    history_score: float
    compliance_score: float
    final_simulation_score: float
    rag_context_length: int
    structural_system: str | None = None
    simulation_module: str | None = None
    normas_cited: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "option_id": self.option_id,
            "discipline": self.discipline,
            "technical_score": round(self.technical_score, 3),
            "rag_score": round(self.rag_score, 3),
            "heuristic_score": round(self.heuristic_score, 3),
            "history_score": round(self.history_score, 3),
            "compliance_score": round(self.compliance_score, 3),
            "final_simulation_score": round(self.final_simulation_score, 3),
            "rag_context_length": self.rag_context_length,
            "structural_system": self.structural_system,
            "simulation_module": self.simulation_module,
            "normas_cited": self.normas_cited,
            "notes": self.notes,
        }


def simulate_designs(
    understanding: ProjectUnderstanding,
    designs: list[DesignOption],
    *,
    use_rag: bool = True,
    structural_selection: "StructuralSelection | None" = None,
) -> list[SimulationResult]:
    """Simula e pontua cada opção de design."""
    history = _load_historical_scores(understanding.disciplines)
    results: list[SimulationResult] = []

    for design in designs:
        results.append(
            _simulate_one(
                understanding,
                design,
                history=history,
                use_rag=use_rag,
                structural_selection=structural_selection,
            )
        )

    return results


def _simulate_one(
    understanding: ProjectUnderstanding,
    design: DesignOption,
    *,
    history: dict[str, float],
    use_rag: bool,
    structural_selection: "StructuralSelection | None" = None,
) -> SimulationResult:
    notes: list[str] = []
    query = f"{understanding.input_text} {design.approach} {design.materials}"

    structural_system: str | None = None
    simulation_module: str | None = None
    if structural_selection and design.discipline == "ESTRUTURAL":
        structural_system = structural_selection.structural_system
        simulation_module = structural_selection.simulation_module
        query = f"{query} {structural_system} {' '.join(structural_selection.norm_set)}"
        notes.append(
            f"Sistema estrutural: {structural_system} → módulo {simulation_module}"
        )

    rag_context = ""
    rag_context_length = 0
    if use_rag:
        try:
            rag_context = get_rag_engine().build_context(
                query=query,
                discipline=design.discipline,
                doc_type="nbr",
            )
            rag_context_length = len(rag_context)
        except Exception as exc:
            logger.warning("AED: RAG indisponível discipline=%s: %s", design.discipline, exc)
            notes.append("RAG indisponível — score normativo reduzido")

    rag_score = min(1.0, rag_context_length / 500) if use_rag else 0.5
    if rag_context_length == 0 and use_rag:
        rag_score = 0.3
        notes.append("Sem contexto RAG recuperado")

    normas_expected = understanding.normas.get(design.discipline, [])
    if structural_selection and design.discipline == "ESTRUTURAL":
        normas_expected = list(
            dict.fromkeys(structural_selection.norm_set + normas_expected)
        )
    normas_in_context = NBR_PATTERN.findall(rag_context) if rag_context else []
    normas_in_design = NBR_PATTERN.findall(design.description)
    normas_cited = list(dict.fromkeys(normas_in_context + normas_in_design))

    compliance_score = _compliance_score(normas_expected, normas_cited, design)
    heuristic_score = _heuristic_score(
        design, understanding, structural_system=structural_system
    )
    history_score = history.get(design.discipline, 0.6)
    technical_score = (heuristic_score + compliance_score) / 2

    final = (
        0.25 * rag_score
        + 0.25 * heuristic_score
        + 0.20 * compliance_score
        + 0.15 * history_score
        + 0.15 * technical_score
    )

    if design.variant in ("conservative", "minimum", "basic", "reference", "standard"):
        notes.append("Variante conservadora — maior margem de segurança")
    if design.variant in ("optimized", "enhanced", "value_engineering"):
        notes.append("Variante otimizada — requer validação detalhada")

    return SimulationResult(
        option_id=design.option_id,
        discipline=design.discipline,
        technical_score=technical_score,
        rag_score=rag_score,
        heuristic_score=heuristic_score,
        history_score=history_score,
        compliance_score=compliance_score,
        final_simulation_score=min(1.0, final),
        rag_context_length=rag_context_length,
        structural_system=structural_system,
        simulation_module=simulation_module,
        normas_cited=normas_cited,
        notes=notes,
    )


def _compliance_score(
    expected_normas: list[str],
    cited: list[str],
    design: DesignOption,
) -> float:
    if not expected_normas:
        return 0.7
    hits = 0
    for norma in expected_normas:
        code = NBR_PATTERN.search(norma)
        if code and any(code.group() in c for c in cited):
            hits += 1
        elif norma.lower() in design.description.lower():
            hits += 0.5
    return min(1.0, hits / len(expected_normas) + 0.3)


def _heuristic_score(
    design: DesignOption,
    understanding: ProjectUnderstanding,
    *,
    structural_system: str | None = None,
) -> float:
    score = 0.6
    if structural_system and design.discipline == "ESTRUTURAL":
        score += _structural_alignment_bonus(design, structural_system)
    if "custo" in understanding.constraints and design.variant in (
        "optimized", "value_engineering", "alternative",
    ):
        score += 0.15
    if "normativo" in understanding.constraints and design.variant in (
        "conservative", "minimum", "standard", "reference",
    ):
        score += 0.15
    if len(design.premissas) >= 2:
        score += 0.1
    if len(design.description) > 80:
        score += 0.05
    return min(1.0, score)


def _structural_alignment_bonus(design: DesignOption, structural_system: str) -> float:
    """Bônus quando materiais/abordagem alinham com o sistema selecionado."""
    blob = f"{design.approach} {design.materials} {design.description}".lower()
    alignment: dict[str, list[str]] = {
        "CONCRETE_ARMED": ["concreto", "armado", "ca-50", "ca-60"],
        "CONCRETE_PRESTRESSED": ["protend", "protens", "cabos"],
        "PRECAST_CONCRETE": ["pré-moldado", "pre-moldado", "precast", "industrializado"],
        "STEEL_STRUCTURE": ["aço", "aco", "metálic", "metalic", "treliça", "trelica"],
        "TIMBER_STRUCTURE": ["madeira", "timber", "clt"],
        "MIXED_SYSTEMS": ["misto", "híbrid", "hibrid"],
    }
    keywords = alignment.get(structural_system, [])
    hits = sum(1 for kw in keywords if kw in blob)
    if hits == 0:
        return 0.0
    return min(0.15, hits * 0.05)


def _load_historical_scores(disciplines: list[str]) -> dict[str, float]:
    """Lê histórico PostgreSQL (copilot_evaluations, system_failures) — read-only."""
    scores: dict[str, float] = {}
    try:
        from core.database.connection import is_db_enabled, session_scope
        from core.database.repository import DatabaseRepository

        if not is_db_enabled():
            return {d: 0.6 for d in disciplines}

        with session_scope() as session:
            repo = DatabaseRepository(session)
            evals = repo.list_copilot_evaluations(limit=50)
            failures = repo.list_system_failures(limit=100)

        failure_disciplines: dict[str, int] = {}
        for f in failures:
            route = f.route_decision or {}
            for d in route.get("disciplines") or [route.get("discipline")]:
                if d:
                    failure_disciplines[d] = failure_disciplines.get(d, 0) + 1

        avg_final = (
            sum(e.final_score for e in evals) / len(evals) if evals else 0.65
        )

        for d in disciplines:
            penalty = min(0.3, failure_disciplines.get(d, 0) * 0.05)
            scores[d] = max(0.3, min(1.0, avg_final - penalty))
    except Exception as exc:
        logger.debug("AED: histórico indisponível: %s", exc)
        scores = {d: 0.6 for d in disciplines}

    return scores
