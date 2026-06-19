"""
Model Router — roteamento centralizado de modelos LLM por tipo de tarefa.
"""

from __future__ import annotations

import logging
import re
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Optional

from config import settings

logger = logging.getLogger(__name__)

_ENGINEERING_KEYWORDS = (
    "dimensionar", "dimensionamento", "nbr", "norma", "viga", "laje", "pilar",
    "fundação", "fundacao", "estrutura", "concreto", "aço", "aco", "carga",
    "projeto executivo", "memorial de cálculo", "memorial de calculo",
)

_LIGHT_MARKERS = (
    "oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "hey", "hello",
    "obrigado", "valeu", "tudo bem", "como funciona", "o que é", "quem é",
)

_DISCIPLINE_KEYWORDS = (
    "estrutural", "hidrául", "hidraul", "elétric", "eletric", "geotec",
    "incêndio", "incendio", "drenagem", "saneamento", "orçamento", "orcamento",
)


@dataclass
class InferenceRecord:
    task_type: str
    model: str
    module: str
    discipline: Optional[str] = None
    latency_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    success: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_type": self.task_type,
            "model": self.model,
            "module": self.module,
            "discipline": self.discipline,
            "latency_ms": round(self.latency_ms, 2),
            "timestamp": self.timestamp,
            "success": self.success,
        }


