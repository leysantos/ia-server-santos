from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pricing.bootstrap import (
    ensure_providers_registered,
    load_default_bases,
)
from pricing.budget.budget_engine_v2 import BudgetEngineV2
from pricing.budget.price_base_store import STORE as PRICE_BASE_STORE
from pricing.core.pricing_engine import PricingEngine
from pricing.orchestrator.budget_orchestrator import BudgetOrchestrator
from pricing.registry.provider_registry import ProviderRegistry

logger = logging.getLogger(__name__)

PPD_EXAMPLE = Path(__file__).resolve().parents[4] / "planilhas-exemplos" / "19_PPD_MC_OR_R01-Nivel-1-2-Marco2026-14-05-2026.xlsm"


def _safe_upload_basename(filename: str | None, fallback: str) -> str:
    """Evita path traversal quando o browser envia webkitRelativePath no filename."""
    raw = (filename or fallback).replace("\\", "/")
    name = Path(raw).name.strip()
    if not name or name in (".", ".."):
        return fallback
    return name

_pricing_engine: PricingEngine | None = None
_budget_engine: BudgetEngineV2 | None = None
_orchestrator: BudgetOrchestrator | None = None


def _get_engine() -> PricingEngine:
    global _pricing_engine
    ensure_providers_registered()
    _ensure_price_base_loaded()
    if _pricing_engine is None:
        _pricing_engine = PricingEngine()
    return _pricing_engine


def _get_budget_engine() -> BudgetEngineV2:
    global _budget_engine
    if _budget_engine is None:
        _budget_engine = BudgetEngineV2(engine=_get_engine())
    return _budget_engine



def _get_orchestrator() -> BudgetOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        try:
            from config.settings import OLLAMA_BUDGET_TIMEOUT
            from models.ollama_client import OllamaClient

            llm = OllamaClient(timeout=OLLAMA_BUDGET_TIMEOUT)
        except Exception:
            llm = None
        _orchestrator = BudgetOrchestrator(
            budget_engine=_get_budget_engine(),
            llm_client=llm,
        )
    return _orchestrator
def _load_rows_into_sinapi(rows: list[dict], label: str, path: str = "") -> int:
    from pricing.models.price_source import PriceSource

    provider = ProviderRegistry.get("sinapi")
    if not provider or not rows:
        return 0
    provider._data = rows  # noqa: SLF001
    provider._source = PriceSource(  # noqa: SLF001
        name="sinapi",
        label=label,
        item_count=len(rows),
        path=path,
    )
    try:
        from pricing.budget.composition_index import get_composition_index

        index = get_composition_index()
        if not index.is_current(rows, label):
            if len(rows) > 800:
                logger.info(
                    "FAISS: base grande (%s itens) — indexação completa em background; "
                    "matching lexical na base inteira",
                    len(rows),
                )
                index.schedule_rebuild(rows, label=label, source="sinapi")
            else:
                index.rebuild(rows, label=label, source="sinapi")
    except Exception as exc:
        logger.warning("FAISS composições não indexado após load: %s", exc)
    return len(rows)


def _ensure_price_base_loaded() -> dict[str, Any]:
    """Carrega base de preços ativa do catálogo unificado (Configurações)."""
    ensure_providers_registered()

    from core.knowledge.price_registry import load_active_price_rows

    catalog_loaded = load_active_price_rows()
    if catalog_loaded:
        name, rows, entry = catalog_loaded
        _load_rows_into_sinapi(rows, name, entry.get("path", ""))
        return {
            "loaded": True,
            "source": "catalog",
            "base_id": entry.get("id"),
            "base_name": name,
            "item_count": len(rows),
        }

    active_entry, active_rows = PRICE_BASE_STORE.get_active_rows()
    if active_rows:
        _load_rows_into_sinapi(
            active_rows,
            active_entry.name if active_entry else "Base customizada",
            active_entry.id if active_entry else "",
        )
        return {
            "loaded": True,
            "source": "legacy_store",
            "base_id": active_entry.id if active_entry else None,
            "base_name": active_entry.name if active_entry else None,
            "item_count": len(active_rows),
        }

    sinapi = ProviderRegistry.get("sinapi")
    if sinapi and sinapi.is_loaded and len(getattr(sinapi, "_data", []) or []) > 0:
        return {
            "loaded": True,
            "source": "memory",
            "base_id": None,
            "base_name": sinapi.label if sinapi else None,
            "item_count": len(sinapi._data),  # noqa: SLF001
        }

    demo = load_default_bases()
    if demo.get("sinapi"):
        return {
            "loaded": True,
            "source": "demo",
            "base_id": None,
            "base_name": "SINAPI (demo)",
            "item_count": demo["sinapi"],
            "hint": "Base demo — importe a PPD em Configurações para orçamento real",
        }

    return {
        "loaded": False,
        "source": "none",
        "base_id": None,
        "base_name": None,
        "item_count": 0,
        "hint": "Importe uma base de preços em Configurações → Biblioteca de documentos",
    }


def _loaded_provider_names() -> list[str]:
    from pricing.registry.provider_registry import ProviderRegistry

    return [
        p.name
        for p in ProviderRegistry.all()
        if p.is_loaded and len(getattr(p, "_data", []) or []) > 0
    ]


def _ensure_budget_pricing_context(
    session_id: str | None = None,
    source_priority: list[str] | None = None,
) -> list[str]:
    """Carrega bases da sessão de orçamento (SINAPI + SICRO…) ou fallback global."""
    ensure_providers_registered()

    if session_id:
        engine = _get_budget_engine()
        session = engine.get_session(session_id)
        if session:
            selections = [s for s in (session.project.price_bases or []) if s.get("enabled")]
            if selections:
                from pricing.budget.price_base_session import apply_price_bases_selection

                applied = apply_price_bases_selection(selections)
                priority = list(applied.get("source_priority") or [])
                if priority:
                    return priority
            if session.source_priority:
                loaded = _loaded_provider_names()
                filtered = [s for s in session.source_priority if s in loaded]
                if filtered:
                    return filtered

    loaded = _loaded_provider_names()
    if source_priority:
        filtered = [s for s in source_priority if s in loaded]
        if filtered:
            return filtered

    _ensure_price_base_loaded()
    loaded = _loaded_provider_names()
    if source_priority:
        filtered = [s for s in source_priority if s in loaded]
        if filtered:
            return filtered
    return loaded or list(source_priority or ["sinapi"])

def _raise_price_sync_http_error(exc: Exception) -> None:
    from pricing.sync.sinapi_errors import SinapiDownloadError

    if isinstance(exc, SinapiDownloadError):
        raise HTTPException(status_code=503, detail=exc.to_dict()) from exc
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.exception("price sync falhou")
    raise HTTPException(status_code=502, detail=str(exc)) from exc
