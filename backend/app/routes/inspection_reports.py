"""API REST — Laudos de Vistoria."""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.auth.dependencies import get_current_user
from core.database.connection import get_db
from core.database.models import User
from core.inspection_report import service as svc
from core.inspection_report.access import report_user_id, require_report_access, user_is_admin
from core.inspection_report.docx_export import build_inspection_laudo_docx
from core.inspection_report.pdf_export import build_inspection_laudo_pdf
from core.inspection_report.gemini_client import gemini_available, resolve_gemini_model
from core.inspection_report.validation import build_export_checklist

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/inspection-reports", tags=["Inspection Reports"])


class CreateReportBody(BaseModel):
    title: str = "Laudo de vistoria"
    template_id: Optional[str] = None
    user_prompt: str = ""
    knowledge_mode: str = Field(
        default="attachments_and_kb",
        description="attachments | attachments_and_kb",
    )
    suggest_instrumented_tests: bool = False
    project_id: Optional[str] = None


class UpdateReportBody(BaseModel):
    title: Optional[str] = None
    template_id: Optional[str] = None
    user_prompt: Optional[str] = None
    knowledge_mode: Optional[str] = None
    suggest_instrumented_tests: Optional[bool] = None
    project_id: Optional[str] = None
    responsaveis_tecnicos: Optional[list[dict[str, Any]]] = None
    responsaveis_imagens: Optional[list[dict[str, Any]]] = None
    solicitante: Optional[dict[str, Any]] = None
    chapters: Optional[list[dict[str, Any]]] = None
    photographic_report: Optional[list[dict[str, Any]]] = None
    content_patch: Optional[dict[str, Any]] = None


class AssayResultsBody(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)


class VisualMemoryBody(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)


class SignatureEvidenceBody(BaseModel):
    rt_signature_asset_ids: Optional[dict[str, str]] = None
    notes: Optional[str] = None


class CorrectBody(BaseModel):
    correction_prompt: str


class AssetCaptionBody(BaseModel):
    caption: Optional[str] = None


class TemplateBody(BaseModel):
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None
    discipline_hint: str = "GERAL"
    chapters: Optional[list[dict[str, Any]]] = None
    system_prompt: Optional[str] = None
    active: bool = True


def _uid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    return uuid.UUID(str(value))


def _list_user_id(user: User | None) -> uuid.UUID | None:
    if user_is_admin(user):
        return None
    return report_user_id(user)


@router.get("/status")
def module_status():
    from core.inspection_report.pades_sign import pades_status

    return {
        "gemini_available": gemini_available(),
        "gemini_model": resolve_gemini_model(),
        "max_asset_mb": svc.MAX_ASSET_BYTES // (1024 * 1024),
        "max_images": svc.MAX_IMAGES_PER_REPORT,
        "max_docs": svc.MAX_DOCS_PER_REPORT,
        "pades": pades_status(),
    }


@router.get("/templates")
def get_templates(db: Session = Depends(get_db)):
    return {"items": svc.list_templates(db)}


@router.post("/templates")
def post_template(body: TemplateBody, db: Session = Depends(get_db)):
    return svc.create_template(db, body.model_dump())


@router.patch("/templates/{template_id}")
def patch_template(template_id: str, body: TemplateBody, db: Session = Depends(get_db)):
    updated = svc.update_template(db, uuid.UUID(template_id), body.model_dump())
    if not updated:
        raise HTTPException(404, "Template não encontrado")
    return updated


