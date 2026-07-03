from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from core.concurrency import run_sync
from pricing.bootstrap import (
    _DEFAULT_DATA_DIR,
    ensure_providers_registered,
    reload_all_bases,
    upload_base_file,
)
from pricing.core.price_query import build_price_request, price_item_to_dict
from pricing.registry.provider_registry import ProviderRegistry

from app.routes.pricing.schemas import LoadProviderRequest, ResolveRequest
from pricing.budget.price_base_store import STORE as PRICE_BASE_STORE

from app.routes.pricing.shared import (
    _ensure_price_base_loaded,
    _get_engine,
    _load_rows_into_sinapi,
)

router = APIRouter()

@router.get("/ollama/status")
def ollama_status():
    """Status do Ollama para o módulo de orçamento."""
    from config.settings import OLLAMA_BASE_URL, OLLAMA_BUDGET_MODEL
    from models.ollama_client import OllamaClient

    client = OllamaClient(primary_model=OLLAMA_BUDGET_MODEL)
    available = client.ping()
    models = client.list_models() if available else []
    return {
        "available": available,
        "url": OLLAMA_BASE_URL,
        "budget_model": client.primary_model,
        "budget_model_configured": OLLAMA_BUDGET_MODEL,
        "fallback_model": client.fallback_model,
        "models_installed": models,
        "models": models,
        "hint": None if available else "Execute: ollama serve",
    }

@router.get("/bases")
def list_price_bases():
    """Lista bases de preço importadas pelo usuário."""
    status = _ensure_price_base_loaded()
    return {
        "bases": [b.to_dict() for b in PRICE_BASE_STORE.list_bases()],
        "active": status,
    }


@router.post("/bases/import")
async def import_price_base(
    name: str = Query(..., min_length=1, max_length=80),
    file: UploadFile = File(...),
):
    """Importa base de preço nomeada (CSV, Excel, XML, PDF, JSON, PPD)."""
    suffix = Path(file.filename or "upload.csv").suffix.lower()
    allowed = (".csv", ".xlsx", ".xls", ".json", ".xlsm", ".xml", ".pdf", ".txt")
    if suffix not in allowed:
        raise HTTPException(status_code=400, detail=f"Formato não suportado. Use: {', '.join(allowed)}")

    import_dir = _DEFAULT_DATA_DIR / "uploads"
    import_dir.mkdir(parents=True, exist_ok=True)
    dest = import_dir / (file.filename or f"base{suffix}")
    with dest.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)

    try:
        entry, rows = await run_sync(PRICE_BASE_STORE.import_file, name, dest)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await run_sync(_load_rows_into_sinapi, rows, entry.name, str(dest))
    return {"base": entry.to_dict(), "loaded": len(rows)}


