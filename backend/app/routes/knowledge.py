import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response, StreamingResponse

from app.schemas.knowledge import (
    KnowledgeCatalogResponse,
    KnowledgeDocumentDeleteResponse,
    KnowledgeDocumentUpdateRequest,
    KnowledgeDocumentUpdateResponse,
    KnowledgePurgeGenericLegislationResponse,
    KnowledgeMaintenanceRequest,
    KnowledgeMaintenanceResponse,
    DocumentTypePreset,
    DocumentTypePresetCreateRequest,
    DocumentTypePresetListResponse,
    DocumentTypePresetUpdateRequest,
    KnowledgeIndexRequest,
    KnowledgeIndexResponse,
    KnowledgeIngestResponse,
    KnowledgeWebIngestRequest,
    KnowledgeWebIngestResponse,
    NormPackAnalyzeResponse,
    NormPackIndexRequest,
    NormPackIndexResponse,
    NormPackPreviewResponse,
    NormPackListResponse,
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
    """Disciplinas, tipos de conteúdo, presets e bases FAISS para o formulário de upload."""
    return KnowledgeOptionsResponse(**knowledge_service.get_options())


@router.get("/document-type-presets", response_model=DocumentTypePresetListResponse)
def list_document_type_presets():
    """Lista tipos de documento configuráveis (rótulo + disciplina + tipo de conteúdo)."""
    return DocumentTypePresetListResponse(**knowledge_service.list_document_type_presets())


@router.post("/document-type-presets", response_model=DocumentTypePreset)
def create_document_type_preset(body: DocumentTypePresetCreateRequest):
    try:
        return DocumentTypePreset(**knowledge_service.create_document_type_preset(body.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/document-type-presets/{preset_id}", response_model=DocumentTypePreset)
def update_document_type_preset(preset_id: str, body: DocumentTypePresetUpdateRequest):
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(status_code=400, detail="Informe ao menos um campo para atualizar")
    try:
        return DocumentTypePreset(**knowledge_service.update_document_type_preset(preset_id, payload))
    except ValueError as exc:
        status = 404 if "não encontrado" in str(exc).lower() else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.delete("/document-type-presets/{preset_id}", response_model=DocumentTypePreset)
def delete_document_type_preset(preset_id: str):
    try:
        return DocumentTypePreset(**knowledge_service.delete_document_type_preset(preset_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/stats", response_model=KnowledgeStatsResponse)
def knowledge_stats():
    """Estatísticas do catálogo e índices FAISS."""
    return KnowledgeStatsResponse(**knowledge_service.get_stats())


@router.get("/catalog", response_model=KnowledgeCatalogResponse)
def knowledge_catalog(limit: int = Query(default=5000, ge=1, le=20000)):
    """Documentos do catálogo (deduplicados por path, mais recentes primeiro)."""
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


@router.post("/ingest-web", response_model=KnowledgeWebIngestResponse)
async def knowledge_ingest_web(body: KnowledgeWebIngestRequest):
    """
    Importa em lote documentos de uma página web (tabela de anexos com links Baixar).
    Baixa, ingere no catálogo e opcionalmente indexa FAISS.
    """
    try:
        result = await knowledge_service.ingest_from_web(
            page_url=body.page_url,
            discipline=body.discipline,
            content_type=body.content_type,
            description_prefix=body.description_prefix or "",
            max_files=body.max_files,
            force=body.force,
            auto_index=body.auto_index,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Falha na ingestão web de knowledge")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return KnowledgeWebIngestResponse(**result)


@router.post("/ingest-web/stream")
async def knowledge_ingest_web_stream(body: KnowledgeWebIngestRequest):
    """Importação web com progresso em tempo real (SSE)."""
    try:
        validate = body.page_url.strip()
        if len(validate) < 8:
            raise ValueError("URL inválida")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    def event_stream():
        try:
            for chunk in knowledge_service.ingest_from_web_stream_events(
                page_url=body.page_url,
                discipline=body.discipline,
                content_type=body.content_type,
                description_prefix=body.description_prefix or "",
                max_files=body.max_files,
                force=body.force,
                auto_index=body.auto_index,
            ):
                yield chunk
        except ValueError as exc:
            from core.stream_events import format_sse

            yield format_sse("error", {"error": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


@router.post("/ingest-norms/stream")
async def knowledge_ingest_norms_stream(request: Request):
    """
    Importação em lote de PDFs NBR/NR com classificação automática (SSE).

    Classifica por nome do arquivo → texto da 1ª página → IA leve (opcional).
    Indexação FAISS da base NBR roda uma vez ao final quando auto_index=true.
    """
    from core.knowledge.norm_bulk.constants import NORM_BULK_MAX_FILES

    from core.knowledge.norm_bulk.constants import NORM_BULK_MAX_FILES
    from core.knowledge.norm_bulk.upload_utils import extract_upload_files, is_upload_file

    def _form_bool(value: object | None) -> bool:
        return str(value or "").lower() in {"true", "1", "yes", "on"}

    form = await request.form(max_files=NORM_BULK_MAX_FILES, max_fields=32)

    files = extract_upload_files(form)
    force = _form_bool(form.get("force"))
    use_ai_fallback = _form_bool(form.get("use_ai_fallback"))
    mark_edition_outdated = _form_bool(form.get("mark_edition_outdated"))
    auto_index = _form_bool(form.get("auto_index")) if form.get("auto_index") is not None else True

    if not files:
        raise HTTPException(status_code=400, detail="Envie ao menos um PDF")

    try:
        tmp_dir, saved, pre_errors = await knowledge_service.save_norm_uploads(
            files,
            max_files=NORM_BULK_MAX_FILES,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not saved and pre_errors:
        raise HTTPException(status_code=400, detail=pre_errors[0].get("error", "Nenhum PDF válido"))

    def event_stream():
        try:
            for chunk in knowledge_service.ingest_norms_stream_events(
                saved,
                force=force,
                use_ai_fallback=use_ai_fallback,
                mark_edition_outdated=mark_edition_outdated,
                auto_index=auto_index,
                pre_errors=pre_errors,
                cleanup_dir=tmp_dir,
            ):
                yield chunk
        except ValueError as exc:
            from core.stream_events import format_sse

            yield format_sse("error", {"error": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


@router.get("/ingest-web/preview")
async def knowledge_ingest_web_preview(page_url: str):
    """Lista links detectados numa página (sem baixar)."""
    from core.knowledge.web_ingest.downloader import fetch_page_html
    from core.knowledge.web_ingest.parser import preview_download_links
    from core.knowledge.web_ingest.security import UnsafeURLError, validate_public_http_url

    try:
        validate_public_http_url(page_url)
        html = await run_sync(fetch_page_html, page_url)
        links = preview_download_links(html, page_url)
    except (UnsafeURLError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Preview web ingest falhou")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"page_url": page_url, "discovered": len(links), "links": links}


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


@router.post("/documents/purge-generic-legislation", response_model=KnowledgePurgeGenericLegislationResponse)
def purge_generic_legislation_imports(dry_run: bool = False):
    """
    Remove documentos importados da web com nome genérico «Instrução Técnica» + arquivo numérico (87.pdf).
    Use dry_run=true para apenas listar o que seria removido.
    """
    return KnowledgePurgeGenericLegislationResponse(
        **knowledge_service.purge_generic_legislation_imports(dry_run=dry_run)
    )


@router.post("/maintenance", response_model=KnowledgeMaintenanceResponse)
def knowledge_maintenance(body: KnowledgeMaintenanceRequest | None = None):
    """
    Manutenção da base NBR: órfãos, dedup catálogo, metadata 9077/14833,
    compact FAISS e indexação de PDFs pendentes (PyMuPDF + OCR).
    """
    req = body or KnowledgeMaintenanceRequest()
    try:
        return KnowledgeMaintenanceResponse(
            **knowledge_service.run_maintenance(
                purge_orphans=req.purge_orphans,
                dedupe_catalog=req.dedupe_catalog,
                repair_norms=req.repair_norms,
                compact_faiss=req.compact_faiss,
                index_pending=req.index_pending,
                dry_run=req.dry_run,
            )
        )
    except Exception as exc:
        logger.exception("Falha na manutenção knowledge")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/norm-packs", response_model=NormPackListResponse)
def list_norm_packs():
    """Pacotes normativos curados (catálogo legal — sem geração de texto por IA)."""
    return NormPackListResponse(**knowledge_service.list_norm_packs())


@router.get("/norm-packs/{pack_id}/analyze", response_model=NormPackAnalyzeResponse)
def analyze_norm_pack(pack_id: str):
    """Gap analysis: PDF licenciado presente? indexado no FAISS?"""
    try:
        return NormPackAnalyzeResponse(**knowledge_service.analyze_norm_pack(pack_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/norm-packs/{pack_id}/preview", response_model=NormPackPreviewResponse)
def preview_norm_pack_indexed(pack_id: str, nbr_code: str | None = None):
    """Preview dos trechos FAISS das NBRs já indexadas no pacote."""
    try:
        return NormPackPreviewResponse(
            **knowledge_service.preview_norm_pack(pack_id, nbr_code=nbr_code)
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/norm-packs/{pack_id}/gap.csv")
def export_norm_pack_gap_csv(pack_id: str):
    """Exporta gap analysis do pacote em CSV (Excel)."""
    try:
        filename, content = knowledge_service.export_norm_pack_gap_csv(pack_id)
        return Response(
            content=content.encode("utf-8"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/norm-packs/{pack_id}/index", response_model=NormPackIndexResponse)
def index_norm_pack(pack_id: str, body: NormPackIndexRequest | None = None):
    """Indexa em lote os PDFs licenciados do pacote na base NBR."""
    force = body.force if body else False
    try:
        return NormPackIndexResponse(**knowledge_service.index_norm_pack(pack_id, force=force))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Falha ao indexar pacote normativo %s", pack_id)
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
