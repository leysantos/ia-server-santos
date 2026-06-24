"""Ajuste de modelo LLM conforme VRAM disponível (evita hang com qwen3.6 em GPU 8GB)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Estimativa mínima de VRAM (MB) para rodar o modelo inteiro na GPU sem swap extremo
_MODEL_VRAM_REQUIREMENTS_MB: tuple[tuple[str, int], ...] = (
    ("qwen3.6", 20_000),
    ("qwen3-coder", 16_000),
    ("deepseek-r1", 8_500),
    ("qwen3:14", 8_500),
    ("gemma4", 7_000),
)

_DEFAULT_FALLBACK_CHAIN: tuple[str, ...] = (
    "gemma4:latest",
    "qwen3:14b",
    "gemma3:12b",
    "deepseek-r1:14b",
    "mistral:7b",
)


def gpu_total_vram_mb() -> float | None:
    try:
        from core.system.benchmark import collect_system_benchmark

        gpu = collect_system_benchmark().get("gpu") or {}
        total = float(gpu.get("memory_total_mb") or 0)
        return total if total > 0 else None
    except Exception:
        return None


def model_vram_requirement_mb(model: str) -> int | None:
    lower = (model or "").lower()
    for token, need_mb in _MODEL_VRAM_REQUIREMENTS_MB:
        if token in lower:
            return need_mb
    return None


def model_fits_vram(model: str, *, headroom_mb: int = 1200) -> bool:
    need = model_vram_requirement_mb(model)
    total = gpu_total_vram_mb()
    if need is None or total is None:
        return True
    return total >= need + headroom_mb


def fit_model_to_vram(
    model: str,
    fallbacks: list[str] | None = None,
    *,
    headroom_mb: int = 1200,
) -> tuple[str, list[str], str | None]:
    """
    Se o modelo exige mais VRAM que a GPU tem, escolhe o primeiro fallback viável.
    Retorna (modelo, fallbacks_restantes, aviso_usuario ou None).
    """
    fb = [m for m in (fallbacks or []) if m and m != model]
    if model_fits_vram(model, headroom_mb=headroom_mb):
        return model, fb, None

    need = model_vram_requirement_mb(model)
    total = gpu_total_vram_mb()
    candidates = fb + list(_DEFAULT_FALLBACK_CHAIN)
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate == model or candidate in seen:
            continue
        seen.add(candidate)
        if model_fits_vram(candidate, headroom_mb=800):
            total_label = f"{int(total)} MB" if total else "VRAM limitada"
            need_label = f"{need // 1000} GB" if need else "muita VRAM"
            notice = (
                f"{model} requer ~{need_label} de VRAM (GPU: {total_label}) — "
                f"usando {candidate}."
            )
            logger.warning("VRAM fit: %s → %s (%s)", model, candidate, notice)
            rest = [m for m in fb if m != candidate]
            if model not in rest:
                rest.append(model)
            return candidate, rest, notice

    return model, fb, None