class ModelRouter:
    """Seleciona modelo LLM ideal por task_type com fallback inteligente."""

    def __init__(self) -> None:
        self.model_map: dict[str, str] = {
            "chat_simple": "phi3:mini",
            "chat_natural": "mistral:7b",
            "code_generation": "deepseek-coder:latest",
            "code_understanding": "qwen2.5-coder",
            "engineering_primary": "qwen3:14b",
            "engineering_fallback": "qwen3-coder",
            "rag_embedding": "nomic-embed-text",
            "orchestration_synthesis": "gemma3:12b",
            "aed_simulation": "qwen3:14b",
            "aed_evaluation": "gemma3:12b",
        }

        self._fallback_map: dict[str, str] = {
            "engineering_primary": "engineering_fallback",
            "chat_natural": "chat_simple",
            "aed_simulation": "engineering_fallback",
            "orchestration_synthesis": "engineering_fallback",
        }

        self._legacy_map: dict[str, str] = {
            "chat_simple": settings.OLLAMA_CHAT_MODEL,
            "chat_natural": settings.OLLAMA_CHAT_MODEL,
            "engineering_primary": settings.OLLAMA_LLM_MODEL,
            "engineering_fallback": settings.OLLAMA_LLM_FALLBACK_MODEL,
            "rag_embedding": settings.OLLAMA_EMBED_MODEL,
            "orchestration_synthesis": settings.OLLAMA_LLM_MODEL,
            "aed_simulation": settings.OLLAMA_LLM_MODEL,
            "aed_evaluation": settings.OLLAMA_LLM_MODEL,
            "code_generation": settings.OLLAMA_LLM_FALLBACK_MODEL,
            "code_understanding": settings.OLLAMA_LLM_FALLBACK_MODEL,
        }

        self._active_by_module: dict[str, str] = {}
        self._recent_requests: deque[InferenceRecord] = deque(maxlen=200)
        self._learned_overrides: dict[str, str] = {}
        self._lock = Lock()

    def evaluation_enabled(self) -> bool:
        return settings.USE_MODEL_EVALUATION

    def get_best_model(self, task_type: str, discipline: Optional[str] = None) -> Optional[str]:
        """Consulta ranking dinâmico (model_performance_profile)."""
        if not self.evaluation_enabled():
            return None
        try:
            from core.models.model_performance_service import get_best_model_from_profile

            resolved = self._resolve_task_type(task_type, {"discipline": discipline})
            return get_best_model_from_profile(resolved, discipline or "GERAL")
        except Exception as exc:
            logger.debug("get_best_model fallback: %s", exc)
            return None

    def apply_learned_model(self, task_type: str, model_name: str) -> None:
        """Atualiza model_map com modelo vencedor do auto-learning."""
        with self._lock:
            self._learned_overrides[task_type] = model_name
            if task_type in self.model_map:
                self.model_map[task_type] = model_name
        logger.info("ModelRouter learned override task=%s model=%s", task_type, model_name)

    def enabled(self) -> bool:
        return settings.USE_MODEL_ROUTER

    def get_model(self, task_type: str, context: Optional[dict[str, Any]] = None) -> str:
        """Retorna modelo ideal baseado no tipo de tarefa e contexto."""
        context = context or {}

        if not self.enabled():
            resolved = self._resolve_task_type(task_type, context or {})
            learned = self.get_best_model(resolved, (context or {}).get("discipline"))
            if learned:
                return learned
            return self._legacy_map.get(task_type, settings.OLLAMA_LLM_MODEL)

        resolved_task = self._resolve_task_type(task_type, context)
        learned = self.get_best_model(resolved_task, context.get("discipline"))
        if learned:
            return learned
        model = self.model_map.get(resolved_task)
        if not model:
            logger.warning("ModelRouter: task_type desconhecido %s, usando engineering_primary", task_type)
            model = self.model_map["engineering_primary"]
        return model

    def get_fallback_models(self, task_type: str) -> list[str]:
        """Cadeia de fallback após falha do modelo primário."""
        if not self.enabled():
            primary = self._legacy_map.get(task_type, settings.OLLAMA_LLM_MODEL)
            fb = settings.OLLAMA_LLM_FALLBACK_MODEL
            return [fb] if fb != primary else []

        resolved = self._resolve_task_type(task_type, {})
        fallbacks: list[str] = []
        fb_key = self._fallback_map.get(resolved)
        if fb_key and fb_key in self.model_map:
            fallbacks.append(self.model_map[fb_key])
        if resolved == "engineering_primary":
            fallbacks.append(self.model_map["engineering_fallback"])
        elif resolved == "chat_natural":
            fallbacks.append(self.model_map["chat_simple"])
        # dedupe preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for m in fallbacks:
            if m not in seen:
                seen.add(m)
                unique.append(m)
        return unique

    def is_light_task(self, text: str) -> bool:
        """Detecta tarefa leve (saudação, chat curto)."""
        if not text:
            return True
        normalized = re.sub(r"\s+", " ", text.strip().lower())
        if len(normalized) <= 40 and any(m in normalized for m in _LIGHT_MARKERS):
            return True
        words = normalized.split()
        if len(words) <= 5 and not any(k in normalized for k in _ENGINEERING_KEYWORDS):
            return True
        return False

    def is_engineering_task(self, text: str, discipline: Optional[str] = None) -> bool:
        """Detecta tarefa de engenharia pesada."""
        if discipline and discipline not in ("CHAT", "GERAL", None):
            return True
        if not text:
            return False
        lowered = text.lower()
        if any(k in lowered for k in _ENGINEERING_KEYWORDS):
            return True
        if any(k in lowered for k in _DISCIPLINE_KEYWORDS):
            return True
        return False

    def resolve_chat_task(self, text: str) -> str:
        return "chat_simple" if self.is_light_task(text) else "chat_natural"

    def resolve_engineering_task(
        self,
        text: str,
        discipline: Optional[str] = None,
        *,
        complexity: Optional[str] = None,
    ) -> str:
        if complexity == "HIGH" or (discipline == "ESTRUTURAL" and self.is_engineering_task(text, discipline)):
            if complexity == "HIGH":
                return "engineering_primary"
        if self.is_engineering_task(text, discipline):
            return "engineering_primary"
        return "engineering_fallback"

    def record_inference(
        self,
        *,
        task_type: str,
        model: str,
        module: str,
        discipline: Optional[str] = None,
        latency_ms: float = 0.0,
        success: bool = True,
    ) -> None:
        record = InferenceRecord(
            task_type=task_type,
            model=model,
            module=module,
            discipline=discipline,
            latency_ms=latency_ms,
            success=success,
        )
        with self._lock:
            self._recent_requests.append(record)
            self._active_by_module[module] = model
        logger.info(
            "model_router task=%s model=%s module=%s discipline=%s latency_ms=%.1f",
            task_type,
            model,
            module,
            discipline,
            latency_ms,
        )

    def get_status(self, installed_models: Optional[list[str]] = None) -> dict[str, Any]:
        with self._lock:
            recent = [r.to_dict() for r in list(self._recent_requests)[-20:]]
            active = dict(self._active_by_module)
            learned = dict(self._learned_overrides)

        return {
            "router_enabled": self.enabled(),
            "evaluation_enabled": self.evaluation_enabled(),
            "model_map": dict(self.model_map),
            "learned_overrides": learned,
            "installed_models": installed_models or [],
            "active_by_module": active,
            "recent_requests": recent,
            "legacy_models": {
                "chat": settings.OLLAMA_CHAT_MODEL,
                "engineering": settings.OLLAMA_LLM_MODEL,
                "fallback": settings.OLLAMA_LLM_FALLBACK_MODEL,
                "embed": settings.OLLAMA_EMBED_MODEL,
            },
        }

    def _resolve_task_type(self, task_type: str, context: dict[str, Any]) -> str:
        text = context.get("text") or context.get("input") or ""
        discipline = context.get("discipline")
        complexity = context.get("complexity")
        module = context.get("module")

        if task_type == "chat" or task_type == "chat_auto":
            return self.resolve_chat_task(text)

        if task_type == "engineering" or task_type == "engineering_auto":
            return self.resolve_engineering_task(text, discipline, complexity=complexity)

        if task_type == "engineering_primary" and complexity == "HIGH":
            return "engineering_primary"

        if module == "sie" and complexity == "HIGH":
            return "engineering_primary"
        if module == "sie" and complexity in ("LOW", "MEDIUM", None):
            return "engineering_fallback"

        return task_type


