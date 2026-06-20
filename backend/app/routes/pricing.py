from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.services.budget_db_service import delete_budget, get_budget, list_budgets, save_budget
from app.services.budget_stream_service import BudgetStreamService
from app.services.tech_spec_stream_service import TechSpecStreamService
from core.concurrency import run_sync
from core.llm_override import llm_model_scope
from core.database.connection import get_db

from pricing.bootstrap import (
    _DEFAULT_DATA_DIR,
    ensure_providers_registered,
    load_default_bases,
    reload_all_bases,
    upload_base_file,
)
from pricing.budget.budget_builder import BudgetBuilder
from pricing.budget.budget_engine_v2 import BudgetEngineV2
from pricing.core.price_query import build_price_request, price_item_to_dict
from pricing.core.pricing_engine import PricingEngine
from pricing.orchestrator.budget_orchestrator import BudgetOrchestrator
from pricing.budget.budget_session import SESSION_STORE
from pricing.budget.ppd_parser import extract_price_base_rows, parse_ppd_workbook
from pricing.budget.ppd_template import create_empty_ppd_metadata, create_empty_ppd_tree
from pricing.budget.price_base_store import STORE as PRICE_BASE_STORE
from pricing.budget.project_importer import ProjectImporter
from pricing.registry.provider_registry import ProviderRegistry

router = APIRouter(prefix="/pricing", tags=["Pricing"])
logger = logging.getLogger(__name__)

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


class ResolveRequest(BaseModel):
    query: str = Field(..., min_length=1)
    unit: Optional[str] = None
    region: Optional[str] = None
    source_priority: Optional[list[str]] = None
    limit: int = Field(default=10, ge=1, le=50)


class LoadProviderRequest(BaseModel):
    file_path: str


class BudgetBuildRequest(BaseModel):
    intent: dict[str, Any]
    source_priority: Optional[list[str]] = None


class BudgetGenerateRequest(BaseModel):
    text: str = Field(..., min_length=3)
    source_priority: Optional[list[str]] = None
    use_llm: bool = True
    obra_type: Optional[str] = Field(
        default=None,
        description="Tipo de obra para BDI: ED, RF, FIE, IE, OPMF, SEE, AG",
    )
    existing_session_id: Optional[str] = None


class BudgetSaveRequest(BaseModel):
    title: Optional[str] = None
    input_text: Optional[str] = None
    project_id: Optional[str] = None
    payload: dict[str, Any]


class BudgetRestoreRequest(BaseModel):
    payload: dict[str, Any]


class BdiObraTypeRequest(BaseModel):
    obra_type: str = Field(..., min_length=2, max_length=8)


class CellUpdateRequest(BaseModel):
    row_id: Optional[str] = None
    code: Optional[str] = None
    field: str = Field(..., pattern="^(quantity|unit_price|unit_cost|name|unit|calculation_note)$")
    value: Any


class ProjectUpdateRequest(BaseModel):
    projeto: Optional[str] = None
    nome_obra: Optional[str] = None
    objeto: Optional[str] = None
    local: Optional[str] = None
    endereco: Optional[str] = None
    empresa: Optional[str] = None
    orgao: Optional[str] = None
    responsavel_tecnico: Optional[str] = None
    base_preco: Optional[str] = None
    orcamento: Optional[str] = None
    data_ref: Optional[str] = None
    processo: Optional[str] = None


class EtapaCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class SubEtapaCreateRequest(BaseModel):
    parent_code: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=200)


class EtapaUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class MemoryGenerateRequest(BaseModel):
    group_code: Optional[str] = Field(default=None, description="Código etapa/sub-etapa; vazio = obra inteira")
    use_llm: bool = False
    llm_model: Optional[str] = Field(
        default=None,
        description='Modelo Ollama. Use "auto" ou omita para roteamento automático.',
    )


class ScheduleSettingsRequest(BaseModel):
    project_start: str = Field(..., min_length=8, max_length=10, description="Data de início (ISO YYYY-MM-DD)")


class ScheduleTaskUpdateRequest(BaseModel):
    duration_days: Optional[int] = Field(default=None, ge=1, le=3650)
    manual_start: Optional[str] = Field(default=None, description="Início manual ISO YYYY-MM-DD")


