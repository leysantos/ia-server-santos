"""
Intent Evaluator — avalia precisão da classificação de intenção do Copilot.
"""

from __future__ import annotations

import re
from typing import Any

from core.copilot.intent_analyzer import INTENT_KEYWORDS, analyze_intent
from core.evaluation_v2.quality_metrics import StageScore, clamp_score

BUILDING_TRIGGERS = ["prédio", "predio", "edific", "residencial", "comercial"]


def evaluate_intent(copilot_output: dict[str, Any]) -> StageScore:
    """
    Compara intent reportado com re-análise rule-based do input.
    """
    input_text = copilot_output.get("input", "")
    reported_intent = copilot_output.get("intent", "general")
    reported_confidence = float(copilot_output.get("intent_confidence", 0.5))
    matched_categories = copilot_output.get("matched_categories", [])

    issues: list[str] = []
    factors: dict[str, float] = {}

    if not input_text.strip():
        return StageScore(
            name="intent_accuracy",
            score=0.0,
            issues=["input_text vazio"],
        )

    reanalysis = analyze_intent(input_text)
    factors["reanalysis_confidence"] = reanalysis.confidence

    # Consistência intent reportado vs re-análise
    intent_match = 1.0 if reanalysis.intent == reported_intent else 0.4
    factors["intent_consistency"] = intent_match
    if intent_match < 1.0:
        issues.append(
            f"intent divergente: reportado={reported_intent}, esperado={reanalysis.intent}"
        )

    # Confiança reportada
    confidence_score = min(1.0, reported_confidence)
    factors["confidence"] = confidence_score
    if reported_confidence < 0.5:
        issues.append(f"confiança de intent baixa ({reported_confidence})")

    # Alinhamento keywords ↔ categorias
    normalized = re.sub(r"\s+", " ", input_text.lower().strip())
    keyword_hits = 0
    for cat in matched_categories:
        keywords = INTENT_KEYWORDS.get(cat, [])
        keyword_hits += sum(1 for kw in keywords if kw in normalized)
    keyword_alignment = min(1.0, keyword_hits / max(len(matched_categories), 1))
    factors["keyword_alignment"] = round(keyword_alignment, 3)

    # Coerência building → multi_discipline
    is_building = any(t in normalized for t in BUILDING_TRIGGERS)
    building_coherence = 1.0
    if is_building and reported_intent != "multi_discipline":
        building_coherence = 0.5
        issues.append("input de edificação deveria ser multi_discipline")
    factors["building_coherence"] = building_coherence

    score = clamp_score(
        0.35 * intent_match
        + 0.25 * confidence_score
        + 0.20 * keyword_alignment
        + 0.20 * building_coherence
    )

    return StageScore(
        name="intent_accuracy",
        score=score,
        issues=issues,
        factors=factors,
    )
