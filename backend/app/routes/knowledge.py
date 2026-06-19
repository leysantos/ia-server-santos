import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from app.schemas.knowledge import (
    KnowledgeCatalogResponse,
    KnowledgeDocumentDeleteResponse,
    KnowledgeDocumentUpdateRequest,
    KnowledgeDocumentUpdateResponse,
    KnowledgeIndexRequest,
    KnowledgeIndexResponse,
    KnowledgeIngestResponse,
    KnowledgeOptionsResponse,
    KnowledgeStatsResponse,
)
from app.services.knowledge_service import KnowledgeService
from core.concurrency import run_sync

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
    name: Optional[str] = Form(default=None, description="Nome do documento (obrigatório para bases de preço)"),
    description: Optional[str] = Form(default=None, description="Descrição opcional"),
    discipline: Optional[str] = Form(default=None),
    content_type: Optional[str] = Form(default=None),
    layer: str = Form(default="raw"),
    force: bool = Form(default=False),
    dry_run: bool = Form(default=False),
    auto_index: bool = Form(default=True),
    index_base: Optional[str] = Form(default=None),
    register_price_base: bool = Form(default=False),
    register_budget_model: bool = Form(default=False),
):
    """
    Ingestão em lote: classifica, copia para knowledge/raw/documents/,
    grava sidecar + catalog.jsonl. Indexação FAISS roda em background quando auto_index=true.
    """
    try:
        result = await knowledge_service.ingest_files(
            files,
            name=name or None,
            description=description or None,
            discipline=discipline or None,
            content_type=content_type or None,
            layer=layer,
            force=force,
            dry_run=dry_run,
            auto_index=False,
            index_base=index_base or None,
            register_price_base=register_price_base,
            register_budget_model=register_budget_model,
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
async def knowledge_index(request: KnowledgeIndexRequest):
    """Dispara indexação FAISS (uma base ou todas)."""
    try:
        result = await run_sync(
            knowledge_service.run_index,
            base=request.base,
            force=request.force,
        )
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


@router.post("/documents/{document_id}/activate-price-base")
def activate_price_base_document(document_id: str):
    """Define documento do catálogo como base de preços ativa (orçamento)."""
    try:
        return knowledge_service.activate_price_document(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/documents/{document_id}/index-budget-model")
def index_budget_model_document(document_id: str):
    """Extrai WBS de PPD já importado e indexa para consulta da IA."""
    try:
        return knowledge_service.index_budget_model_document(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/documents/{document_id}", response_model=KnowledgeDocumentUpdateResponse)
def update_knowledge_document(document_id: str, body: KnowledgeDocumentUpdateRequest):
    """Atualiza metadados (nome, descrição, tipo, disciplina) de um documento do catálogo."""
    if not any(
        v is not None
        for v in (body.name, body.description, body.content_type, body.discipline)
    ):
        raise HTTPException(status_code=400, detail="Informe ao menos um campo para atualizar")
    try:
        return KnowledgeDocumentUpdateResponse(
            **knowledge_service.update_document(
                document_id,
                name=body.name,
                description=body.description,
                content_type=body.content_type,
                discipline=body.discipline,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Falha ao atualizar documento %s", document_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/documents/{document_id}", response_model=KnowledgeDocumentDeleteResponse)
def delete_knowledge_document(document_id: str):
    """Remove documento do catálogo, disco, sidecars e índices FAISS."""
    try:
        return KnowledgeDocumentDeleteResponse(
            **knowledge_service.delete_document(document_id)
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Falha ao excluir documento %s", document_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
