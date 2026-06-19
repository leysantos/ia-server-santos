"""
Response Evaluator — avalia qualidade da resposta final sintetizada.
"""

from __future__ import annotations

import re
from typing import Any

from core.evaluation_v2.quality_metrics import StageScore, clamp_score

NBR_PATTERN = re.compile(r"NBR\s*\d+", re.IGNORECASE)
MIN_CONTENT_LENGTH = 80
STRUCTURE_MARKERS = ["##", "###", "Análise", "Premissas", "Recomendações", "Conclusão"]


def evaluate_response(copilot_output: dict[str, Any]) -> StageScore:
    """Avalia profundidade, estrutura e cobertura da resposta consolidada."""
    result = copilot_output.get("result") or {}
    plan = copilot_output.get("plan") or []
    disciplines = copilot_output.get("disciplines") or []
    v1_eval = copilot_output.get("evaluation") or {}
    issues: list[str] = []
    factors: dict[str, float] = {}

    final_report = result.get("final_report") or ""
    technical_summary = result.get("technical_summary") or ""
    by_discipline = result.get("by_discipline") or {}
    combined = final_report + technical_summary

    if not combined.strip():
        return StageScore(
            name="response_quality",
            score=0.0,
            issues=["resposta final vazia"],
        )

    # Profundidade de conteúdo
    contents = [
        (by_discipline.get(d) or {}).get("content", "")
        for d in disciplines
    ]
    if not contents:
        contents = [combined]

    depth_scores = [
        1.0 if len(c) >= MIN_CONTENT_LENGTH else len(c) / MIN_CONTENT_LENGTH
        for c in contents
    ]
    content_depth = sum(depth_scores) / max(len(depth_scores), 1)
    factors["content_depth"] = round(content_depth, 3)
    if content_depth < 0.5:
        issues.append("respostas superficiais (conteúdo curto)")

    # Cobertura por disciplina
    covered = sum(
        1 for d in disciplines
        if (by_discipline.get(d) or {}).get("content", "").strip()
    )
    discipline_coverage = covered / max(len(disciplines), 1)
    factors["discipline_coverage"] = round(discipline_coverage, 3)
    if discipline_coverage < 1.0:
        missing = [d for d in disciplines if d not in by_discipline]
        issues.append(f"disciplinas sem resposta: {', '.join(missing)}")

    # Estrutura técnica
    structure_hits = sum(1 for m in STRUCTURE_MARKERS if m in combined)
    structure_score = min(1.0, structure_hits / 3)
    factors["structure"] = round(structure_score, 3)

    # Referências normativas
    nbr_count = len(NBR_PATTERN.findall(combined))
    normative = min(1.0, nbr_count / max(len(disciplines), 1))
    factors["normative_references"] = round(normative, 3)
    if normative < 0.3 and copilot_output.get("intent") != "general":
        issues.append("poucas citações normativas (NBR) na resposta")

    # Consistência com avaliação Copilot v1 (se presente)
    v1_score = v1_eval.get("score")
    if v1_score is not None:
        factors["copilot_v1_score"] = round(float(v1_score), 3)

    # Erros reportados na síntese
    error_steps = result.get("error_steps", 0)
    error_penalty = 1.0 - (error_steps / max(len(plan), 1))
    factors["synthesis_error_penalty"] = round(max(0.0, error_penalty), 3)
    if error_steps > 0:
        issues.append(f"síntese reporta {error_steps} etapa(s) com erro")

    v1_component = float(v1_score) if v1_score is not None else content_depth

    score = clamp_score(
        0.30 * content_depth
        + 0.25 * discipline_coverage
        + 0.20 * structure_score
        + 0.15 * normative
        + 0.10 * v1_component
    )

    return StageScore(
        name="response_quality",
        score=score,
        issues=issues,
        factors=factors,
    )
