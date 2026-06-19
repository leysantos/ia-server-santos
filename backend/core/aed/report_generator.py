"""
Report Generator — relatório técnico estruturado do AED v1.
"""

from __future__ import annotations

from typing import Any

from core.aed.comparison_engine import ComparisonMatrix
from core.aed.design_generator import DesignOption
from core.aed.engineering_simulator import SimulationResult
from core.aed.project_understanding import ProjectUnderstanding
from core.aed.selection_engine import SelectionResult


def generate_report(
    understanding: ProjectUnderstanding,
    designs: list[DesignOption],
    simulations: list[SimulationResult],
    comparison: ComparisonMatrix,
    selection: SelectionResult,
) -> dict[str, Any]:
    """Gera relatório técnico com solução escolhida, alternativas e riscos."""
    design_map = {d.option_id: d for d in designs}
    sim_map = {s.option_id: s for s in simulations}
    winner = design_map[selection.selected_option_id]
    winner_sim = sim_map.get(selection.selected_option_id)

    alternatives_section = _alternatives_section(
        selection.alternatives, design_map, sim_map
    )
    risks = _identify_risks(winner, winner_sim, understanding)
    normas = _collect_normas(understanding, winner_sim)

    final_report = _build_markdown_report(
        understanding, winner, winner_sim, selection, alternatives_section, risks, normas
    )

    return {
        "final_report": final_report,
        "selected_solution": winner.to_dict(),
        "selection": selection.to_dict(),
        "alternatives": alternatives_section,
        "normas_aplicadas": normas,
        "risks": risks,
        "comparison_summary": comparison.to_dict(),
        "disciplines_analyzed": understanding.disciplines,
        "designs_count": len(designs),
    }


def _alternatives_section(
    alt_ids: list[str],
    design_map: dict[str, DesignOption],
    sim_map: dict[str, SimulationResult],
) -> list[dict[str, Any]]:
    alts = []
    for oid in alt_ids:
        d = design_map.get(oid)
        s = sim_map.get(oid)
        if d:
            alts.append({
                "option_id": oid,
                "name": d.name,
                "discipline": d.discipline,
                "approach": d.approach,
                "simulation_score": s.final_simulation_score if s else None,
            })
    return alts


def _identify_risks(
    winner: DesignOption,
    sim: SimulationResult | None,
    understanding: ProjectUnderstanding,
) -> list[str]:
    risks: list[str] = []
    if winner.variant in ("optimized", "value_engineering", "alternative"):
        risks.append("Variante otimizada requer validação de cálculo detalhado")
    if sim and sim.rag_context_length == 0:
        risks.append("Contexto normativo RAG ausente — validar NBRs manualmente")
    if sim and sim.compliance_score < 0.6:
        risks.append("Compliance normativo abaixo do ideal")
    if understanding.intent == "multi_discipline":
        risks.append("Integração multidisciplinar requer compatibilização de projetos")
    if not risks:
        risks.append("Riscos dentro de parâmetros preliminares — revisão por engenheiro responsável")
    return risks


def _collect_normas(
    understanding: ProjectUnderstanding,
    sim: SimulationResult | None,
) -> list[str]:
    normas: list[str] = []
    for disc in understanding.disciplines:
        normas.extend(understanding.normas.get(disc, []))
    if sim:
        normas.extend(sim.normas_cited)
    return list(dict.fromkeys(normas))


def _build_markdown_report(
    understanding,
    winner,
    sim,
    selection,
    alternatives,
    risks,
    normas,
) -> str:
    lines = [
        "# Relatório AED v1 — Autonomous Engineering Designer",
        "",
        f"**Projeto:** {understanding.input_text}",
        f"**Tipo:** {understanding.project_type} | **Intent:** {understanding.intent}",
        f"**Disciplinas:** {', '.join(understanding.disciplines)}",
        "",
        "## Solução selecionada",
        "",
        f"### {winner.name} ({winner.discipline})",
        "",
        winner.description,
        "",
        f"**Justificativa:** {selection.justification}",
        "",
        "## Premissas",
        "",
    ]
    for p in winner.premissas:
        lines.append(f"- {p}")

    lines.extend(["", "## Normas aplicadas", ""])
    for n in normas[:10]:
        lines.append(f"- {n}")

    lines.extend(["", "## Alternativas analisadas", ""])
    for alt in alternatives:
        score = alt.get("simulation_score")
        score_txt = f" (score: {score:.2f})" if score is not None else ""
        lines.append(f"- **{alt['name']}** [{alt['discipline']}]{score_txt}: {alt['approach']}")

    lines.extend(["", "## Riscos identificados", ""])
    for r in risks:
        lines.append(f"- ⚠ {r}")

    lines.extend([
        "",
        "## Objetivos do projeto",
        "",
    ])
    for obj in understanding.objectives:
        lines.append(f"- {obj}")

    if sim:
        lines.extend([
            "",
            "## Scores de simulação (solução escolhida)",
            "",
            f"- Score final: {sim.final_simulation_score:.3f}",
            f"- RAG: {sim.rag_score:.3f} | Heurística: {sim.heuristic_score:.3f}",
            f"- Compliance: {sim.compliance_score:.3f} | Histórico: {sim.history_score:.3f}",
        ])

    lines.extend([
        "",
        "---",
        "*Relatório gerado automaticamente pelo AED v1. Requer validação por engenheiro responsável.*",
    ])

    return "\n".join(lines)