@router.get("")
def list_reports(
    project_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    # Órfãos só entram na listagem do admin
    include_orphans = user_is_admin(user)
    return {
        "items": svc.list_reports(
            db,
            user_id=_list_user_id(user),
            project_id=_uid(project_id),
            include_orphans=include_orphans,
        )
    }


@router.post("")
def create_report(
    body: CreateReportBody,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    return svc.create_report(
        db,
        title=body.title,
        template_id=_uid(body.template_id),
        user_prompt=body.user_prompt,
        knowledge_mode=body.knowledge_mode,
        user_id=report_user_id(user),
        project_id=_uid(body.project_id),
        suggest_instrumented_tests=bool(body.suggest_instrumented_tests),
    )


class ArtLookupBody(BaseModel):
    crea: Optional[str] = None
    art: Optional[str] = None
    art_protocolo: Optional[str] = None
    uf: Optional[str] = None
    probe: bool = True


class AssignOwnerBody(BaseModel):
    user_id: Optional[str] = None


class BackfillOrphansBody(BaseModel):
    user_id: Optional[str] = None


@router.post("/art/lookup")
def art_lookup(
    body: ArtLookupBody,
    user: User | None = Depends(get_current_user),
):
    """Consulta live ART/CREA + link SICAR público (preenche art_url)."""
    from config.settings import get_settings
    from core.inspection_report.art_lookup import lookup_art

    _ = user  # exige auth via middleware
    settings = get_settings()
    probe = bool(body.probe and getattr(settings, "laudo_art_lookup_live", True))
    return lookup_art(
        crea=body.crea,
        art=body.art,
        art_protocolo=body.art_protocolo,
        uf=body.uf,
        probe=probe,
    )


@router.get("/orphans")
def list_orphans(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    from core.inspection_report.access import require_admin

    require_admin(user)
    return {"items": svc.list_orphan_reports(db)}


@router.post("/orphans/backfill")
def backfill_orphans(
    body: BackfillOrphansBody,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    from core.inspection_report.access import require_admin

    admin = require_admin(user)
    owner = _uid(body.user_id) or admin.id
    return svc.backfill_orphan_reports(db, owner)


@router.post("/{report_id}/assign")
def assign_report(
    report_id: str,
    body: AssignOwnerBody,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """Admin atribui dono a laudo (inclui órfãos)."""
    from core.inspection_report.access import require_admin

    admin = require_admin(user)
    owner = _uid(body.user_id) or admin.id
    updated = svc.assign_report_owner(db, uuid.UUID(report_id), owner)
    if not updated:
        raise HTTPException(404, "Laudo não encontrado")
    return updated


@router.post("/{report_id}/claim")
def claim_report(
    report_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """Admin assume laudo órfão (atribui a si)."""
    from core.inspection_report.access import require_admin

    admin = require_admin(user)
    report = svc.get_report(db, uuid.UUID(report_id))
    if not report:
        raise HTTPException(404, "Laudo não encontrado")
    if report.user_id is not None and report.user_id != admin.id:
        raise HTTPException(409, "Laudo já possui dono — use /assign")
    updated = svc.assign_report_owner(db, uuid.UUID(report_id), admin.id)
    return updated


@router.get("/{report_id}")
def get_report(
    report_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    report = require_report_access(db, uuid.UUID(report_id), user)
    return svc.serialize_report(report)


@router.patch("/{report_id}")
def patch_report(
    report_id: str,
    body: UpdateReportBody,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    require_report_access(db, uuid.UUID(report_id), user)
    data = body.model_dump(exclude_unset=True)
    updated = svc.update_report_meta(db, uuid.UUID(report_id), data)
    if not updated:
        raise HTTPException(404, "Laudo não encontrado")
    return updated


@router.post("/{report_id}/assets")
async def upload_asset(
    report_id: str,
    file: UploadFile = File(...),
    kind: Optional[str] = Form(None),
    caption: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    require_report_access(db, uuid.UUID(report_id), user)
    content = await file.read()
    if not content:
        raise HTTPException(400, "Arquivo vazio")
    try:
        return svc.add_asset(
            db,
            uuid.UUID(report_id),
            filename=file.filename or "arquivo.bin",
            content=content,
            mime_type=file.content_type,
            caption=caption,
            kind_hint=kind,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if "não encontrado" in detail.lower() else 400
        raise HTTPException(code, detail) from exc
    except RuntimeError as exc:
        raise HTTPException(500, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"Falha no upload: {exc}") from exc


@router.patch("/{report_id}/assets/{asset_id}")
def patch_asset_caption(
    report_id: str,
    asset_id: str,
    body: AssetCaptionBody,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    require_report_access(db, uuid.UUID(report_id), user)
    updated = svc.update_asset_caption(
        db, uuid.UUID(report_id), uuid.UUID(asset_id), body.caption
    )
    if not updated:
        raise HTTPException(404, "Anexo não encontrado")
    return updated


@router.delete("/{report_id}")
def delete_report(
    report_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    require_report_access(db, uuid.UUID(report_id), user)
    ok = svc.delete_report(db, uuid.UUID(report_id))
    if not ok:
        raise HTTPException(404, "Laudo não encontrado")
    return {"ok": True}


@router.delete("/{report_id}/assets/{asset_id}")
def remove_asset(
    report_id: str,
    asset_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    require_report_access(db, uuid.UUID(report_id), user)
    ok = svc.delete_asset(db, uuid.UUID(report_id), uuid.UUID(asset_id))
    if not ok:
        raise HTTPException(404, "Anexo não encontrado")
    return {"ok": True}


@router.get("/{report_id}/assets/{asset_id}/file")
def download_asset(
    report_id: str,
    asset_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """Serve arquivo do anexo (preview inline de imagens georref./fotos)."""
    report = require_report_access(db, uuid.UUID(report_id), user)
    asset = next((a for a in (report.assets or []) if str(a.id) == asset_id), None)
    if not asset:
        raise HTTPException(404, "Anexo não encontrado")
    path = svc.asset_path(report.id, asset)
    if not path.exists():
        raise HTTPException(404, "Arquivo não encontrado no disco")
    data = path.read_bytes()
    media = asset.mime_type or "application/octet-stream"
    if asset.kind in ("image", "georef") and not media.startswith("image/"):
        suffix = path.suffix.lower()
        media = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".tif": "image/tiff",
            ".tiff": "image/tiff",
            ".bmp": "image/bmp",
        }.get(suffix, "image/jpeg")
    return Response(
        content=data,
        media_type=media,
        headers={
            "Cache-Control": "private, max-age=3600",
            "Content-Disposition": f'inline; filename="{asset.filename}"',
        },
    )


@router.post("/{report_id}/generate")
def generate(
    report_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    require_report_access(db, uuid.UUID(report_id), user)
    try:
        return svc.generate_report(db, uuid.UUID(report_id))
    except svc.GenerationCancelled as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"Falha na geração: {exc}") from exc


@router.post("/{report_id}/generate/stream")
def generate_stream(
    report_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """SSE com progresso em tempo real da geração do laudo."""
    require_report_access(db, uuid.UUID(report_id), user)
    return StreamingResponse(
        svc.iter_generate_report_events(uuid.UUID(report_id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Encoding": "identity",
        },
    )


@router.post("/{report_id}/generate/cancel")
def cancel_generate(
    report_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    require_report_access(db, uuid.UUID(report_id), user)
    svc.request_cancel_generation(uuid.UUID(report_id))
    return {"ok": True, "message": "Cancelamento solicitado"}


@router.get("/{report_id}/assay-results")
def get_assay_results(
    report_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """L16 — lista resultados medidos e ensaios sugeridos para pré-preenchimento."""
    from core.inspection_report.assay_results import build_assay_results_view

    report = require_report_access(db, uuid.UUID(report_id), user)
    return build_assay_results_view(report)


@router.put("/{report_id}/assay-results")
def put_assay_results(
    report_id: str,
    body: AssayResultsBody,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """L16 — salva resultados medidos de ensaios instrumentados."""
    require_report_access(db, uuid.UUID(report_id), user)
    try:
        return svc.save_assay_results(db, uuid.UUID(report_id), body.items)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{report_id}/visual-memory")
def get_visual_memory(
    report_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """L17 — croquis/overlays cotados por foto."""
    from core.inspection_report.visual_memory import build_visual_memory_view

    report = require_report_access(db, uuid.UUID(report_id), user)
    return build_visual_memory_view(report)


@router.put("/{report_id}/visual-memory")
def put_visual_memory(
    report_id: str,
    body: VisualMemoryBody,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    require_report_access(db, uuid.UUID(report_id), user)
    try:
        return svc.save_visual_memory(db, uuid.UUID(report_id), body.items)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{report_id}/signature-evidence")
def get_signature_evidence(
    report_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """L19 — evidência de assinatura (imagem + hash PDF)."""
    from core.inspection_report.signature_evidence import get_signature_evidence as get_ev

    report = require_report_access(db, uuid.UUID(report_id), user)
    return get_ev(report.content)


@router.put("/{report_id}/signature-evidence")
def put_signature_evidence(
    report_id: str,
    body: SignatureEvidenceBody,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    require_report_access(db, uuid.UUID(report_id), user)
    try:
        return svc.save_signature_evidence(
            db,
            uuid.UUID(report_id),
            body.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{report_id}/correct")
def correct(
    report_id: str,
    body: CorrectBody,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    require_report_access(db, uuid.UUID(report_id), user)
    if not (body.correction_prompt or "").strip():
        raise HTTPException(400, "Informe as correções solicitadas")
    try:
        return svc.correct_report(db, uuid.UUID(report_id), body.correction_prompt.strip())
    except svc.GenerationCancelled as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"Falha na correção: {exc}") from exc


@router.post("/{report_id}/correct/stream")
def correct_stream(
    report_id: str,
    body: CorrectBody,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """SSE da correção profissional (L2)."""
    require_report_access(db, uuid.UUID(report_id), user)
    if not (body.correction_prompt or "").strip():
        raise HTTPException(400, "Informe as correções solicitadas")
    return StreamingResponse(
        svc.iter_correct_report_events(uuid.UUID(report_id), body.correction_prompt.strip()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Encoding": "identity",
        },
    )


def _image_assets_for_export(db: Session, report) -> list[dict]:
    assets = []
    for a in report.assets or []:
        if a.kind != "image":
            continue
        path = svc.asset_path(report.id, a)
        assets.append(
            {
                "asset_id": str(a.id),
                "photo_number": a.photo_number,
                "filename": a.filename,
                "path": str(path),
                "orientation": a.orientation,
                "caption": a.caption,
            }
        )
    return assets


def _signature_paths_by_party(report) -> dict[str, str]:
    """Mapa party_id -> path da imagem de firma (L19)."""
    from core.inspection_report.signature_evidence import get_signature_evidence

    ev = get_signature_evidence(report.content)
    id_map = dict(ev.get("rt_signature_asset_ids") or {})
    # também lê do party
    for rt in (report.content or {}).get("responsaveis_tecnicos") or []:
        if isinstance(rt, dict) and rt.get("id") and rt.get("signature_asset_id"):
            id_map[str(rt["id"])] = str(rt["signature_asset_id"])
    by_asset = {str(a.id): a for a in (report.assets or []) if a.kind == "signature"}
    out: dict[str, str] = {}
    for party_id, asset_id in id_map.items():
        asset = by_asset.get(str(asset_id))
        if not asset:
            continue
        path = svc.asset_path(report.id, asset)
        if path.exists():
            out[str(party_id)] = str(path)
    return out


def _georef_asset_for_export(db: Session, report) -> dict | None:
    """Asset de capa/georref + coordenadas para foto e mapa satélite no export."""
    from core.inspection_report.geo_utils import decode_gps_payload, extract_gps_from_image

    geo = (report.content or {}).get("georreferencia") or {}
    map_cache = str(svc.report_dir(report.id) / "location_map_v3.png")
    result: dict | None = None

    for a in report.assets or []:
        if a.kind != "georef":
            continue
        path = svc.asset_path(report.id, a)
        gps = decode_gps_payload(a.extracted_text) or {}
        result = {
            "asset_id": str(a.id),
            "filename": a.filename,
            "path": str(path),
            "caption": a.caption
            or geo.get("label")
            or "Imagem georreferenciada do objeto",
            "latitude": gps.get("latitude", geo.get("latitude")),
            "longitude": gps.get("longitude", geo.get("longitude")),
            "label": gps.get("label") or geo.get("label"),
            "map_cache_path": map_cache,
        }
        break

    # Fallback: coordenadas só no content, ou EXIF de outra foto do laudo
    lat = (result or {}).get("latitude") if result else geo.get("latitude")
    lon = (result or {}).get("longitude") if result else geo.get("longitude")
    label = (result or {}).get("label") if result else geo.get("label")

    if lat is None or lon is None:
        for a in report.assets or []:
            if a.kind not in {"georef", "image"}:
                continue
            path = svc.asset_path(report.id, a)
            if not path.exists():
                continue
            gps = decode_gps_payload(a.extracted_text) or extract_gps_from_image(path) or {}
            if gps.get("latitude") is None or gps.get("longitude") is None:
                continue
            lat, lon = gps["latitude"], gps["longitude"]
            label = label or gps.get("label")
            if result is None:
                result = {
                    "asset_id": str(a.id),
                    "filename": a.filename,
                    "path": str(path),
                    "caption": a.caption or "Imagem georreferenciada do objeto",
                    "latitude": lat,
                    "longitude": lon,
                    "label": label,
                    "map_cache_path": map_cache,
                }
            break

    if result is None and lat is not None and lon is not None:
        result = {
            "path": None,
            "caption": "Localização do objeto",
            "latitude": lat,
            "longitude": lon,
            "label": label,
            "map_cache_path": map_cache,
        }
    elif result is not None:
        result["latitude"] = lat if lat is not None else result.get("latitude")
        result["longitude"] = lon if lon is not None else result.get("longitude")
        result["label"] = label or result.get("label")
        result["map_cache_path"] = map_cache

    return result


@router.get("/{report_id}/export/checklist")
def export_checklist(
    report_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """L9 — checklist pré-export oficial."""
    report = require_report_access(db, uuid.UUID(report_id), user)
    return build_export_checklist(report.content, assets=report.assets)


@router.get("/{report_id}/export/docx")
def export_docx(
    report_id: str,
    strict: bool = Query(False, description="Bloqueia se checklist oficial falhar"),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    report = require_report_access(db, uuid.UUID(report_id), user)
    if not report.content:
        raise HTTPException(404, "Laudo gerado não encontrado")
    export_content = svc.prepare_report_content(report, persist=True, db=db)
    checklist = build_export_checklist(export_content, assets=report.assets)
    if strict and checklist.get("blocking"):
        raise HTTPException(
            422,
            detail={"message": "Checklist oficial incompleto", "checklist": checklist},
        )
    data = build_inspection_laudo_docx(
        content=export_content,
        image_assets=_image_assets_for_export(db, report),
        georef_asset=_georef_asset_for_export(db, report),
        signature_paths=_signature_paths_by_party(report),
    )
    svc._record_laudo_activity(
        report=report,
        event_type="exported",
        title=f"Export Word: {report.title}",
        summary="DOCX",
    )
    filename = f"laudo_{(report.title or 'vistoria')[:40].replace(' ', '_')}.docx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{report_id}/export/pdf")
def export_pdf(
    report_id: str,
    strict: bool = Query(False, description="Bloqueia se checklist oficial falhar"),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    report = require_report_access(db, uuid.UUID(report_id), user)
    if not report.content:
        raise HTTPException(404, "Laudo gerado não encontrado")
    export_content = svc.prepare_report_content(report, persist=True, db=db)
    checklist = build_export_checklist(export_content, assets=report.assets)
    if strict and checklist.get("blocking"):
        raise HTTPException(
            422,
            detail={"message": "Checklist oficial incompleto", "checklist": checklist},
        )
    try:
        data = build_inspection_laudo_pdf(
            content=export_content,
            image_assets=_image_assets_for_export(db, report),
            georef_asset=_georef_asset_for_export(db, report),
            signature_paths=_signature_paths_by_party(report),
        )
    except Exception as exc:
        logger.exception("Falha ao gerar PDF do laudo %s", report_id)
        raise HTTPException(
            500,
            detail=f"Falha ao gerar PDF: {exc}",
        ) from exc

    pades_meta: dict[str, Any] | None = None
    method = "image_hash"
    try:
        from core.inspection_report.pades_sign import pades_status, sign_pdf_pades

        if pades_status().get("ready"):
            data, pades_meta = sign_pdf_pades(data)
            method = "pades"
    except Exception as exc:
        logger.warning("PAdES não aplicado no laudo %s: %s", report_id, exc)

    digest = hashlib.sha256(data).hexdigest()
    try:
        digest = svc.record_export_pdf_hash(
            db, report, data, method=method, pades_meta=pades_meta
        )
        svc._record_laudo_activity(
            report=report,
            event_type="exported",
            title=f"Export PDF: {report.title}",
            summary=f"PDF · {method} · SHA-256 {digest[:16]}…",
        )
    except Exception:
        logger.exception(
            "PDF gerado mas falhou ao gravar hash/atividade do laudo %s",
            report_id,
        )
        try:
            db.rollback()
        except Exception:
            pass

    filename = f"laudo_{(report.title or 'vistoria')[:40].replace(' ', '_')}.pdf"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Laudo-PDF-SHA256": digest,
        "X-Laudo-PDF-Sign-Method": method,
    }
    return Response(
        content=data,
        media_type="application/pdf",
        headers=headers,
    )
