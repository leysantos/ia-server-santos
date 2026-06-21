"""Snapshot agregado para o Operations Console."""

from __future__ import annotations

from typing import Any

from core.runtime.job_registry import get_job_registry
from core.runtime.ollama_runtime import list_running_models
from core.runtime.ops_log import list_ops_logs
from core.system.benchmark import collect_system_benchmark


def _model_in_vram(job_model: str | None, loaded_names: list[str]) -> bool:
    if not job_model or not loaded_names:
        return False
    base = job_model.split(":")[0]
    for loaded in loaded_names:
        loaded_base = loaded.split(":")[0]
        if job_model == loaded or loaded.startswith(base) or loaded_base == base:
            return True
    return False


def build_ollama_queue(active_jobs: list[dict[str, Any]], loaded_models: list[dict[str, Any]]) -> dict[str, Any]:
    """Fila estimada: jobs ativos vs modelos residentes na VRAM."""
    loaded_names = [m.get("name", "") for m in loaded_models if m.get("name")]
    ordered = sorted(active_jobs, key=lambda j: j.get("started_at") or 0)
    items: list[dict[str, Any]] = []
    gpu_slot_taken = False

    for job in ordered:
        has_vram = _model_in_vram(job.get("model"), loaded_names)
        kind = job.get("kind") or ""
        # Chat pode rodar em CPU em paralelo — não bloquear slot GPU na fila visual.
        if kind == "chat" and gpu_slot_taken:
            state = "running"
        elif has_vram and not gpu_slot_taken:
            state = "on_gpu"
            gpu_slot_taken = True
        elif gpu_slot_taken or (len(active_jobs) > max(len(loaded_names), 1) and not has_vram):
            state = "queued"
        else:
            state = "running"

        items.append(
            {
                "job_id": job["id"],
                "kind": job["kind"],
                "label": job["label"],
                "model": job.get("model"),
                "state": state,
                "position": len(items) + 1,
                "message": job.get("message"),
                "phase": job.get("phase"),
            }
        )

    waiting = sum(1 for item in items if item["state"] == "queued")
    on_gpu = sum(1 for item in items if item["state"] == "on_gpu")

    return {
        "depth": len(active_jobs),
        "waiting_count": waiting,
        "on_gpu_count": on_gpu,
        "loaded_slots": len(loaded_names),
        "items": items,
    }


def build_vram_snapshot(
    gpu: dict[str, Any] | None,
    loaded_models: list[dict[str, Any]],
) -> dict[str, Any]:
    """Agrega VRAM total (nvidia-smi) vs modelos Ollama residentes."""
    gpu = gpu or {}
    total_mb = float(gpu.get("memory_total_mb") or 0)
    used_mb = float(gpu.get("memory_used_mb") or 0)

    model_rows: list[dict[str, Any]] = []
    ollama_mb = 0.0
    for row in loaded_models:
        mb = float(row.get("size_vram_mb") or 0)
        ollama_mb += mb
        pct = round(100.0 * mb / total_mb, 1) if total_mb > 0 else 0.0
        model_rows.append(
            {
                "name": row.get("name") or "—",
                "size_vram_mb": round(mb, 1),
                "percent_of_total": pct,
            }
        )

    free_mb = round(max(0.0, total_mb - used_mb), 1) if total_mb > 0 else None
    other_mb = round(max(0.0, used_mb - ollama_mb), 1) if used_mb else None
    used_pct = round(100.0 * used_mb / total_mb, 1) if total_mb > 0 else None

    return {
        "available": bool(gpu.get("available")),
        "total_mb": round(total_mb, 1) if total_mb else None,
        "used_mb": round(used_mb, 1) if used_mb else None,
        "free_mb": free_mb,
        "utilization_percent": gpu.get("percent"),
        "memory_percent": gpu.get("memory_percent") or used_pct,
        "ollama_allocated_mb": round(ollama_mb, 1),
        "other_mb": other_mb,
        "models": model_rows,
    }


def build_live_snapshot() -> dict[str, Any]:
    registry = get_job_registry()
    registry.prune_old()

    ollama = list_running_models()
    benchmark = collect_system_benchmark()
    jobs = registry.list_jobs(active_only=False, limit=30)
    active_jobs = [j for j in jobs if j.get("status") == "running"]
    loaded_models = ollama.get("models") or []
    gpu = benchmark.get("gpu")

    return {
        "timestamp": benchmark.get("timestamp"),
        "ollama": ollama,
        "gpu": gpu,
        "cpu_percent": benchmark.get("cpu", {}).get("percent"),
        "memory_percent": benchmark.get("memory", {}).get("percent"),
        "active_jobs": active_jobs,
        "recent_jobs": jobs,
        "active_job_count": len(active_jobs),
        "loaded_model_count": ollama.get("count", 0),
        "ollama_queue": build_ollama_queue(active_jobs, loaded_models),
        "ops_logs": list_ops_logs(80),
        "vram": build_vram_snapshot(gpu, loaded_models),
    }
