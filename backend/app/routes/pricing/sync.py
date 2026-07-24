from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import Response, StreamingResponse

from core.concurrency import run_sync
from config.settings import KNOWLEDGE_DIR

from app.routes.pricing.schemas import (
    PriceBankActiveRequest,
    PriceSourceConfigRequest,
    PriceSourceCreateRequest,
    PriceSyncRequest,
    SeminfRefreshPricesRequest,
)
from app.routes.pricing.shared import (
    _raise_price_sync_http_error,
    _safe_upload_basename,
)

router = APIRouter()

@router.get("/sync/bank")
def price_sync_bank(reference: str | None = Query(default=None)):
    from pricing.sync.service import get_price_sync_service

    return get_price_sync_service().bank_stats(reference=reference)


@router.get("/sync/bank/references")
def price_sync_bank_references():
    from pricing.sync.service import get_price_sync_service

    return {"references": get_price_sync_service().list_references()}


@router.get("/sync/bank/inventory")
def price_sync_bank_inventory():
    """Totais globais e períodos importados agrupados por fonte (SINAPI, PPD/SEMINF, etc.)."""
    from pricing.sync.service import get_price_sync_service

    return get_price_sync_service().bank_inventory()


@router.post("/sync/bank/active")
def price_sync_bank_set_active(body: PriceBankActiveRequest):
    from pricing.sync.service import get_price_sync_service

    active = get_price_sync_service().set_active_reference(body.reference)
    return {"active_reference": active}


@router.delete("/sync/bank/references/{reference}")
def price_sync_bank_delete_reference(reference: str):
    from pricing.sync.service import get_price_sync_service

    try:
        return get_price_sync_service().delete_reference(reference)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/sync/bank/faiss/sinapi")
def price_sync_bank_purge_sinapi_faiss(reference: str | None = Query(default=None)):
    """Remove chunks legados SINAPI/TCPO do índice RAG cost_index (não afeta price_bank)."""
    from pricing.sync.service import get_price_sync_service

    return get_price_sync_service().purge_sinapi_faiss(reference=reference)


@router.get("/sync/bank/composition")
def price_sync_bank_composition_by_query(
    code: str = Query(..., min_length=1),
    uf: str = Query(default="SP", min_length=2, max_length=2),
    reference: str | None = Query(default=None),
    compare_previous: bool = Query(default=True),
):
    return _price_sync_bank_composition_response(
        code, uf=uf, reference=reference, compare_previous=compare_previous
    )


@router.get("/sync/bank/composition/export/pdf")
def price_sync_bank_composition_export_pdf_by_query(
    code: str = Query(..., min_length=1),
    uf: str = Query(default="SP", min_length=2, max_length=2),
    reference: str | None = Query(default=None),
    mode: str = Query(default="comd", pattern="^(comd|semd)$"),
):
    return _price_sync_bank_composition_export_pdf_response(
        code, uf=uf, reference=reference, mode=mode
    )


@router.get("/sync/bank/composition/{code:path}/export/pdf")
def price_sync_bank_composition_export_pdf(
    code: str,
    uf: str = Query(default="SP", min_length=2, max_length=2),
    reference: str | None = Query(default=None),
    mode: str = Query(default="comd", pattern="^(comd|semd)$"),
):
    return _price_sync_bank_composition_export_pdf_response(
        code, uf=uf, reference=reference, mode=mode
    )


@router.get("/sync/bank/composition/{code:path}")
def price_sync_bank_composition(
    code: str,
    uf: str = Query(default="SP", min_length=2, max_length=2),
    reference: str | None = Query(default=None),
    compare_previous: bool = Query(default=True),
):
    return _price_sync_bank_composition_response(
        code, uf=uf, reference=reference, compare_previous=compare_previous
    )


def _price_sync_bank_composition_response(
    code: str,
    *,
    uf: str,
    reference: str | None,
    compare_previous: bool,
) -> dict[str, Any]:
    from pricing.budget.composition_lookup import resolve_composition_detail
    from pricing.budget.price_bank_index import PriceBankIndex
    from pricing.budget.price_bank_period_variation import compute_period_variation_warnings

    ref = PriceBankIndex.resolve_reference(reference)
    comp = resolve_composition_detail(code, uf=uf.upper(), reference=ref)
    if not comp:
        raise HTTPException(status_code=404, detail=f"Composição aberta '{code}' não encontrada")
    resolved_ref = str(comp.get("resolved_reference") or ref or "")
    if compare_previous and resolved_ref:
        comp["period_variation"] = compute_period_variation_warnings(
            comp, uf=uf.upper(), reference=resolved_ref
        )
    return comp


