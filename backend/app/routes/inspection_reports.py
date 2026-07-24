"""API REST — Laudos de Vistoria."""

from __future__ import annotations

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

router = APIRouter(prefix="/inspection-reports", tags=["Inspection Reports"])


class CreateReportBody(BaseModel):
    title: str = "Laudo de vistoria"
    template_id: Optional[str] = None
    user_prompt: str = ""
    knowledge_mode: str = Field(
        default="attachments_and_kb",
        description="attachments | attachments_and_kb",
    )
    project_id: Optional[str] = None


class UpdateReportBody(BaseModel):
    title: Optional[str] = None
    template_id: Optional[str] = None
    user_prompt: Optional[str] = None
    knowledge_mode: Optional[str] = None
    project_id: Optional[str] = None
    responsaveis_tecnicos: Optional[list[dict[str, Any]]] = None
    responsaveis_imagens: Optional[list[dict[str, Any]]] = None
    solicitante: Optional[dict[str, Any]] = None
    chapters: Optional[list[dict[str, Any]]] = None
    photographic_report: Optional[list[dict[str, Any]]] = None
    content_patch: Optional[dict[str, Any]] = None


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
    return {
        "gemini_available": gemini_available(),
        "gemini_model": resolve_gemini_model(),
        "max_asset_mb": svc.MAX_ASSET_BYTES // (1024 * 1024),
        "max_images": svc.MAX_IMAGES_PER_REPORT,
        "max_docs": svc.MAX_DOCS_PER_REPORT,
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
    return {
        "items": svc.list_reports(
            db,
            user_id=_list_user_id(user),
            project_id=_uid(project_id),
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
    )


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
                "photo_number": a.photo_number,
                "filename": a.filename,
                "path": str(path),
                "orientation": a.orientation,
                "caption": a.caption,
            }
        )
    return assets


def _georef_asset_for_export(db: Session, report) -> dict | None:
    from core.inspection_report.geo_utils import decode_gps_payload

    for a in report.assets or []:
        if a.kind != "georef":
            continue
        path = svc.asset_path(report.id, a)
        gps = decode_gps_payload(a.extracted_text) or {}
        geo = (report.content or {}).get("georreferencia") or {}
        return {
            "asset_id": str(a.id),
            "filename": a.filename,
            "path": str(path),
            "caption": a.caption
            or geo.get("label")
            or "Imagem georreferenciada do objeto",
            "latitude": gps.get("latitude", geo.get("latitude")),
            "longitude": gps.get("longitude", geo.get("longitude")),
            "label": gps.get("label") or geo.get("label"),
        }
    return None


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
    checklist = build_export_checklist(report.content, assets=report.assets)
    if strict and checklist.get("blocking"):
        raise HTTPException(
            422,
            detail={"message": "Checklist oficial incompleto", "checklist": checklist},
        )
    data = build_inspection_laudo_docx(
        content=report.content,
        image_assets=_image_assets_for_export(db, report),
        georef_asset=_georef_asset_for_export(db, report),
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
    checklist = build_export_checklist(report.content, assets=report.assets)
    if strict and checklist.get("blocking"):
        raise HTTPException(
            422,
            detail={"message": "Checklist oficial incompleto", "checklist": checklist},
        )
    data = build_inspection_laudo_pdf(
        content=report.content,
        image_assets=_image_assets_for_export(db, report),
        georef_asset=_georef_asset_for_export(db, report),
    )
    svc._record_laudo_activity(
        report=report,
        event_type="exported",
        title=f"Export PDF: {report.title}",
        summary="PDF",
    )
    filename = f"laudo_{(report.title or 'vistoria')[:40].replace(' ', '_')}.pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
