"""
Project Understanding — extrai requisitos, disciplinas e restrições do input.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from core.copilot.intent_analyzer import analyze_intent, IntentResult
from core.copilot.task_planner import DISCIPLINE_KEYWORDS
from core.agents.base_agent_intelligent import DISCIPLINE_NBRS


@dataclass
class ProjectUnderstanding:
    input_text: str
    intent: str
    intent_confidence: float
    disciplines: list[str]
    objectives: list[str]
    constraints: list[str]
    normas: dict[str, list[str]] = field(default_factory=dict)
    project_type: str = "geral"
    keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_text": self.input_text,
            "intent": self.intent,
            "intent_confidence": self.intent_confidence,
            "disciplines": self.disciplines,
            "objectives": self.objectives,
            "constraints": self.constraints,
            "normas": self.normas,
            "project_type": self.project_type,
            "keywords": self.keywords,
        }


BUILDING_TYPES = {
    "residencial": ["residencial", "apartamento", "habitacional"],
    "comercial": ["comercial", "loja", "escritório", "escritorio"],
    "industrial": ["industrial", "galpão", "galpao", "fabrica"],
    "infraestrutura": ["ponte", "viaduto", "rodovia", "infraestrutur"],
}

CONSTRAINT_KEYWORDS = {
    "prazo": ["prazo", "urgente", "rápido", "rapido"],
    "custo": ["custo", "orçamento", "orcamento", "econômico", "economico"],
    "sustentabilidade": ["sustentável", "sustentavel", "ambiental", "verde"],
    "normativo": ["nbr", "norma", "conformidade", "compliance"],
}


def understand_project(text: str) -> ProjectUnderstanding:
    """Analisa o projeto e deriva contexto multidisciplinar."""
    text = text.strip()
    intent_result = analyze_intent(text)
    disciplines = _resolve_disciplines_from_intent(text, intent_result)

    keywords = _extract_keywords(text)
    objectives = _extract_objectives(text, intent_result)
    constraints = _extract_constraints(text)
    project_type = _detect_project_type(text)
    normas = {d: DISCIPLINE_NBRS.get(d, []) for d in disciplines}

    return ProjectUnderstanding(
        input_text=text,
        intent=intent_result.intent,
        intent_confidence=intent_result.confidence,
        disciplines=disciplines,
        objectives=objectives,
        constraints=constraints,
        normas=normas,
        project_type=project_type,
        keywords=keywords,
    )


def _resolve_disciplines_from_intent(text: str, intent_result: IntentResult) -> list[str]:
    from core.copilot.task_planner import build_plan

    plan = build_plan(text, intent_result)
    return plan.disciplines


def _extract_keywords(text: str) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for discipline, keywords in DISCIPLINE_KEYWORDS.items():
        for kw in keywords:
            if kw in lowered and kw not in found:
                found.append(kw)
    return found[:10]


def _extract_objectives(text: str, intent_result: IntentResult) -> list[str]:
    objectives = [f"Atender intent: {intent_result.intent}"]
    lowered = text.lower()
    if "dimensionar" in lowered:
        objectives.append("Dimensionamento técnico conforme normas")
    if "projeto" in lowered:
        objectives.append("Elaborar solução de projeto executável")
    if "otimizar" in lowered or "melhor" in lowered:
        objectives.append("Otimizar solução técnica e econômica")
    if intent_result.intent == "multi_discipline":
        objectives.append("Integrar soluções multidisciplinares")
    return objectives


def _extract_constraints(text: str) -> list[str]:
    lowered = text.lower()
    constraints: list[str] = []
    for name, keywords in CONSTRAINT_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            constraints.append(name)
    if not constraints:
        constraints.append("conformidade_normativa")
    return constraints


def _detect_project_type(text: str) -> str:
    lowered = text.lower()
    for ptype, keywords in BUILDING_TYPES.items():
        if any(kw in lowered for kw in keywords):
            return ptype
    return "geral"