@router.post("/bases/{base_id}/activate")
def activate_price_base(base_id: str):
    try:
        rows = PRICE_BASE_STORE.activate(base_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Base não encontrada") from None
    entry = PRICE_BASE_STORE.get(base_id)
    _load_rows_into_sinapi(rows, entry.name if entry else "Base", base_id)
    return {"activated": base_id, "item_count": len(rows), "base": entry.to_dict() if entry else None}


@router.delete("/bases/{base_id}")
def delete_price_base(base_id: str):
    try:
        removed = PRICE_BASE_STORE.delete(base_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Base não encontrada") from None

    status = _ensure_price_base_loaded()
    return {"deleted": base_id, "removed": removed.to_dict() if removed else None, "active": status}


@router.post("/bases/import-example")
def import_ppd_example_base():
    """Importa planilha PPD de exemplo via catálogo unificado."""
    if not PPD_EXAMPLE.exists():
        raise HTTPException(status_code=404, detail="Planilha exemplo não encontrada")

    from core.knowledge.ingestion import get_ingester

    ingester = get_ingester()
    record = ingester.ingest(
        PPD_EXAMPLE,
        name="SINAPI PPD Mar/2026",
        description="Base de preços extraída da planilha PPD municipal de exemplo",
        content_type_hint="sinapi",
        discipline_hint="ORÇAMENTO",
        register_price_base=True,
        force=True,
    )
    if record.get("status") != "copied":
        raise HTTPException(status_code=400, detail=record.get("reason", "Falha ao importar exemplo"))

    status = _ensure_price_base_loaded()
    return {
        "base": {
            "id": record.get("document_id"),
            "name": "SINAPI PPD Mar/2026",
            "item_count": record.get("price_item_count", 0),
            "active": True,
        },
        "loaded": record.get("price_item_count", 0),
        "reactivated": False,
    }

@router.get("/bdi/types")
def list_bdi_obra_types():
    from pricing.budget.bdi_types import list_obra_bdi_types

    return {"types": list_obra_bdi_types(), "default": "RF"}


@router.get("/bdi/profiles")
def list_bdi_edital_profiles_route():
    from pricing.budget.bdi_edital_profiles import list_bdi_edital_profiles

    return {"profiles": list_bdi_edital_profiles()}


@router.get("/providers")
def list_providers():
    ensure_providers_registered()
    _ensure_price_base_loaded()
    return {
        "data_dir": str(_DEFAULT_DATA_DIR),
        "providers": [
            {
                "name": p.name,
                "label": p.label,
                "loaded": p.is_loaded,
                "item_count": len(p._data) if p.is_loaded else 0,  # noqa: SLF001
                "source": p.source_info.to_dict() if p.source_info else None,
            }
            for p in ProviderRegistry.all()
        ],
    }


@router.post("/bases/reload")
async def reload_bases():
    ensure_providers_registered()
    loaded = await run_sync(reload_all_bases)
    return {"reloaded": loaded, "data_dir": str(_DEFAULT_DATA_DIR)}
@router.get("/tools/references")
def pricing_tools_list_references():
    from pricing.tools.budget_pricing_tools import BudgetPricingTools

    return {"references": BudgetPricingTools.list_references()}


@router.get("/tools/composition/{code}")
def pricing_tools_open_composition(
    code: str,
    uf: str = Query(default="SP", min_length=2, max_length=2),
    reference: str | None = Query(default=None),
    format: str = Query(default="json", pattern="^(json|markdown)$"),
):
    """Consulta CPU aberta no price_bank (ComD/SemD por UF)."""
    from pricing.tools.budget_pricing_tools import BudgetPricingTools

    try:
        comp = BudgetPricingTools.get_open_composition(code, uf=uf.upper(), reference=reference)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if format == "markdown":
        return {
            "markdown": BudgetPricingTools.format_open_composition_markdown(comp),
            "meta": {
                "code": comp.get("code"),
                "uf": comp.get("price_uf"),
                "reference": comp.get("reference"),
            },
        }
    return comp
@router.post("/providers/{name}/load")
def load_provider(name: str, body: LoadProviderRequest):
    ensure_providers_registered()
    provider = ProviderRegistry.get(name)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{name}' não registrado")
    path = Path(body.file_path).resolve()
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Arquivo não encontrado: {path}")
    result = upload_base_file(name, path)
    return {**result, "loaded": True}


@router.post("/providers/{name}/upload")
async def upload_provider_file(name: str, file: UploadFile = File(...)):
    ensure_providers_registered()
    provider = ProviderRegistry.get(name)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{name}' não registrado")

    suffix = Path(file.filename or "upload.csv").suffix.lower()
    if suffix not in (".csv", ".xlsx", ".xls", ".json"):
        raise HTTPException(status_code=400, detail="Formato não suportado")

    dest_dir = _DEFAULT_DATA_DIR / name
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / _safe_upload_basename(file.filename, f"upload{suffix}")

    with dest_path.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)

    result = upload_base_file(name, dest_path)
    return {**result, "uploaded": True, "filename": file.filename}


@router.post("/resolve")
def resolve_price(body: ResolveRequest):
    engine = _get_engine()
    request = build_price_request(
        query=body.query,
        unit=body.unit,
        region=body.region,
        source_priority=body.source_priority,
        limit=body.limit,
    )
    best = engine.resolve(request)
    many = engine.resolve_many(request, best_only=False)
    return {
        "best": price_item_to_dict(best),
        "results": [price_item_to_dict(i) for i in many],
        "query": body.query,
    }
