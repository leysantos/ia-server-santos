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
