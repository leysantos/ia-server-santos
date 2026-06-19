import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from app.schemas.knowledge import (
    KnowledgeCatalogResponse,
    KnowledgeIndexRequest,
    KnowledgeIndexResponse,
    KnowledgeIngestResponse,
    KnowledgeOptionsResponse,
    KnowledgeStatsResponse,
)
from app.services.knowledge_service import KnowledgeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])
knowledge_service = KnowledgeService()


@router.get("/options", response_model=KnowledgeOptionsResponse)
def knowledge_options():
    """Disciplinas, tipos de conteúdo e bases FAISS para o formulário de upload."""
    return KnowledgeOptionsResponse(**knowledge_service.get_options())


@router.get("/stats", response_model=KnowledgeStatsResponse)
def knowledge_stats():
    """Estatísticas do catálogo e índices FAISS."""
    return KnowledgeStatsResponse(**knowledge_service.get_stats())


@router.get("/catalog", response_model=KnowledgeCatalogResponse)
def knowledge_catalog(limit: int = 100):
    """Últimos documentos ingeridos (catalog.jsonl)."""
    limit = max(1, min(limit, 500))
    return KnowledgeCatalogResponse(**knowledge_service.get_catalog(limit=limit))


@router.post("/ingest", response_model=KnowledgeIngestResponse)
async def knowledge_ingest(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(..., description="Um ou mais arquivos (PDF, CSV, Excel, …)"),
    discipline: Optional[str] = Form(default=None),
    content_type: Optional[str] = Form(default=None),
    layer: str = Form(default="raw"),
    force: bool = Form(default=False),
    dry_run: bool = Form(default=False),
    auto_index: bool = Form(default=True),
    index_base: Optional[str] = Form(default=None),
):
    """
    Ingestão em lote: classifica, copia para knowledge/raw/documents/,
    grava sidecar + catalog.jsonl. Indexação FAISS roda em background quando auto_index=true.
    """
    try:
        result = await knowledge_service.ingest_files(
            files,
            discipline=discipline or None,
            content_type=content_type or None,
            layer=layer,
            force=force,
            dry_run=dry_run,
            auto_index=False,
            index_base=index_base or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Falha na ingestão de knowledge")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if auto_index and not dry_run and result.get("ingested", 0) > 0:
        content_types = {
            (r.get("classification") or {}).get("content_type")
            for r in result.get("results", [])
            if r.get("status") == "copied"
        }
        background_tasks.add_task(
            knowledge_service.run_index,
            base=index_base,
            force=force,
            content_types=content_types,
        )
        result["indexing"] = {
            "status": "scheduled",
            "message": "Indexação FAISS iniciada em background",
            "base": index_base,
        }

    return KnowledgeIngestResponse(**result)


@router.post("/index", response_model=KnowledgeIndexResponse)
def knowledge_index(request: KnowledgeIndexRequest):
    """Dispara indexação FAISS (uma base ou todas)."""
    try:
        result = knowledge_service.run_index(base=request.base, force=request.force)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Falha na indexação de knowledge")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if "bases" in result:
        return KnowledgeIndexResponse(
            bases=result.get("bases", {}),
            total_chunks=result.get("total_chunks", 0),
            total_chunks_in_store=result.get("total_chunks_in_store", 0),
            errors=result.get("errors", []),
        )

    base_key = result.get("base", "")
    return KnowledgeIndexResponse(
        bases={base_key: result},
        total_chunks=result.get("indexed_chunks", 0),
        total_chunks_in_store=result.get("indexed_chunks", 0),
        errors=result.get("errors", []),
    )