def _price_sync_bank_composition_export_pdf_response(
    code: str,
    *,
    uf: str,
    reference: str | None,
    mode: str,
) -> Response:
    """Relatório PDF da CPU consultada (composição aberta)."""
    from pricing.budget.cpu_pdf_export import export_open_composition_pdf
    from pricing.budget.price_bank_index import PriceBankIndex
    from pricing.sync.service import get_price_sync_service

    ref = PriceBankIndex.resolve_reference(reference)
    comp = get_price_sync_service().get_open_composition(code, uf=uf.upper(), reference=ref)
    if not comp:
        raise HTTPException(status_code=404, detail=f"Composição aberta '{code}' não encontrada")
    ref_label = ref or str(comp.get("reference") or "")
    try:
        content = export_open_composition_pdf(comp, mode=mode, reference_label=ref_label)  # type: ignore[arg-type]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    safe_code = code.replace("/", "-").replace(" ", "_")[:40]
    filename = f"CPU_{safe_code}_{uf.upper()}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/sync/bank/open-compositions")
def price_sync_bank_list_open_compositions(
    reference: str | None = Query(default=None),
    uf: str = Query(default="SP", min_length=2, max_length=2),
    q: str | None = Query(default=None, max_length=200),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Lista CPUs abertas de um período (paginado, filtro opcional por código/descrição)."""
    from pricing.budget.open_composition_catalog import list_open_compositions

    return list_open_compositions(reference, uf=uf.upper(), q=q, offset=offset, limit=limit)


@router.get("/sync/bank/open-compositions/search")
def price_sync_bank_search_open_compositions(
    q: str = Query(..., min_length=1, max_length=200),
    reference: str | None = Query(default=None),
    uf: str = Query(default="SP", min_length=2, max_length=2),
    limit: int = Query(default=20, ge=1, le=50),
):
    """Busca CPUs por código ou descrição."""
    from pricing.budget.open_composition_catalog import search_open_compositions

    return search_open_compositions(q, reference=reference, uf=uf.upper(), limit=limit)


@router.post("/sync/{source}/upload")
async def price_sync_upload(
    source: str,
    file: UploadFile = File(...),
    uf: str = Query(default="SP", min_length=2, max_length=2),
    index_faiss: bool = Query(default=True),
    reload_providers: bool = Query(default=True),
    set_active: bool = Query(default=False),
):
    from config.settings import KNOWLEDGE_DIR
    from pricing.sync.connectors import is_known_source
    from pricing.sync.service import get_price_sync_service

    if not is_known_source(source):
        raise HTTPException(status_code=404, detail=f"Fonte '{source}' desconhecida")

    suffix = Path(file.filename or "upload.zip").suffix.lower()
    allowed = {".zip", ".xlsx", ".xls", ".csv"}
    if source.lower() in ("ppd_seminf", "dp_seminf"):
        allowed.add(".xlsm")
    if source.lower() == "orse":
        allowed.add(".orse")
    if suffix not in allowed:
        raise HTTPException(status_code=400, detail="Formato não suportado — use ZIP, XLSX, XLSM ou CSV")

    dest_dir = KNOWLEDGE_DIR / "sync" / "uploads" / source.lower()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / _safe_upload_basename(file.filename, f"upload{suffix}")
    content = await file.read()
    dest_path.write_bytes(content)

    if source.lower() in ("ppd_seminf", "dp_seminf"):
        from pricing.budget.seminf_bundle_detect import is_tabela_preco_file

        if is_tabela_preco_file(dest_path):
            raise HTTPException(
                status_code=400,
                detail=(
                    "DP/SEMINF: não envie só a Tabela de Preço. "
                    "Use Configurações → Bases de preços → Selecionar pasta "
                    "(Tabela_Preco + ComD + SemD)."
                ),
            )

    try:
        return await run_sync(
            get_price_sync_service().sync,
            source,
            local_file=dest_path,
            uf=uf,
            index_faiss=index_faiss,
            reload_providers=reload_providers,
            set_active=set_active,
        )
    except Exception as exc:
        _raise_price_sync_http_error(exc)

@router.get("/sync/status")
def price_sync_status():
    from pricing.sync.service import get_price_sync_service

    return get_price_sync_service().status()


@router.get("/sync/sources")
def price_sync_sources():
    from pricing.sync.service import get_price_sync_service

    return {"sources": get_price_sync_service().list_sources()}


@router.post("/sync/sources")
def price_sync_create_source(body: PriceSourceCreateRequest):
    from pricing.sync.service import get_price_sync_service

    try:
        profile = get_price_sync_service().create_custom_source(
            name=body.name,
            label=body.label,
            download_url=body.download_url,
        )
        return {"source": profile}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/sync/sources/{name}")
def price_sync_update_source(name: str, body: PriceSourceConfigRequest):
    from pricing.sync.service import get_price_sync_service

    try:
        profile = get_price_sync_service().update_source_config(
            name,
            download_url=body.download_url,
            label=body.label,
        )
        return {"source": profile}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/sync/sources/{name}")
def price_sync_delete_source(name: str):
    from pricing.sync.service import get_price_sync_service

    try:
        return get_price_sync_service().delete_custom_source(name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sync/{source}/stream")
async def price_sync_stream(source: str, body: PriceSyncRequest | None = None):
    from pricing.sync.connectors import is_known_source, list_all_source_names
    from pricing.sync.service import get_price_sync_service
    from pricing.sync.stream import sync_stream_events

    if not is_known_source(source):
        raise HTTPException(
            status_code=404,
            detail=f"Fonte '{source}' desconhecida. Disponíveis: {list_all_source_names()}",
        )
    body = body or PriceSyncRequest()
    options: dict[str, Any] = {
        "uf": body.uf,
        "year": body.year,
        "month": body.month,
        "index_faiss": body.index_faiss,
        "reload_providers": body.reload_providers,
        "set_active": body.set_active,
        "download_all_regions": body.download_all_regions,
        "skip_existing_ufs": body.skip_existing_ufs,
        "package_only": body.package_only,
        "portal_sync": body.portal_sync,
    }
    if body.local_file:
        options["local_file"] = Path(body.local_file)

    service = get_price_sync_service()

    def event_stream():
        try:
            for chunk in sync_stream_events(service, source, **options):
                yield chunk
        except Exception as exc:
            from core.stream_events import format_sse

            yield format_sse("error", {"error": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


@router.post("/sync/{source}/upload/stream")
async def price_sync_upload_stream(
    source: str,
    file: UploadFile = File(...),
    uf: str = Query(default="SP", min_length=2, max_length=2),
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    index_faiss: bool = Query(default=True),
    reload_providers: bool = Query(default=True),
    set_active: bool = Query(default=False),
):
    from config.settings import KNOWLEDGE_DIR
    from pricing.sync.connectors import is_known_source
    from pricing.sync.service import get_price_sync_service
    from pricing.sync.stream import sync_stream_events

    if not is_known_source(source):
        raise HTTPException(status_code=404, detail=f"Fonte '{source}' desconhecida")

    suffix = Path(file.filename or "upload.zip").suffix.lower()
    allowed = {".zip", ".xlsx", ".xls", ".csv"}
    if source.lower() in ("ppd_seminf", "dp_seminf"):
        allowed.add(".xlsm")
    if source.lower() == "orse":
        allowed.add(".orse")
    if suffix not in allowed:
        raise HTTPException(
            status_code=400,
            detail="Formato não suportado — use ZIP, XLSX, XLSM ou CSV",
        )

    dest_dir = KNOWLEDGE_DIR / "sync" / "uploads" / source.lower()
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_upload_basename(file.filename, f"upload{suffix}")
    dest_path = dest_dir / safe_name
    content = await file.read()
    dest_path.write_bytes(content)

    if source.lower() in ("ppd_seminf", "dp_seminf"):
        from pricing.budget.seminf_bundle_detect import is_tabela_preco_file

        if is_tabela_preco_file(dest_path):
            raise HTTPException(
                status_code=400,
                detail=(
                    "DP/SEMINF: não envie só a Tabela de Preço. "
                    "Use Configurações → Bases de preços → Selecionar pasta "
                    "(Tabela_Preco + ComD + SemD)."
                ),
            )

    service = get_price_sync_service()
    options: dict[str, Any] = {
        "local_file": dest_path,
        "uf": uf,
        "index_faiss": index_faiss,
        "reload_providers": reload_providers,
        "set_active": set_active,
    }
    if year is not None:
        options["year"] = year
    if month is not None:
        options["month"] = month

    def event_stream():
        try:
            for chunk in sync_stream_events(service, source, **options):
                yield chunk
        except Exception as exc:
            from core.stream_events import format_sse

            yield format_sse("error", {"error": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


@router.post("/sync/{source}/upload/bundle/stream")
async def price_sync_upload_bundle_stream(
    source: str,
    closed_file: UploadFile = File(..., description="Tabela_Preco — composições fechadas (.xlsm)"),
    open_comd_file: UploadFile = File(..., description="Composicao-Seminf ComD (.xlsx)"),
    open_semd_file: UploadFile = File(..., description="Composicao-Seminf SemD (.xlsx)"),
    uf: str = Query(default="AM", min_length=2, max_length=2),
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    index_faiss: bool = Query(default=True),
    reload_providers: bool = Query(default=True),
    set_active: bool = Query(default=False),
):
    """Importação DP/SEMINF em lote: Tabela de Preço + CPUs ComD + CPUs SemD."""
    from config.settings import KNOWLEDGE_DIR
    from pricing.sync.connectors import is_known_source
    from pricing.sync.service import get_price_sync_service
    from pricing.sync.stream import sync_stream_events

    src = source.lower()
    if src not in ("ppd_seminf", "dp_seminf"):
        raise HTTPException(
            status_code=400,
            detail="Upload em lote disponível apenas para ppd_seminf e dp_seminf",
        )
    if not is_known_source(src):
        raise HTTPException(status_code=404, detail=f"Fonte '{source}' desconhecida")

    dest_dir = KNOWLEDGE_DIR / "sync" / "uploads" / src
    dest_dir.mkdir(parents=True, exist_ok=True)

    async def _save(upload: UploadFile, role: str) -> Path:
        fallback = f"{role}.xlsx"
        safe_name = _safe_upload_basename(upload.filename, fallback)
        suffix = Path(safe_name).suffix.lower()
        allowed = {".xlsm", ".xlsx", ".xls"}
        if suffix not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Formato não suportado em {role}: use XLSM/XLSX",
            )
        dest = dest_dir / f"{role}_{safe_name}"
        dest.write_bytes(await upload.read())
        return dest

    try:
        closed_path = await _save(closed_file, "closed")
        comd_path = await _save(open_comd_file, "open_comd")
        semd_path = await _save(open_semd_file, "open_semd")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Falha ao salvar planilhas: {exc}") from exc

    service = get_price_sync_service()
    options: dict[str, Any] = {
        "local_file": closed_path,
        "open_comd_file": comd_path,
        "open_semd_file": semd_path,
        "uf": uf,
        "index_faiss": index_faiss,
        "reload_providers": reload_providers,
        "set_active": set_active,
    }
    if year is not None:
        options["year"] = year
    if month is not None:
        options["month"] = month

    def event_stream():
        try:
            for chunk in sync_stream_events(service, src, **options):
                yield chunk
        except Exception as exc:
            from core.stream_events import format_sse

            yield format_sse("error", {"error": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


@router.post("/sync/orse/upload/bundle/stream")
async def price_sync_orse_upload_bundle_stream(
    composicoes_file: UploadFile = File(..., description="Export ORSE — Composições/Serviços (.xlsx)"),
    insumos_file: UploadFile | None = File(default=None, description="Export ORSE — Insumos (.xlsx)"),
    analitico_file: UploadFile | None = File(default=None, description="Export ORSE — Analítico (.xlsx)"),
    uf: str = Query(default="SE", min_length=2, max_length=2),
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    index_faiss: bool = Query(default=True),
    reload_providers: bool = Query(default=True),
    set_active: bool = Query(default=False),
):
    """Importação ORSE: composições fechadas + insumos (+ analítico opcional)."""
    from config.settings import KNOWLEDGE_DIR
    from pricing.sync.service import get_price_sync_service
    from pricing.sync.stream import sync_stream_events

    dest_dir = KNOWLEDGE_DIR / "sync" / "uploads" / "orse"
    dest_dir.mkdir(parents=True, exist_ok=True)

    async def _save(upload: UploadFile, role: str) -> Path:
        fallback = f"{role}.xlsx"
        safe_name = _safe_upload_basename(upload.filename, fallback)
        suffix = Path(safe_name).suffix.lower()
        if suffix not in {".xlsx", ".xls", ".csv"}:
            raise HTTPException(status_code=400, detail=f"Formato inválido em {role}")
        dest = dest_dir / f"{role}_{safe_name}"
        dest.write_bytes(await upload.read())
        return dest

    try:
        comp_path = await _save(composicoes_file, "composicoes")
        ins_path = await _save(insumos_file, "insumos") if insumos_file and insumos_file.filename else None
        ana_path = await _save(analitico_file, "analitico") if analitico_file and analitico_file.filename else None
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Falha ao salvar planilhas ORSE: {exc}") from exc

    service = get_price_sync_service()
    options: dict[str, Any] = {
        "composicoes_file": comp_path,
        "insumos_file": ins_path,
        "analitico_file": ana_path,
        "uf": uf,
        "index_faiss": index_faiss,
        "reload_providers": reload_providers,
        "set_active": set_active,
    }
    if year is not None:
        options["year"] = year
    if month is not None:
        options["month"] = month

    def event_stream():
        try:
            for chunk in sync_stream_events(service, "orse", **options):
                yield chunk
        except Exception as exc:
            from core.stream_events import format_sse

            yield format_sse("error", {"error": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


@router.post("/sync/{source}/refresh-prices")
def price_sync_refresh_seminf_prices(source: str, body: SeminfRefreshPricesRequest):
    """Gera base SEMINF do mês SINAPI (ex. BR-DP-SEMINF-2026-05); base fonte preservada."""
    src = source.lower()
    if src not in ("ppd_seminf", "dp_seminf"):
        raise HTTPException(
            status_code=400,
            detail="Atualização de preços disponível apenas para ppd_seminf e dp_seminf",
        )
    from pricing.budget.seminf_open_refresh import apply_seminf_open_refresh

    try:
        result = apply_seminf_open_refresh(
            body.reference,
            sinapi_reference=body.sinapi_reference,
            uf=body.uf.upper(),
            set_active=body.set_active,
        )
        return {
            "status": "ok",
            "reference": result.reference,
            "parent_reference": result.parent_reference,
            "sinapi_reference": result.sinapi_reference,
            "uf": result.uf,
            "compositions_updated": result.compositions_updated,
            "items_updated": result.items_updated,
            "items_missing_price": result.items_missing_price,
            "warnings": result.warnings,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sync/{source}")
async def price_sync_source(source: str, body: PriceSyncRequest | None = None):
    from pricing.sync.connectors import is_known_source, list_all_source_names
    from pricing.sync.service import get_price_sync_service

    if not is_known_source(source):
        raise HTTPException(
            status_code=404,
            detail=f"Fonte '{source}' desconhecida. Disponíveis: {list_all_source_names()}",
        )
    body = body or PriceSyncRequest()
    options: dict[str, Any] = {
        "uf": body.uf,
        "year": body.year,
        "month": body.month,
        "index_faiss": body.index_faiss,
        "reload_providers": body.reload_providers,
        "set_active": body.set_active,
        "download_all_regions": body.download_all_regions,
        "skip_existing_ufs": body.skip_existing_ufs,
        "package_only": body.package_only,
        "portal_sync": body.portal_sync,
    }
    if body.local_file:
        options["local_file"] = Path(body.local_file)

    try:
        return await run_sync(get_price_sync_service().sync, source, **options)
    except Exception as exc:
        _raise_price_sync_http_error(exc)


@router.post("/sync")
async def price_sync_all(skip_manual: bool = Query(default=True)):
    from pricing.sync.service import get_price_sync_service

    return await run_sync(
        get_price_sync_service().sync_all,
        skip_manual=skip_manual,
    )
