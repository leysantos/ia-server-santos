from __future__ import annotations

from fastapi import APIRouter

from app.routes.pricing import budget, export, providers, sync, tech_spec
from app.routes.pricing.budget import (
    build_budget,
    generate_budget,
    import_ppd_from_path,
    update_budget_cell,
)
from app.routes.pricing.providers import resolve_price
from app.routes.pricing.schemas import (
    BudgetBuildRequest,
    BudgetGenerateRequest,
    CellUpdateRequest,
    ResolveRequest,
)

router = APIRouter(prefix="/pricing", tags=["Pricing"])
router.include_router(providers.router)
router.include_router(sync.router)
router.include_router(budget.router)
router.include_router(tech_spec.router)
router.include_router(export.router)

__all__ = [
    "router",
    "ResolveRequest",
    "resolve_price",
    "BudgetBuildRequest",
    "build_budget",
    "BudgetGenerateRequest",
    "generate_budget",
    "update_budget_cell",
    "CellUpdateRequest",
    "import_ppd_from_path",
]
