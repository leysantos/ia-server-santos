"""
Model Scorer — avalia qualidade de respostas LLM (0–1) sem LLM adicional.
"""

from __future__ import annotations

import re
from typing import Optional

_ENGINEERING_MARKERS = (
    "nbr", "norma", "dimension", "premissa", "recomend", "análise", "analise",
    "segurança", "seguranca", "conformidade", "estrutura", "carga", "verific",
)

_STRUCTURE_MARKERS = ("##", "###", "- ", "1.", "2.", "premissas", "conclusão", "conclusao")

_CHAT_MARKERS = ("posso", "ajudar", "plataforma", "agente", "disciplina", "roteamento")


class ModelScorer:
    """Score heurístico de qualidade de resposta por task_type."""

    def score_response(
        self,
        input_text: str,
        response_text: str,
        task_type: str,
    ) -> float:
        if not response_text or not response_text.strip():
            return 0.0

        input_l = (input_text or "").lower()
        response_l = response_text.lower()
        words_in = set(re.findall(r"\w+", input_l))
        words_out = set(re.findall(r"\w+", response_l))

        overlap = len(words_in & words_out) / max(len(words_in), 1)
        length_score = min(1.0, len(response_text) / 800)
        structure_score = min(1.0, sum(1 for m in _STRUCTURE_MARKERS if m in response_l) * 0.15)

        relevance = min(1.0, overlap * 2.5 + 0.2)

        technical = 0.5
        if self._is_engineering_task(task_type):
            tech_hits = sum(1 for m in _ENGINEERING_MARKERS if m in response_l)
            technical = min(1.0, 0.3 + tech_hits * 0.12)
            if "nbr" in input_l and "nbr" not in response_l:
                technical *= 0.85
        elif task_type.startswith("chat"):
            chat_hits = sum(1 for m in _CHAT_MARKERS if m in response_l)
            technical = min(1.0, 0.4 + chat_hits * 0.1)

        completeness = min(1.0, length_score * 0.6 + structure_score * 0.4)
        coherence = min(1.0, 0.5 + (1.0 if len(response_text.split()) > 20 else 0.0) * 0.3 + structure_score * 0.2)

        final = (
            0.30 * relevance
            + 0.25 * completeness
            + 0.25 * coherence
            + 0.20 * technical
        )
        return round(min(1.0, max(0.0, final)), 4)

    @staticmethod
    def _is_engineering_task(task_type: str) -> bool:
        return task_type.startswith("engineering") or task_type.startswith("aed") or task_type in (
            "orchestration_synthesis",
            "code_generation",
            "code_understanding",
        )
