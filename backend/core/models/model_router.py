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

# --- Estimativa de complexidade (centralizada) ---

_BUDGET_HEAVY_KEYWORDS = (
    "passarela", "ponte", "viaduto", "igarap", "tabuleiro", "estrutura met",
    "todos os servi", "completo", "completa",
)

_ENGINEERING_HEAVY_KEYWORDS = (
    "dimensionar", "dimensionamento", "memorial de cálculo", "memorial de calculo",
    "projeto executivo", "nbr 6118", "nbr 6122", "concreto armado", "estaca",
    "fundação", "fundacao", "passarela", "ponte", "viga", "laje", "pilar",
)

_REASONING_KEYWORDS = (
    "justificar", "justificativa", "memorial", "analisar", "avaliar", "comparar",
    "raciocínio", "raciocinio", "deduzir", "conclusão", "conclusao", "hipótese",
    "hipotese", "premissa", "sintetizar", "síntese", "sintese",
)

_DISCIPLINE_HEAVY = frozenset(
    {"ESTRUTURAL", "GEOTECNIA", "ORÇAMENTO", "INFRAESTRUTURA", "TRANSPORTES"}
)

# Serviços de orçamento/pricing com alta complexidade técnica (estruturas, fundações, contenções)
_PRICING_HIGH_KEYWORDS = (
    # Estruturas gerais e metálicas
    "estrutura",
    "estruturas",
    "metalic",
    "metálic",
    "metalica",
    "metálica",
    "aço estrutural",
    "aco estrutural",
    "galpão",
    "galpao",
    "cobertura met",
    "treliça",
    "trelica",
    "perfil estrutural",
    "pórtico",
    "portico",
    # Obras de arte especiais / grandes vãos
    "passarela",
    "ponte",
    "viaduto",
    "tabuleiro",
    "taboão",
    "taboao",
    # Concreto e pré-moldados
    "concretagem",
    "concreto armado",
    "pré-moldado",
    "pre-moldado",
    "premoldado",
    "pré moldado",
    "pre moldado",
    "pré-fabricad",
    "pre-fabricad",
    "laje nervurada",
    "laje pré",
    "laje pre",
    # Madeira
    "madeira",
    "estrutura de madeira",
    "compensado estrutural",
    "mdf estrutural",
    # Protensão / pós-tensão
    "protensão",
    "protensao",
    "protendido",
    "protendida",
    "pós-tensão",
    "pos-tensao",
    "postensao",
    # Fundações
    "fundacao",
    "fundação",
    "fundações",
    "fundacoes",
    "fundação rasa",
    "fundacao rasa",
    "fundação profunda",
    "fundacao profunda",
    "fundação direta",
    "fundacao direta",
    "fundação indireta",
    "fundacao indireta",
    "radier",
    "sapata",
    "sapatas",
    "bloco de coroamento",
    "coroamento",
    "estaca",
    "estacas",
    "estaca raiz",
    "microestaca",
    "micro estaca",
    "tubulão",
    "tubulao",
    "broca",
    "helice",
    "hélice",
    "cravada",
    "escavada",
    "baldrame",
    "viga baldrame",
    # Contenção, arrimo e proteção geotécnica
    "contenção",
    "contencao",
    "contenç",
    "arrimo",
    "muro de arrimo",
    "muro de contenção",
    "muro de contencao",
    "gabião",
    "gabiao",
    "gabiões",
    "gabioes",
    "ancoragem",
    "solo grampeado",
    "grampeamento",
    "proteção de talude",
    "protecao de talude",
    "proteção de encosta",
    "protecao de encosta",
    "escoramento",
    "escorament",
    "cortina",
    "cortina atirantada",
    "atirantada",
    "barreira",
    "barreira de injeção",
    "barreira de injecao",
)


def estimate_budget_complexity(text: str, intent: dict[str, Any] | None = None) -> str:
    lower = (text or "").lower()
    score = 0
    if len(text) > 180:
        score += 1
    if len(text) > 400:
        score += 1
    if re.search(r"\d+(?:[.,]\d+)?\s*m\b", lower):
        score += 1
    if any(k in lower for k in _BUDGET_HEAVY_KEYWORDS):
        score += 2
    if any(k in lower for k in ("fundação", "fundacao", "estaca", "bloco", "coroamento")):
        score += 1
    if intent:
        etapas = intent.get("etapas") or []
        svc_count = sum(len(e.get("services") or []) for e in etapas)
        if len(etapas) >= 4:
            score += 1
        if svc_count >= 12:
            score += 2
        elif svc_count >= 8:
            score += 1
    if score >= 4:
        return "HIGH"
    if score >= 2:
        return "MEDIUM"
    return "LOW"


def estimate_pricing_complexity(
    line_name: str | None,
    query: str | None,
    service_context: str | None = None,
) -> str:
    combined = f"{line_name or ''} {query or ''} {service_context or ''}".lower()
    if any(k in combined for k in _PRICING_HIGH_KEYWORDS):
        return "HIGH"
    if len(combined) > 70:
        return "MEDIUM"
    return "LOW"