class ScheduleLinkRequest(BaseModel):
    predecessor_id: str = Field(..., min_length=1)
    successor_id: str = Field(..., min_length=1)
    link_type: str = Field(default="FS", pattern="^(FS|SS|FF|SF)$")
    lag_days: int = Field(default=0, ge=0, le=365)


class ScheduleComposeRequest(BaseModel):
    prompt: str = Field(..., min_length=2, max_length=4000)
    use_llm: bool = True
    replace_links: bool = Field(
        default=False,
        description="Se true, remove todos os vínculos antes de aplicar o plano da IA",
    )
    llm_model: Optional[str] = Field(
        default=None,
        description='Modelo Ollama. Use "auto" ou omita para roteamento automático.',
    )


class TechSpecComposeRequest(BaseModel):
    prompt: Optional[str] = Field(
        default=None,
        max_length=8000,
        description="Instruções para gerar ou editar o documento.",
    )
    mode: str = Field(
        default="generate",
        pattern="^(generate|edit)$",
        description="generate = criar do orçamento; edit = alterar documento existente via prompt.",
    )
    use_llm: bool = True
    llm_model: Optional[str] = Field(default=None, description="Modelo Ollama ou auto.")


class TechSpecUpdateRequest(BaseModel):
    title: Optional[str] = None
    markdown: Optional[str] = None
    html_content: Optional[str] = None
    formatting: Optional[dict[str, Any]] = None


class ComposeEtapaRequest(BaseModel):
    prompt: str = Field(..., min_length=2, max_length=4000)
    source_priority: Optional[list[str]] = None
    default_quantity: Optional[float] = Field(
        default=None,
        ge=0,
        description="Quantidade aplicada a todos os termos sem quantidade individual",
    )
    replace_existing: bool = Field(
        default=False,
        description="Se true, remove serviços atuais do grupo antes de compor",
    )


class ReplaceServiceRequest(BaseModel):
    code: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    price: Optional[float] = None
    source: Optional[str] = "sinapi"
    query: Optional[str] = None


class ApplyGroupQuantityRequest(BaseModel):
    quantity: float = Field(..., ge=0)
    include_subgroups: bool = Field(
        default=True,
        description="Se true, aplica também aos serviços das sub-etapas",
    )


class AddServiceRequest(BaseModel):
    etapa_code: str = Field(..., min_length=1)
    code: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    price: Optional[float] = None
    source: Optional[str] = "sinapi"
    quantity: float = Field(default=1.0, ge=0)
    query: Optional[str] = None


class SearchPriceRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(default=15, ge=1, le=50)
    source_priority: Optional[list[str]] = None


PPD_EXAMPLE = Path(__file__).resolve().parents[3] / "planilhas-exemplos" / "19_PPD_MC_OR_R01-Nivel-1-2-Marco2026-14-05-2026.xlsm"


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


@router.post("/budget/new-template")
def create_ppd_template(
    obra_type: str = Query(default="RF"),
    projeto: str = Query(default=""),
):
    """Cria sessão vazia no template PPD municipal padrão."""
    from pricing.budget.bdi_types import normalize_obra_type

    meta = create_empty_ppd_metadata(projeto=projeto, obra_type=normalize_obra_type(obra_type))
    roots = create_empty_ppd_tree(meta)
    session = SESSION_STORE.create(
        roots=roots,
        title=meta.projeto,
        intent={"template": True},
        project=meta,
    )
    return session.to_dict()


