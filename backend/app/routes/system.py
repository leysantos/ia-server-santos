from fastapi import APIRouter

from core.system.benchmark import collect_system_benchmark

router = APIRouter(tags=["System"])


@router.get("/system/benchmark")
def system_benchmark():
    """Uso atual de CPU, RAM e GPU (servidor backend / WSL)."""
    return collect_system_benchmark()
