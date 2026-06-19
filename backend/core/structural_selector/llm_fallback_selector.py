"""
LLM fallback selector — classificação via Ollama quando heurísticas são inconclusivas.
"""

from __future__ import annotations

import logging
import re

from core.aed.project_understanding import ProjectUnderstanding
from core.structural_selector.system_registry import StructuralSystem, parse_system

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.55

VALID_VALUES = ", ".join(s.value for s in StructuralSystem)


def should_use_llm_fallback(rules_confidence: float, ambiguous: bool) -> bool:
    return rules_confidence < CONFIDENCE_THRESHOLD or ambiguous


def select_by_llm(understanding: ProjectUnderstanding) -> tuple[StructuralSystem, float, str]:
    """
    Classifica sistema estrutural via LLM.
    Retorna (system, confidence, raw_response).
    """
    prompt = f"""Classifique o sistema estrutural mais adequado para o projeto abaixo.

Projeto: {understanding.input_text}
Tipo: {understanding.project_type}
Disciplinas: {", ".join(understanding.disciplines)}
Objetivos: {", ".join(understanding.objectives)}

Responda APENAS com um destes valores (sem explicação):
{VALID_VALUES}

Sistema:"""

    try:
        from models.ollama_client import OllamaClient
        from config import settings

        if settings.USE_MODEL_ROUTER or settings.USE_MODEL_EVALUATION:
            from core.models.model_router import routed_generate

            raw, _model = routed_generate(
                prompt,
                "aed_evaluation",
                context={"text": understanding.input_text, "module": "aed"},
                module="aed",
                discipline="ESTRUTURAL",
                client=OllamaClient(timeout=30),
            )
        else:
            client = OllamaClient(timeout=30)
            raw, _model = client.generate(prompt)
    except Exception as exc:
        logger.warning("Structural selector LLM fallback indisponível: %s", exc)
        return StructuralSystem.CONCRETE_ARMED, 0.45, ""

    system = _parse_llm_response(raw)
    confidence = 0.75 if system else 0.45
    if not system:
        system = StructuralSystem.CONCRETE_ARMED
        confidence = 0.4

    return system, confidence, raw.strip()


def _parse_llm_response(raw: str) -> StructuralSystem | None:
    if not raw:
        return None
    # Primeira linha / token
    first_line = raw.strip().split("\n")[0].strip()
    token = re.sub(r"[^A-Z0-9_]", "", first_line.upper())
    parsed = parse_system(token)
    if parsed:
        return parsed
    for system in StructuralSystem:
        if system.value in raw.upper():
            return system
    return None
