"""
Intent Analyzer — classifica intenção do usuário para o Copilot v1.

Intents: structural, hydraulic, electrical, cost, multi_discipline, general
Rule-based (sem LLM) — não altera Router v2.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

CopilotIntent = Literal[
    "structural",
    "hydraulic",
    "electrical",
    "cost",
    "multi_discipline",
    "general",
]

INTENT_KEYWORDS: dict[str, list[str]] = {
    "structural": [
        "estrutur", "viga", "pilar", "laje", "concreto", "aço", "fundação",
        "armadura", "protens", "nbr 6118", "dimensionar",
    ],
    "hydraulic": [
        "hidrául", "hidraul", "hidrossanit", "esgoto", "água", "agua",
        "sanitário", "sanitario", "drenagem", "pluvial", "nbr 5626", "nbr 8160",
    ],
    "electrical": [
        "elétric", "eletric", "energia", "iluminação", "iluminacao",
        "quadro elétrico", "nbr 5410", "telecom", "cabeamento",
    ],
    "cost": [
        "orçament", "orcament", "custo", "budget", "sinapi", "bdí", "bdi",
        "planilha orçamentária", "composição de preço",
    ],
}

BUILDING_TRIGGERS = ["prédio", "predio", "edific", "residencial", "comercial", "condomínio", "condominio"]

INTENT_TO_PRIMARY_DISCIPLINE: dict[str, str] = {
    "structural": "ESTRUTURAL",
    "hydraulic": "HIDROSSANITÁRIO",
    "electrical": "ELÉTRICA",
    "cost": "ORÇAMENTO",
    "general": "GERAL",
}


@dataclass
class IntentResult:
    intent: CopilotIntent
    confidence: float
    matched_categories: list[str]
    disciplines_hint: list[str]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _score_categories(text: str) -> dict[str, int]:
    scores: dict[str, int] = {}
    for category, keywords in INTENT_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text)
        if hits:
            scores[category] = hits
    return scores


def analyze_intent(text: str) -> IntentResult:
    """
    Classifica intenção do input.

    multi_discipline quando:
    - 2+ categorias de intent detectadas, ou
    - trigger de edificação (prédio, residencial, etc.)
    """
    normalized = _normalize(text)
    scores = _score_categories(normalized)
    matched = list(scores.keys())

    is_building = any(t in normalized for t in BUILDING_TRIGGERS)
    multi_category = len(matched) >= 2

    if is_building or multi_category:
        disciplines_hint = _disciplines_for_multi(normalized, matched)
        confidence = min(0.95, 0.55 + 0.1 * len(disciplines_hint))
        return IntentResult(
            intent="multi_discipline",
            confidence=round(confidence, 2),
            matched_categories=matched,
            disciplines_hint=disciplines_hint,
        )

    if len(matched) == 1:
        category = matched[0]
        discipline = INTENT_TO_PRIMARY_DISCIPLINE[category]
        hits = scores[category]
        confidence = min(0.95, 0.5 + 0.1 * hits)
        return IntentResult(
            intent=category,  # type: ignore[arg-type]
            confidence=round(confidence, 2),
            matched_categories=matched,
            disciplines_hint=[discipline],
        )

    if any(kw in normalized for kw in INTENT_KEYWORDS["structural"]):
        return IntentResult(
            intent="structural",
            confidence=0.6,
            matched_categories=["structural"],
            disciplines_hint=["ESTRUTURAL"],
        )

    return IntentResult(
        intent="general",
        confidence=0.5,
        matched_categories=[],
        disciplines_hint=["GERAL"],
    )


def _disciplines_for_multi(normalized: str, matched_categories: list[str]) -> list[str]:
    """Deriva disciplinas para intent multi_discipline."""
    disciplines: list[str] = []

    category_disciplines = {
        "structural": ["ESTRUTURAL", "GEOTECNIA"],
        "hydraulic": ["HIDROSSANITÁRIO", "DRENAGEM"],
        "electrical": ["ELÉTRICA", "TELECOM"],
        "cost": ["ORÇAMENTO"],
    }

    for cat in matched_categories:
        for disc in category_disciplines.get(cat, []):
            if disc not in disciplines:
                disciplines.append(disc)

    if any(t in normalized for t in BUILDING_TRIGGERS):
        for disc in ["ARQUITETURA", "ESTRUTURAL", "HIDROSSANITÁRIO", "INCÊNDIO", "ORÇAMENTO"]:
            if disc not in disciplines:
                disciplines.append(disc)

    if not disciplines:
        disciplines = ["ESTRUTURAL", "ORÇAMENTO"]

    return disciplines
