"""Coleta de métricas de sistema (CPU, RAM, GPU) para benchmark da aplicação."""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from typing import Any

logger = logging.getLogger(__name__)

_psutil = None


def _get_psutil():
    global _psutil
    if _psutil is None:
        try:
            import psutil

            _psutil = psutil
        except ImportError:
            _psutil = False
    return _psutil if _psutil is not False else None


def _read_gpu_stats() -> dict[str, Any]:
    if not shutil.which("nvidia-smi"):
        return {"available": False, "percent": None, "memory_percent": None}

    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return {"available": False, "percent": None, "memory_percent": None}

        util, mem_used, mem_total = [
            float(x.strip()) for x in result.stdout.strip().split("\n")[0].split(",")
        ]
        mem_pct = round(100.0 * mem_used / mem_total, 1) if mem_total > 0 else 0.0
        return {
            "available": True,
            "percent": round(util, 1),
            "memory_percent": mem_pct,
            "memory_used_mb": round(mem_used, 0),
            "memory_total_mb": round(mem_total, 0),
        }
    except Exception as exc:
        logger.debug("GPU stats unavailable: %s", exc)
        return {"available": False, "percent": None, "memory_percent": None}


def collect_system_benchmark() -> dict[str, Any]:
    psutil = _get_psutil()
    if psutil is None:
        return {
            "available": False,
            "error": "psutil não instalado — pip install psutil",
            "cpu": {"percent": None},
            "memory": {"percent": None},
            "gpu": {"available": False, "percent": None},
        }

    try:
        cpu_percent = psutil.cpu_percent(interval=0.05)
        vm = psutil.virtual_memory()
        gpu = _read_gpu_stats()

        gpu_percent = gpu.get("percent")
        if gpu.get("available") and gpu_percent is None and gpu.get("memory_percent") is not None:
            gpu_percent = gpu["memory_percent"]

        return {
            "available": True,
            "timestamp": time.time(),
            "cpu": {
                "percent": round(float(cpu_percent), 1),
                "cores": psutil.cpu_count(logical=True) or 0,
            },
            "memory": {
                "percent": round(float(vm.percent), 1),
                "used_gb": round(vm.used / (1024**3), 2),
                "total_gb": round(vm.total / (1024**3), 2),
            },
            "gpu": {
                **gpu,
                "percent": gpu_percent,
            },
        }
    except Exception as exc:
        logger.warning("Benchmark collection failed: %s", exc)
        return {
            "available": False,
            "error": str(exc),
            "cpu": {"percent": None},
            "memory": {"percent": None},
            "gpu": {"available": False, "percent": None},
        }