@router.post("/budget/import-project")
async def import_project_budget(
    file: UploadFile = File(...),
    use_llm: bool = Query(default=True),
    obra_type: Optional[str] = Query(default=None),
):
    """Importa documento de projeto — IA extrai quantitativos e gera orçamento."""
    suffix = Path(file.filename or "doc.pdf").suffix.lower()
    allowed = (".pdf", ".docx", ".xlsx", ".xls", ".txt", ".md", ".csv", ".json", ".rtf")
    if suffix not in allowed:
        raise HTTPException(status_code=400, detail=f"Formato não suportado: {suffix}")

    import_dir = _DEFAULT_DATA_DIR / "projects"
    import_dir.mkdir(parents=True, exist_ok=True)
    dest = import_dir / (file.filename or f"project{suffix}")
    with dest.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)

    _ensure_price_base_loaded()
    importer = ProjectImporter(_get_orchestrator())
    try:
        return importer.import_and_generate(dest, use_llm=use_llm, obra_type=obra_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/bdi/types")
def list_bdi_obra_types():
    from pricing.budget.bdi_types import list_obra_bdi_types

    return {"types": list_obra_bdi_types(), "default": "RF"}


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
    dest_path = dest_dir / (file.filename or f"upload{suffix}")

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


@router.post("/budget/build")
def build_budget(body: BudgetBuildRequest):
    builder = BudgetBuilder(engine=_get_engine())
    return builder.build_dict(body.intent, body.source_priority)


@router.post("/budget/generate")
def generate_budget(body: BudgetGenerateRequest):
    """Pipeline completo: LLM → Quantity → Pricing → Budget v2."""
    _ensure_price_base_loaded()
    orchestrator = _get_orchestrator()
    return orchestrator.run(
        body.text,
        source_priority=body.source_priority or ["sinapi"],
        use_llm=body.use_llm,
        obra_type=body.obra_type,
    )


@router.post("/budget/generate/stream")
def generate_budget_stream(body: BudgetGenerateRequest):
    """Pipeline com SSE — tokens LLM e etapas em tempo real."""
    _ensure_price_base_loaded()
    service = BudgetStreamService(orchestrator=_get_orchestrator())
    return StreamingResponse(
        service.stream(
            body.text,
            source_priority=body.source_priority or ["sinapi"],
            use_llm=body.use_llm,
            obra_type=body.obra_type,
            existing_session_id=body.existing_session_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


@router.get("/budget/saved")
def list_saved_budgets(
    project_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    try:
        return {"items": list_budgets(db, project_id=project_id)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Banco indisponível: {exc}") from exc


@router.get("/budget/saved/{budget_id}")
def get_saved_budget(budget_id: str, db: Session = Depends(get_db)):
    try:
        payload = get_budget(db, budget_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Banco indisponível: {exc}") from exc
    if not payload:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")
    return payload


@router.post("/budget/saved")
def create_saved_budget(body: BudgetSaveRequest, db: Session = Depends(get_db)):
    try:
        return save_budget(
            db,
            body.payload,
            title=body.title,
            input_text=body.input_text,
            project_id=body.project_id,
        )
    except Exception as exc:
        if "indisponível" in str(exc).lower() or "connection" in str(exc).lower():
            raise HTTPException(status_code=503, detail=f"Banco indisponível — rode make db-init ou docker-up: {exc}") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/budget/saved/{budget_id}")
def update_saved_budget(budget_id: str, body: BudgetSaveRequest, db: Session = Depends(get_db)):
    try:
        return save_budget(
            db,
            body.payload,
            title=body.title,
            input_text=body.input_text,
            budget_id=budget_id,
            project_id=body.project_id,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado") from None
    except Exception as exc:
        if "connection" in str(exc).lower():
            raise HTTPException(status_code=503, detail=f"Banco indisponível: {exc}") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/budget/saved/{budget_id}")
def remove_saved_budget(budget_id: str, db: Session = Depends(get_db)):
    try:
        if not delete_budget(db, budget_id):
            raise HTTPException(status_code=404, detail="Orçamento não encontrado")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Banco indisponível: {exc}") from exc
    return {"deleted": budget_id}


@router.post("/budget/restore")
def restore_budget_session(body: BudgetRestoreRequest):
    """Reidrata sessão em memória a partir do payload (ex.: após restart do backend)."""
    from app.services.budget_db_service import session_from_payload

    payload = body.payload
    if not payload.get("items") and not payload.get("rows"):
        raise HTTPException(status_code=400, detail="Payload inválido: sem itens da sessão")
    session = session_from_payload(payload)
    return session.to_dict()


@router.get("/budget/{session_id}")
def get_budget_session(session_id: str):
    engine = _get_budget_engine()
    session = engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    return session.to_dict()


@router.patch("/budget/{session_id}/bdi")
def update_budget_bdi(session_id: str, body: BdiObraTypeRequest):
    from pricing.budget.bdi_types import normalize_obra_type

    engine = _get_budget_engine()
    try:
        session = engine.set_obra_type(session_id, normalize_obra_type(body.obra_type))
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    return session.to_dict()


@router.post("/budget/{session_id}/subetapas")
def create_budget_subetapa(session_id: str, body: SubEtapaCreateRequest):
    engine = _get_budget_engine()
    try:
        session = engine.add_subetapa(session_id, body.parent_code, body.name)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return session.to_dict()


@router.post("/budget/{session_id}/memory/generate")
def generate_budget_memories(session_id: str, body: MemoryGenerateRequest):
    engine = _get_budget_engine()
    try:
        with llm_model_scope(body.llm_model):
            session, log = engine.generate_memories(
                session_id,
                group_code=body.group_code,
                use_llm=body.use_llm,
            )
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"session": session.to_dict(), "memory_log": log}


@router.get("/budget/{session_id}/schedule")
def get_budget_schedule(session_id: str):
    engine = _get_budget_engine()
    try:
        session = engine.get_schedule(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    return {"schedule": session.schedule.to_dict() if session.schedule else None}


@router.post("/budget/{session_id}/schedule/sync")
def sync_budget_schedule(session_id: str):
    engine = _get_budget_engine()
    try:
        session = engine.sync_schedule(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    return session.to_dict()


@router.post("/budget/{session_id}/schedule/recalculate")
def recalculate_budget_schedule(session_id: str):
    engine = _get_budget_engine()
    try:
        session = engine.recalculate_schedule(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    return session.to_dict()


@router.patch("/budget/{session_id}/schedule/settings")
def update_budget_schedule_settings(session_id: str, body: ScheduleSettingsRequest):
    engine = _get_budget_engine()
    try:
        session = engine.update_schedule_settings(session_id, project_start=body.project_start)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    return session.to_dict()


@router.patch("/budget/{session_id}/schedule/tasks/{task_id}")
def update_budget_schedule_task(session_id: str, task_id: str, body: ScheduleTaskUpdateRequest):
    engine = _get_budget_engine()
    try:
        session = engine.update_schedule_task(
            session_id,
            task_id,
            duration_days=body.duration_days,
            manual_start=body.manual_start,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return session.to_dict()


@router.post("/budget/{session_id}/schedule/links")
def add_budget_schedule_link(session_id: str, body: ScheduleLinkRequest):
    engine = _get_budget_engine()
    try:
        session = engine.add_schedule_link(
            session_id,
            body.predecessor_id,
            body.successor_id,
            link_type=body.link_type,
            lag_days=body.lag_days,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return session.to_dict()


@router.delete("/budget/{session_id}/schedule/links/{link_id}")
def delete_budget_schedule_link(session_id: str, link_id: str):
    engine = _get_budget_engine()
    try:
        session = engine.remove_schedule_link(session_id, link_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    return session.to_dict()


@router.post("/budget/{session_id}/schedule/compose")
def compose_budget_schedule(session_id: str, body: ScheduleComposeRequest):
    engine = _get_budget_engine()
    try:
        with llm_model_scope(body.llm_model):
            session, log, summary, llm_model = engine.compose_schedule(
                session_id,
                body.prompt,
                use_llm=body.use_llm,
                replace_links=body.replace_links,
            )
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "session": session.to_dict(),
        "schedule_log": log,
        "summary": summary,
        "llm_model": llm_model,
    }


@router.get("/budget/{session_id}/tech-spec")
def get_budget_tech_spec(session_id: str):
    engine = _get_budget_engine()
    try:
        spec = engine.get_tech_spec(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    return {"tech_spec": spec}


@router.put("/budget/{session_id}/tech-spec")
def update_budget_tech_spec(session_id: str, body: TechSpecUpdateRequest):
    engine = _get_budget_engine()
    try:
        session = engine.update_tech_spec(session_id, body.model_dump(exclude_none=True))
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    return {"tech_spec": session.tech_spec, "session": session.to_dict()}


@router.post("/budget/{session_id}/tech-spec/compose/stream")
def compose_budget_tech_spec_stream(session_id: str, body: TechSpecComposeRequest):
    service = TechSpecStreamService()
    with llm_model_scope(body.llm_model):
        return StreamingResponse(
            service.stream(
                session_id,
                body.prompt or "",
                mode="edit" if body.mode == "edit" else "generate",
                use_llm=body.use_llm,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Content-Type": "text/event-stream; charset=utf-8",
            },
        )


@router.get("/budget/{session_id}/tech-spec/export")
def export_budget_tech_spec(session_id: str):
    engine = _get_budget_engine()
    try:
        content = engine.export_tech_spec_docx(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="especificacao_tecnica_{session_id[:8]}.docx"'
        },
    )


@router.patch("/budget/{session_id}/project")
def update_budget_project(session_id: str, body: ProjectUpdateRequest):
    engine = _get_budget_engine()
    try:
        session = engine.update_project(session_id, body.model_dump(exclude_none=True))
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    return session.to_dict()


@router.post("/budget/{session_id}/etapas")
def create_budget_etapa(session_id: str, body: EtapaCreateRequest):
    engine = _get_budget_engine()
    try:
        session = engine.add_etapa(session_id, body.name)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    return session.to_dict()


@router.patch("/budget/{session_id}/etapas/{etapa_code}")
def update_budget_etapa(session_id: str, etapa_code: str, body: EtapaUpdateRequest):
    engine = _get_budget_engine()
    try:
        session = engine.update_etapa(session_id, etapa_code, body.name)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return session.to_dict()


@router.delete("/budget/{session_id}/rows/{row_id}")
def delete_budget_row(session_id: str, row_id: str):
    engine = _get_budget_engine()
    try:
        session = engine.delete_row(session_id, row_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return session.to_dict()


@router.post("/budget/{session_id}/itemization/renumber")
def renumber_budget_itemization(session_id: str):
    engine = _get_budget_engine()
    try:
        session, mapping = engine.renumber_itemization(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    payload = session.to_dict()
    payload["renumber_result"] = {"changed_count": len(mapping), "mapping": mapping}
    return payload


@router.get("/budget/{session_id}/groups/{group_code}/compose-prompt")
def get_group_compose_prompt(session_id: str, group_code: str):
    engine = _get_budget_engine()
    try:
        prompt, count = engine.get_group_compose_prompt(session_id, group_code)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"prompt": prompt, "service_count": count}


@router.post("/budget/{session_id}/etapas/{etapa_code}/compose")
def compose_budget_etapa(session_id: str, etapa_code: str, body: ComposeEtapaRequest):
    _ensure_price_base_loaded()
    engine = _get_budget_engine()
    try:
        session, log, removed = engine.compose_etapa(
            session_id,
            etapa_code,
            body.prompt,
            source_priority=body.source_priority or ["sinapi"],
            default_quantity=body.default_quantity,
            replace_existing=body.replace_existing,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"session": session.to_dict(), "compose_log": log, "removed_count": removed}


@router.post("/budget/{session_id}/services/{row_id}/replace")
def replace_budget_service(session_id: str, row_id: str, body: ReplaceServiceRequest):
    _ensure_price_base_loaded()
    engine = _get_budget_engine()
    pricing = _get_engine()

    price_data: dict[str, Any]
    if body.code or body.description:
        price_data = {
            "code": body.code or "",
            "description": body.description or "",
            "unit": body.unit or "",
            "price": body.price or 0,
            "source": body.source or "sinapi",
        }
    elif body.query:
        from pricing.budget.budget_structure import parse_term_hints

        q, unit_hint, _ = parse_term_hints(body.query)
        request = build_price_request(q, unit=unit_hint, limit=1)
        item = pricing.resolve(request)
        if not item:
            raise HTTPException(status_code=404, detail="Serviço não encontrado na base de preços")
        price_data = price_item_to_dict(item) or {}
        if unit_hint:
            price_data["unit_hint"] = unit_hint
        price_data["query"] = q
    else:
        raise HTTPException(status_code=400, detail="Informe code/description ou query")

    try:
        session = engine.replace_service(session_id, row_id, price_data)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return session.to_dict()


@router.post("/budget/{session_id}/groups/{group_code}/apply-quantity")
def apply_group_quantity(session_id: str, group_code: str, body: ApplyGroupQuantityRequest):
    engine = _get_budget_engine()
    try:
        session, count = engine.apply_group_quantity(
            session_id,
            group_code,
            body.quantity,
            include_subgroups=body.include_subgroups,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"session": session.to_dict(), "updated_count": count}


@router.post("/budget/{session_id}/services")
def add_budget_service(session_id: str, body: AddServiceRequest):
    _ensure_price_base_loaded()
    engine = _get_budget_engine()
    pricing = _get_engine()

    price_data: dict[str, Any]
    quantity = body.quantity
    if body.code or body.description:
        price_data = {
            "code": body.code or "",
            "description": body.description or "",
            "unit": body.unit or "",
            "price": body.price or 0,
            "source": body.source or "sinapi",
        }
    elif body.query:
        from pricing.budget.budget_structure import parse_term_hints

        q, unit_hint, term_qty = parse_term_hints(body.query)
        request = build_price_request(q, unit=unit_hint, source_priority=body.source_priority, limit=1)
        item = pricing.resolve(request)
        if not item:
            raise HTTPException(status_code=404, detail="Serviço não encontrado na base de preços")
        price_data = price_item_to_dict(item) or {}
        if unit_hint:
            price_data["unit_hint"] = unit_hint
        quantity = term_qty if term_qty is not None else body.quantity
    else:
        raise HTTPException(status_code=400, detail="Informe code/description ou query")

    try:
        session = engine.add_service(
            session_id,
            body.etapa_code,
            price_data,
            quantity=quantity if body.query else body.quantity,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return session.to_dict()


@router.post("/budget/search")
def search_price_items(body: SearchPriceRequest):
    from pricing.budget.budget_structure import parse_term_hints

    _ensure_price_base_loaded()
    engine = _get_engine()
    query, unit_hint, parsed_qty = parse_term_hints(body.query)
    request = build_price_request(
        query or body.query,
        unit=unit_hint,
        source_priority=body.source_priority,
        limit=body.limit,
    )
    results = engine.resolve_many(request, best_only=False)
    if unit_hint and results:
        preferred = [r for r in results if r.unit and r.unit.upper() == unit_hint]
        if preferred:
            results = preferred + [r for r in results if r not in preferred]
    return {
        "query": body.query,
        "parsed_query": query,
        "unit_hint": unit_hint,
        "parsed_quantity": parsed_qty,
        "parsed": {
            "query": query,
            "unit_hint": unit_hint,
            "quantity": parsed_qty,
        },
        "results": [price_item_to_dict(i) for i in results],
        "count": len(results),
    }


@router.post("/budget/import-model-template")
async def import_model_template(
    file: UploadFile = File(...),
    session_id: Optional[str] = Query(default=None),
    include_services: bool = Query(default=False),
):
    """Importa etapas de planilha modelo de orçamento (PPD/WBS)."""
    suffix = Path(file.filename or "model.xlsm").suffix.lower()
    if suffix not in (".xlsm", ".xlsx", ".xls"):
        raise HTTPException(status_code=400, detail="Formato inválido — use .xlsm/.xlsx")

    import_dir = _DEFAULT_DATA_DIR / "imports"
    import_dir.mkdir(parents=True, exist_ok=True)
    dest = import_dir / (file.filename or f"model{suffix}")
    with dest.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)

    from core.knowledge.regional_budget_indexer import extract_regional_budget_model
    from pricing.budget.budget_structure import import_etapas_from_sidecar
    from pricing.budget.ppd_template import create_empty_ppd_metadata

    model = extract_regional_budget_model(dest)
    etapas_data = model.get("etapas") or []
    if not etapas_data:
        raise HTTPException(status_code=400, detail="Nenhuma etapa detectada no modelo")

    engine = _get_budget_engine()
    if session_id:
        session = engine.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Sessão não encontrada")
        count = import_etapas_from_sidecar(
            session.roots,
            etapas_data,
            session.project,
            include_services=include_services,
        )
        session.title = session.title or model.get("projeto") or dest.stem
        if model.get("projeto") and not session.project.projeto:
            session.project.projeto = str(model["projeto"])
        from pricing.budget.budget_structure import refresh_calculation_memory

        session.calculation_memory = refresh_calculation_memory(session.roots)
        return {**session.to_dict(), "imported_etapas": count}

    meta = create_empty_ppd_metadata(
        projeto=str(model.get("projeto") or dest.stem),
        obra_type=str(model.get("obra_type") or "RF"),
    )
    roots: list = []
    count = import_etapas_from_sidecar(roots, etapas_data, meta, include_services=include_services)
    session = SESSION_STORE.create(
        roots=roots,
        title=meta.projeto,
        intent={"imported_template": True},
        project=meta,
    )
    return {**session.to_dict(), "imported_etapas": count}


@router.patch("/budget/{session_id}/cell")
def update_budget_cell(session_id: str, body: CellUpdateRequest):
    if not body.row_id and not body.code:
        raise HTTPException(status_code=400, detail="Informe row_id ou code")
    engine = _get_budget_engine()
    try:
        session = engine.update_cell(
            session_id,
            body.row_id or "",
            body.field,
            body.value,
            code=body.code,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return session.to_dict()


@router.get("/budget/{session_id}/export")
def export_budget_excel(session_id: str, format: str = Query(default="ppd")):
    engine = _get_budget_engine()
    session = engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    content = session.export_xlsx(format=format)
    filename = f"PPD_OR_{session_id[:8]}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def import_ppd_from_path(source_path: Path, load_base: bool = True) -> dict[str, Any]:
    """Importa PPD de caminho local (sync — usado por API e testes)."""
    ensure_providers_registered()
    metadata, roots, info = parse_ppd_workbook(source_path)
    base_loaded = 0
    if load_base:
        base_rows = extract_price_base_rows(source_path)
        if base_rows:
            provider = ProviderRegistry.get("sinapi")
            if provider:
                provider._data = base_rows  # noqa: SLF001
                from pricing.models.price_source import PriceSource
                provider._source = PriceSource(  # noqa: SLF001
                    name="sinapi",
                    label="SINAPI (PPD Base)",
                    item_count=len(base_rows),
                    path=str(source_path),
                )
                base_loaded = len(base_rows)

    session = SESSION_STORE.create(
        roots=roots,
        title=metadata.projeto or metadata.objeto or "Orçamento PPD",
        intent={"imported": True, "project": metadata.to_dict()},
        project=metadata,
    )
    session.calculation_memory = [{"step": "import", "source": str(source_path), **info}]
    return {
        **session.to_dict(),
        "import_info": {**info, "base_loaded": base_loaded, "path": str(source_path)},
    }


@router.post("/budget/import-ppd")
async def import_ppd_budget(
    file: UploadFile | None = File(default=None),
    load_base: bool = Query(default=True),
):
    """Importa planilha PPD MC/OR (.xlsm/.xlsx) como sessão editável."""
    if file and file.filename:
        suffix = Path(file.filename).suffix.lower()
        if suffix not in (".xlsm", ".xlsx", ".xls"):
            raise HTTPException(status_code=400, detail="Formato PPD inválido")
        import_dir = _DEFAULT_DATA_DIR / "imports"
        import_dir.mkdir(parents=True, exist_ok=True)
        dest = import_dir / file.filename
        with dest.open("wb") as handle:
            shutil.copyfileobj(file.file, handle)
        source_path = dest
    elif PPD_EXAMPLE.exists():
        source_path = PPD_EXAMPLE
    else:
        raise HTTPException(status_code=400, detail="Envie um arquivo PPD ou configure planilha-exemplo")

    return import_ppd_from_path(source_path, load_base=load_base)


@router.post("/budget/load-ppd-example")
def load_ppd_example_base():
    """Carrega aba Base da planilha PPD de exemplo no provider SINAPI."""
    ensure_providers_registered()
    if not PPD_EXAMPLE.exists():
        raise HTTPException(status_code=404, detail="Planilha exemplo não encontrada")
    rows = extract_price_base_rows(PPD_EXAMPLE)
    provider = ProviderRegistry.get("sinapi")
    if not provider:
        raise HTTPException(status_code=500, detail="Provider sinapi não registrado")
    provider._data = rows  # noqa: SLF001
    from pricing.models.price_source import PriceSource
    provider._source = PriceSource(
        name="sinapi",
        label="SINAPI PPD Março/2026",
        item_count=len(rows),
        path=str(PPD_EXAMPLE),
        metadata={"sheet": "Base_Março2026-copia"},
    )
    return {"loaded": len(rows), "source": str(PPD_EXAMPLE)}
