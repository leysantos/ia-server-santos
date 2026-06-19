"""
Model Evaluation Loop v1 — compara modelos e aprende ranking dinâmico por task/disciplina.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from config import settings
from core.models.model_scorer import ModelScorer

logger = logging.getLogger(__name__)

RECALIBRATE_EVERY = 50


class ModelEvaluationLoop:
    """Executa avaliação comparativa entre primary e fallback model."""

    def __init__(self, scorer: Optional[ModelScorer] = None) -> None:
        self.scorer = scorer or ModelScorer()

    @staticmethod
    def enabled() -> bool:
        return settings.USE_MODEL_EVALUATION

    def evaluate(
        self,
        *,
        prompt: str,
        input_text: str,
        task_type: str,
        discipline: str,
        primary_model: str,
        fallback_model: Optional[str] = None,
        client: Any = None,
        timeout: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Executa primary e fallback (sequencial), compara scores e retorna vencedor.
        """
        from models.ollama_client import OllamaClient

        llm = client or OllamaClient(timeout=timeout or 120)

        primary_text, primary_latency = self._run_model(llm, prompt, primary_model)
        primary_score = self.scorer.score_response(input_text, primary_text, task_type)

        fallback_text = ""
        fallback_score = 0.0
        fallback_latency = 0.0

        if fallback_model and fallback_model != primary_model:
            try:
                fallback_text, fallback_latency = self._run_model(llm, prompt, fallback_model)
                fallback_score = self.scorer.score_response(input_text, fallback_text, task_type)
            except Exception as exc:
                logger.warning("ModelEvaluationLoop fallback falhou model=%s: %s", fallback_model, exc)
                fallback_score = 0.0

        winner_model, decision_reason = self._pick_winner(
            primary_model,
            primary_score,
            primary_latency,
            fallback_model,
            fallback_score,
            fallback_latency,
        )
        winner_response = primary_text if winner_model == primary_model else fallback_text

        result = {
            "winner_model": winner_model,
            "winner_response": winner_response,
            "scores": {
                "primary": primary_score,
                "fallback": fallback_score if fallback_model else None,
            },
            "latency": {
                "primary": round(primary_latency, 2),
                "fallback": round(fallback_latency, 2) if fallback_model else None,
            },
            "decision_reason": decision_reason,
            "primary_model": primary_model,
            "fallback_model": fallback_model,
        }

        self._persist_and_learn(
            input_text=input_text,
            task_type=task_type,
            discipline=discipline,
            result=result,
            primary_text=primary_text,
            fallback_text=fallback_text,
        )

        logger.info(
            "model_evaluation task=%s discipline=%s winner=%s reason=%s scores=%s",
            task_type,
            discipline,
            winner_model,
            decision_reason,
            result["scores"],
        )

        return result

    def _run_model(self, llm: Any, prompt: str, model: str) -> tuple[str, float]:
        start = time.perf_counter()
        text, _used = llm.generate(prompt, model=model, fallback_models=[])
        latency_ms = (time.perf_counter() - start) * 1000
        return text, latency_ms

    def _pick_winner(
        self,
        primary_model: str,
        primary_score: float,
        primary_latency: float,
        fallback_model: Optional[str],
        fallback_score: float,
        fallback_latency: float,
    ) -> tuple[str, str]:
        if not fallback_model or fallback_score <= 0:
            return primary_model, "primary_only_or_fallback_failed"

        score_delta = primary_score - fallback_score
        if abs(score_delta) < 0.03:
            if primary_latency <= fallback_latency:
                return primary_model, "tie_breaker_latency_primary"
            return fallback_model, "tie_breaker_latency_fallback"

        if primary_score >= fallback_score:
            return primary_model, f"higher_quality_score (+{score_delta:.3f})"
        return fallback_model, f"higher_quality_score (+{-score_delta:.3f})"

    def _persist_and_learn(
        self,
        *,
        input_text: str,
        task_type: str,
        discipline: str,
        result: dict[str, Any],
        primary_text: str,
        fallback_text: str,
    ) -> None:
        try:
            from core.models.model_performance_service import (
                maybe_recalibrate_profiles,
                save_model_evaluation,
            )

            save_model_evaluation(
                input_text=input_text,
                task_type=task_type,
                discipline=discipline or "GERAL",
                primary_model=result["primary_model"],
                fallback_model=result.get("fallback_model"),
                winner_model=result["winner_model"],
                primary_score=result["scores"]["primary"],
                fallback_score=result["scores"].get("fallback"),
                primary_latency_ms=result["latency"]["primary"],
                fallback_latency_ms=result["latency"].get("fallback"),
                decision_reason=result["decision_reason"],
                primary_response=primary_text[:4000],
                fallback_response=(fallback_text or "")[:4000],
            )
            maybe_recalibrate_profiles(task_type, discipline or "GERAL")
        except Exception as exc:
            logger.debug("ModelEvaluationLoop persist/learn ignorado: %s", exc)


def evaluate_and_generate(
    prompt: str,
    *,
    input_text: str,
    task_type: str,
    discipline: Optional[str] = None,
    primary_model: str,
    fallback_model: Optional[str] = None,
    client: Any = None,
    timeout: Optional[int] = None,
) -> tuple[str, str, dict[str, Any]]:
    """Atalho: retorna (texto_vencedor, modelo_vencedor, metadata_eval)."""
    loop = ModelEvaluationLoop()
    meta = loop.evaluate(
        prompt=prompt,
        input_text=input_text,
        task_type=task_type,
        discipline=discipline or "GERAL",
        primary_model=primary_model,
        fallback_model=fallback_model,
        client=client,
        timeout=timeout,
    )
    return meta["winner_response"], meta["winner_model"], meta