def estimate_engineering_complexity(text: str, discipline: str | None = None) -> str:
    lower = (text or "").lower()
    score = 0
    if discipline and discipline not in ("CHAT", "GERAL"):
        score += 1
    if discipline in _DISCIPLINE_HEAVY:
        score += 1
    if len(text) > 120:
        score += 1
    if len(text) > 280:
        score += 1
    if re.search(r"\d+(?:[.,]\d+)?\s*(?:m|m²|m2|kn|mpa|cm|mm)\b", lower):
        score += 1
    if any(k in lower for k in _ENGINEERING_HEAVY_KEYWORDS):
        score += 2
    if "nbr" in lower or "norma" in lower:
        score += 1
    if score >= 4:
        return "HIGH"
    if score >= 2:
        return "MEDIUM"
    return "LOW"


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
            # RTX 4060 8GB — leves 100% VRAM
            "chat_simple": "phi3:mini",
            "intent_layer": "phi3:mini",
            "chat_natural": "mistral:7b",
            # Código / fallback rápido
            "code_generation": "deepseek-coder:latest",
            "code_understanding": "qwen2.5-coder:latest",
            # Engenharia — qwen3.6 (primário) + deepseek-r1 (raciocínio) + gemma4 (secundário)
            "engineering_primary": "qwen3.6:latest",
            "engineering_reasoning": "deepseek-r1:14b",
            "engineering_secondary": "gemma4:latest",
            "engineering_fallback": "qwen2.5-coder:latest",
            "rag_embedding": "nomic-embed-text",
            "orchestration_synthesis": "deepseek-r1:14b",
            "platform_evaluation": "deepseek-r1:14b",
            "aed_simulation": "qwen3.6:latest",
            "aed_evaluation": "deepseek-r1:14b",
            # Orçamento WBS / pricing
            "budget_wbs_light": "mistral:7b",
            "budget_wbs": "qwen2.5-coder:latest",
            "budget_wbs_high": "deepseek-r1:14b",
            "budget_pricing_light": "phi3:mini",
            "budget_pricing": "mistral:7b",
            "budget_pricing_high": "qwen2.5-coder:latest",
        }

        self._fallback_map: dict[str, str] = {
            "engineering_primary": "engineering_reasoning",
            "engineering_reasoning": "engineering_secondary",
            "engineering_secondary": "engineering_fallback",
            "chat_natural": "chat_simple",
            "aed_simulation": "engineering_reasoning",
            "aed_evaluation": "engineering_secondary",
            "orchestration_synthesis": "engineering_secondary",
            "platform_evaluation": "engineering_secondary",
            "budget_wbs_high": "budget_wbs",
            "budget_wbs": "budget_wbs_light",
            "budget_pricing_high": "budget_pricing",
            "budget_pricing": "budget_pricing_light",
        }

        self._fallback_chains: dict[str, tuple[str, ...]] = {
            "engineering_primary": (
                "engineering_reasoning",
                "engineering_secondary",
                "engineering_fallback",
            ),
            "engineering_reasoning": ("engineering_secondary", "engineering_fallback"),
            "engineering_secondary": ("engineering_fallback",),
            "orchestration_synthesis": ("engineering_secondary", "engineering_fallback"),
            "platform_evaluation": ("engineering_secondary", "engineering_fallback"),
            "aed_simulation": (
                "engineering_reasoning",
                "engineering_secondary",
                "engineering_fallback",
            ),
            "aed_evaluation": ("engineering_secondary", "engineering_fallback"),
            "budget_wbs_high": ("budget_wbs", "budget_wbs_light"),
        }

        self._legacy_map: dict[str, str] = {
            "chat_simple": settings.OLLAMA_CHAT_MODEL,
            "chat_natural": settings.OLLAMA_CHAT_MODEL,
            "engineering_primary": settings.OLLAMA_LLM_MODEL,
            "engineering_reasoning": settings.OLLAMA_LLM_MODEL,
            "engineering_secondary": settings.OLLAMA_LLM_FALLBACK_MODEL,
            "engineering_fallback": settings.OLLAMA_LLM_FALLBACK_MODEL,
            "rag_embedding": settings.OLLAMA_EMBED_MODEL,
            "orchestration_synthesis": settings.OLLAMA_LLM_MODEL,
            "platform_evaluation": settings.OLLAMA_LLM_MODEL,
            "aed_simulation": settings.OLLAMA_LLM_MODEL,
            "aed_evaluation": settings.OLLAMA_LLM_MODEL,
            "code_generation": settings.OLLAMA_LLM_FALLBACK_MODEL,
            "code_understanding": settings.OLLAMA_LLM_FALLBACK_MODEL,
            "budget_wbs_light": settings.OLLAMA_CHAT_MODEL,
            "budget_wbs": settings.OLLAMA_BUDGET_MODEL,
            "budget_wbs_high": settings.OLLAMA_LLM_MODEL,
            "budget_pricing_light": "phi3:mini",
            "budget_pricing": settings.OLLAMA_BUDGET_MODEL,
            "budget_pricing_high": settings.OLLAMA_LLM_FALLBACK_MODEL,
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

    def resolve_budget_task_type(self, task: str, complexity: str) -> str:
        if task == "wbs":
            if complexity == "HIGH":
                return "budget_wbs_high"
            if complexity == "MEDIUM":
                return "budget_wbs"
            return "budget_wbs_light"
        if complexity == "HIGH":
            return "budget_pricing_high"
        if complexity == "MEDIUM":
            return "budget_pricing"
        return "budget_pricing_light"

    def resolve_engineering_task_type(self, complexity: str) -> str:
        if complexity == "HIGH":
            return "engineering_primary"
        if complexity == "MEDIUM":
            return "engineering_reasoning"
        return "engineering_fallback"

    def _needs_reasoning(self, text: str) -> bool:
        lower = (text or "").lower()
        return any(k in lower for k in _REASONING_KEYWORDS)

    def get_optimal_model(
        self,
        task_type: str,
        *,
        complexity: str | None = None,
        context: Optional[dict[str, Any]] = None,
    ) -> tuple[str, list[str], str]:
        """
        Ponto único de decisão: task_type + complexidade → (modelo, fallbacks, task resolvido).
        """
        ctx = dict(context or {})
        if complexity:
            ctx["complexity"] = complexity
        resolved = self._resolve_task_type(task_type, ctx)
        model = self.get_model(resolved, ctx)
        fallbacks = self.get_fallback_models(resolved, ctx)
        return model, fallbacks, resolved

    def get_model(self, task_type: str, context: Optional[dict[str, Any]] = None) -> str:
        """Retorna modelo ideal baseado no tipo de tarefa e contexto."""
        context = context or {}
        resolved_task = self._resolve_task_type(task_type, context)

        learned = self.get_best_model(resolved_task, context.get("discipline"))
        if learned:
            return learned

        if not self.enabled():
            return self._legacy_map.get(resolved_task, settings.OLLAMA_LLM_MODEL)

        model = self.model_map.get(resolved_task)
        if not model:
            logger.warning("ModelRouter: task_type desconhecido %s, usando engineering_primary", task_type)
            model = self.model_map["engineering_primary"]
        return model

    def get_fallback_models(
        self,
        task_type: str,
        context: Optional[dict[str, Any]] = None,
    ) -> list[str]:
        """Cadeia de fallback após falha do modelo primário."""
        context = context or {}
        if not self.enabled():
            primary = self._legacy_map.get(task_type, settings.OLLAMA_LLM_MODEL)
            fb = settings.OLLAMA_LLM_FALLBACK_MODEL
            return [fb] if fb != primary else []

        resolved = self._resolve_task_type(task_type, context)
        fallbacks: list[str] = []
        chain = self._fallback_chains.get(resolved)
        if chain:
            fallbacks.extend(self.model_map[k] for k in chain if k in self.model_map)
        else:
            fb_key = self._fallback_map.get(resolved)
            if fb_key and fb_key in self.model_map:
                fallbacks.append(self.model_map[fb_key])
        if resolved == "chat_natural":
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
        if complexity == "HIGH":
            return "engineering_primary"
        if complexity == "MEDIUM":
            return "engineering_reasoning"
        if self.is_engineering_task(text, discipline):
            if self._needs_reasoning(text) or discipline in _DISCIPLINE_HEAVY:
                return "engineering_reasoning"
            return "engineering_fallback"
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
            return self.resolve_engineering_task(
                text, discipline, complexity=complexity
            )

        if module == "budget" and context.get("budget_task"):
            cx = complexity or estimate_budget_complexity(text, context.get("intent"))
            return self.resolve_budget_task_type(context["budget_task"], cx)

        if module == "agent" and complexity:
            return self.resolve_engineering_task_type(complexity)

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
    format_json: bool = False,
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
        from core.llm_override import get_llm_model_override

        llm = client or OllamaClient(timeout=timeout or 120)
        override = get_llm_model_override()
        if override:
            return llm.generate(prompt, model=override, format_json=format_json)
        text, model_used = llm.generate(prompt, format_json=format_json)
        return text, model_used

    from core.llm_override import get_llm_model_override

    input_text = ctx.get("text") or ctx.get("input") or prompt[:500]
    override = get_llm_model_override()
    if override:
        model = override
        fallbacks = router.get_fallback_models(task_type, ctx)
    else:
        model = router.get_model(task_type, ctx)
        fallbacks = router.get_fallback_models(task_type, ctx)

    from core.runtime.model_vram import fit_model_to_vram

    model, fallbacks, vram_notice = fit_model_to_vram(model, fallbacks)
    if vram_notice:
        logger.info("routed_generate VRAM: %s", vram_notice)
    fallback_model = fallbacks[0] if fallbacks else None

    llm = client or OllamaClient(timeout=timeout or 120)

    if router.evaluation_enabled() and fallback_model and fallback_model != model and not override:
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
        text, model_used = llm.generate(prompt, model=model, fallback_models=fallbacks, format_json=format_json)
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
