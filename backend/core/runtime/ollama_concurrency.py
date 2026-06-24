"""Concorrência Ollama — chat em paralelo com jobs GPU (visão, orçamento)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import settings
from core.runtime.job_registry import get_job_registry


@dataclass
class ChatRuntimePlan:
    """Plano de execução do chat conforme carga da GPU."""

    timeout_sec: int
    ollama_options: dict[str, Any]
    model_override: str | None
    gpu_busy: bool
    active_vision_jobs: int
    vram_percent: float | None
    parallel_mode: str  # gpu | cpu_parallel | normal
    status_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeout_sec": self.timeout_sec,
            "ollama_options": self.ollama_options,
            "model_override": self.model_override,
            "gpu_busy": self.gpu_busy,
            "active_vision_jobs": self.active_vision_jobs,
            "vram_percent": self.vram_percent,
            "parallel_mode": self.parallel_mode,
            "status_message": self.status_message,
        }


def _vram_pressure_percent() -> float | None:
    try:
        from core.system.benchmark import collect_system_benchmark

        gpu = collect_system_benchmark().get("gpu") or {}
        total = float(gpu.get("memory_total_mb") or 0)
        used = float(gpu.get("memory_used_mb") or 0)
        if total <= 0:
            return None
        return round(100.0 * used / total, 1)
    except Exception:
        return None


def _active_gpu_jobs() -> list[dict[str, Any]]:
    registry = get_job_registry()
    gpu_kinds = {"vision", "budget", "orchestrator", "review"}
    return [
        j
        for j in registry.list_jobs(active_only=True, limit=20)
        if j.get("kind") in gpu_kinds
    ]


_HEAVY_MODEL_MARKERS = (
    "gemma4",
    "gemma3:12",
    "deepseek-r1",
    "qwen3-coder",
    "qwen3:14",
)


def is_heavy_llm_model(model: str | None) -> bool:
    """Modelos >8B que demoram para carregar e não devem rodar só em CPU."""
    if not model:
        return False
    lower = model.lower()
    return any(marker in lower for marker in _HEAVY_MODEL_MARKERS)


def resolve_llm_stream_config(
    *,
    primary_model: str | None = None,
    fallback_models: list[str] | None = None,
    llm_model: str | None = None,
) -> tuple[int, dict[str, Any], list[str]]:
    """
    Timeout e opções Ollama para stream/generate.

    Modelos pesados escolhidos pelo usuário usam timeout estendido e GPU
    (não força num_gpu=0 quando a VRAM está ocupada).
    """
    from core.llm_override import resolve_llm_model

    plan = resolve_chat_runtime()
    override = resolve_llm_model(llm_model)
    effective = override or primary_model or plan.model_override

    opts = dict(plan.ollama_options or {})
    timeout = plan.timeout_sec

    if is_heavy_llm_model(effective):
        heavy_timeout = int(getattr(settings, "OLLAMA_HEAVY_MODEL_TIMEOUT", 300))
        timeout = max(timeout, heavy_timeout)
        if override or primary_model:
            opts.pop("num_gpu", None)

    fallbacks = list(fallback_models or [])
    if override and not fallbacks:
        try:
            from core.models.model_router import get_model_router

            router = get_model_router()
            fallbacks = [
                router.model_map.get("engineering_secondary", "gemma3:12b"),
                router.model_map.get("engineering_fallback", "qwen2.5-coder:latest"),
                router.model_map.get("chat_natural", "mistral:7b"),
            ]
        except Exception:
            fallbacks = ["gemma3:12b", "qwen2.5-coder:latest", "mistral:7b"]

    seen: set[str] = set()
    deduped: list[str] = []
    for name in fallbacks:
        if name and name != effective and name not in seen:
            seen.add(name)
            deduped.append(name)

    return timeout, opts, deduped


def resolve_chat_runtime() -> ChatRuntimePlan:
    """
    Define timeout e opções Ollama para chat coexistir com análise visual.

    Com VRAM ocupada, o chat usa CPU (`num_gpu: 0`) para não competir com Gemma/Qwen.
    """
    base_timeout = int(settings.OLLAMA_CHAT_TIMEOUT)
    busy_timeout = int(getattr(settings, "OLLAMA_CHAT_BUSY_TIMEOUT", 180))
    cpu_when_busy = bool(getattr(settings, "OLLAMA_CHAT_CPU_WHEN_GPU_BUSY", True))
    light_model = getattr(settings, "OLLAMA_CHAT_LIGHT_MODEL", None) or None
    vram_threshold = float(getattr(settings, "OLLAMA_CHAT_GPU_BUSY_VRAM_PCT", 75.0))

    vision_jobs = [j for j in _active_gpu_jobs() if j.get("kind") == "vision"]
    vram_pct = _vram_pressure_percent()
    gpu_busy = bool(vision_jobs) or (vram_pct is not None and vram_pct >= vram_threshold)

    if not gpu_busy:
        return ChatRuntimePlan(
            timeout_sec=base_timeout,
            ollama_options={},
            model_override=None,
            gpu_busy=False,
            active_vision_jobs=len(vision_jobs),
            vram_percent=vram_pct,
            parallel_mode="normal",
        )

    status = None
    options: dict[str, Any] = {}
    model_override = None
    mode = "gpu_wait"

    if cpu_when_busy:
        options = {"num_gpu": 0}
        mode = "cpu_parallel"
        if light_model:
            model_override = light_model
        vision_label = vision_jobs[0].get("label") if vision_jobs else "job GPU"
        status = (
            f"Análise visual em andamento ({vision_label}) — "
            "chat rodando em CPU em paralelo para liberar a GPU."
        )
    else:
        mode = "gpu_wait"
        status = (
            "GPU ocupada pela análise visual — aguardando slot Ollama. "
            "Use Análise rápida ou aguarde a conclusão."
        )

    return ChatRuntimePlan(
        timeout_sec=busy_timeout,
        ollama_options=options,
        model_override=model_override,
        gpu_busy=True,
        active_vision_jobs=len(vision_jobs),
        vram_percent=vram_pct,
        parallel_mode=mode,
        status_message=status,
    )
