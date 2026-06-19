"""
Métricas e utilitários compartilhados — Evaluation Loop v2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Pesos para final_score
SCORE_WEIGHTS = {
    "intent_accuracy": 0.15,
    "plan_quality": 0.20,
    "execution_completeness": 0.30,
    "response_quality": 0.35,
}

ISSUE_THRESHOLD = 0.6


@dataclass
class StageScore:
    name: str
    score: float
    issues: list[str] = field(default_factory=list)
    factors: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "score": round(self.score, 3),
            "issues": self.issues,
            "factors": self.factors,
        }


def clamp_score(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 3)


def weighted_final_score(scores: dict[str, float]) -> float:
    total = 0.0
    for key, weight in SCORE_WEIGHTS.items():
        total += weight * scores.get(key, 0.0)
    return clamp_score(total)


def grade_from_score(score: float) -> str:
    if score >= 0.85:
        return "excelente"
    if score >= 0.70:
        return "bom"
    if score >= 0.50:
        return "aceitável"
    if score >= 0.30:
        return "insuficiente"
    return "crítico"


def collect_issues(stages: list[StageScore]) -> list[str]:
    issues: list[str] = []
    for stage in stages:
        if stage.score < ISSUE_THRESHOLD:
            issues.append(f"{stage.name}: score baixo ({stage.score})")
        issues.extend(stage.issues)
    return issues