_router: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router


def routed_generate(
    prompt: str,
    task_type: str,
    *,
    context: Optional[dict[str, Any]] = None,
    module: str = "unknown",
    discipline: Optional[str] = None,
    client: Any = None,
    timeout: Optional[int] = None,
) -> tuple[str, str]:
    """
    Gera resposta LLM via ModelRouter (ou legado se flag desabilitada).
    Com USE_MODEL_EVALUATION=true, compara primary vs fallback quando possível.
    Retorna (texto, modelo_utilizado).
    """
    from models.ollama_client import OllamaClient

    router = get_model_router()
    ctx = dict(context or {})
    if discipline:
        ctx.setdefault("discipline", discipline)

    if not router.enabled() and not router.evaluation_enabled():
        llm = client or OllamaClient(timeout=timeout or 120)
        text, model_used = llm.generate(prompt)
        return text, model_used

    input_text = ctx.get("text") or ctx.get("input") or prompt[:500]
    model = router.get_model(task_type, ctx)
    fallbacks = router.get_fallback_models(task_type)
    fallback_model = fallbacks[0] if fallbacks else None

    llm = client or OllamaClient(timeout=timeout or 120)

    if router.evaluation_enabled() and fallback_model and fallback_model != model:
        from core.models.model_evaluation_loop import evaluate_and_generate

        start = time.perf_counter()
        text, model_used, eval_meta = evaluate_and_generate(
            prompt,
            input_text=input_text,
            task_type=router._resolve_task_type(task_type, ctx),
            discipline=discipline or "GERAL",
            primary_model=model,
            fallback_model=fallback_model,
            client=llm,
            timeout=timeout,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        router.record_inference(
            task_type=task_type,
            model=model_used,
            module=module,
            discipline=discipline,
            latency_ms=latency_ms,
            success=True,
        )
        return text, model_used

    start = time.perf_counter()
    success = True
    model_used = model
    try:
        text, model_used = llm.generate(prompt, model=model, fallback_models=fallbacks)
    except Exception:
        success = False
        raise
    finally:
        latency_ms = (time.perf_counter() - start) * 1000
        router.record_inference(
            task_type=task_type,
            model=model_used if success else model,
            module=module,
            discipline=discipline,
            latency_ms=latency_ms,
            success=success,
        )

    return text, model_used
