"""Serviço de domínio — CRUD, geração e correção de laudos."""

from __future__ import annotations

import logging
import re
import threading
import uuid
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session, joinedload

from config.settings import DATA_DIR
from core.inspection_report.constants import DEFAULT_CHAPTERS, SYSTEM_PROMPT_BASE
from core.inspection_report.gemini_client import generate_laudo_content, gemini_available
from core.inspection_report.models import (
    InspectionReport,
    InspectionReportAsset,
    InspectionReportTemplate,
)
from core.inspection_report.typology import chapters_for_slug, system_prompt_for_slug
from core.system.company_profile import get_company_profile

logger = logging.getLogger(__name__)

STORAGE_ROOT = DATA_DIR / "inspection_reports"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
DOC_EXTS = {".pdf", ".txt", ".md", ".docx"}

# L6 — limites de upload
MAX_ASSET_BYTES = 25 * 1024 * 1024  # 25 MB por arquivo
MAX_IMAGES_PER_REPORT = 80
MAX_DOCS_PER_REPORT = 20

# Cancelamento de geração (L6)
_cancel_lock = threading.Lock()
_cancelled_generations: set[str] = set()


def request_cancel_generation(report_id: uuid.UUID | str) -> None:
    with _cancel_lock:
        _cancelled_generations.add(str(report_id))


def clear_cancel_generation(report_id: uuid.UUID | str) -> None:
    with _cancel_lock:
        _cancelled_generations.discard(str(report_id))


def is_generation_cancelled(report_id: uuid.UUID | str) -> bool:
    with _cancel_lock:
        return str(report_id) in _cancelled_generations


class GenerationCancelled(Exception):
    """Geração/correção abortada pelo usuário."""


def _check_cancelled(report_id: uuid.UUID) -> None:
    if is_generation_cancelled(report_id):
        raise GenerationCancelled("Geração cancelada pelo usuário")


def _summarize_content_for_correction(content: dict[str, Any], *, max_chars: int = 6000) -> str:
    """L2 — resumo compacto do laudo para o prompt de correção (evita dump 20k)."""
    parts: list[str] = []
    for key in ("titulo", "objeto", "local", "data_vistoria", "numero_laudo"):
        if content.get(key):
            parts.append(f"{key}: {content[key]}")
    for ch in (content.get("chapters") or [])[:12]:
        if not isinstance(ch, dict):
            continue
        title = ch.get("title") or ch.get("id") or "capítulo"
        paras = ch.get("paragraphs") or []
        snippet = " ".join(str(p) for p in paras[:2])[:400]
        parts.append(f"[cap {title}] {snippet}")
    for p in (content.get("pathologies") or [])[:15]:
        if not isinstance(p, dict):
            continue
        parts.append(
            f"[pat {p.get('code') or ''}] {p.get('name')} | {p.get('severity')} | {str(p.get('description') or '')[:180]}"
        )
    for ph in (content.get("photographic_report") or [])[:20]:
        if not isinstance(ph, dict):
            continue
        parts.append(
            f"[foto {ph.get('photo_number')}] {ph.get('title')} | {str(ph.get('legend') or '')[:120]}"
        )
    text = "\n".join(parts)
    return text[:max_chars]


def _record_laudo_activity(
    *,
    report: InspectionReport,
    event_type: str,
    title: str,
    summary: str | None = None,
) -> None:
    """L8 — timeline do projeto quando houver project_id."""
    if not report.project_id:
        return
    try:
        from core.project_memory.service import record_activity

        record_activity(
            source="inspection_report",
            event_type=event_type,
            title=title,
            summary=summary,
            project_id=report.project_id,
            meta={"report_id": str(report.id), "status": report.status},
        )
    except Exception as exc:
        logger.warning("Activity laudo falhou: %s", exc)


def report_dir(report_id: uuid.UUID | str) -> Path:
    path = STORAGE_ROOT / str(report_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def serialize_template(t: InspectionReportTemplate) -> dict[str, Any]:
    return {
        "id": str(t.id),
        "slug": t.slug,
        "name": t.name,
        "description": t.description,
        "discipline_hint": t.discipline_hint,
        "chapters": t.chapters or list(DEFAULT_CHAPTERS),
        "system_prompt": t.system_prompt,
        "active": t.active,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def serialize_asset(a: InspectionReportAsset) -> dict[str, Any]:
    from core.inspection_report.geo_utils import decode_gps_payload

    gps = decode_gps_payload(a.extracted_text) if a.kind == "georef" else None
    return {
        "id": str(a.id),
        "report_id": str(a.report_id),
        "kind": a.kind,
        "filename": a.filename,
        "stored_name": a.stored_name,
        "mime_type": a.mime_type,
        "caption": a.caption,
        "photo_number": a.photo_number,
        "sort_order": a.sort_order,
        "width": a.width,
        "height": a.height,
        "orientation": a.orientation,
        "has_text": bool(a.extracted_text),
        "gps": gps,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def serialize_report(r: InspectionReport, *, include_content: bool = True) -> dict[str, Any]:
    data = {
        "id": str(r.id),
        "title": r.title,
        "template_id": str(r.template_id) if r.template_id else None,
        "template": serialize_template(r.template) if r.template else None,
        "status": r.status,
        "knowledge_mode": r.knowledge_mode,
        "suggest_instrumented_tests": bool(
            getattr(r, "suggest_instrumented_tests", False)
        ),
        "user_prompt": r.user_prompt or "",
        "gemini_model": r.gemini_model,
        "error_message": r.error_message,
        "correction_history": r.correction_history or [],
        "user_id": str(r.user_id) if r.user_id else None,
        "project_id": str(r.project_id) if getattr(r, "project_id", None) else None,
        "assets": [serialize_asset(a) for a in sorted(r.assets or [], key=lambda x: (x.sort_order, x.filename))],
        "gemini_available": gemini_available(),
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }
    if include_content:
        from core.inspection_report.instrumented_tests import report_wants_ensaios

        if report_wants_ensaios(r, r.content):
            data["content"] = prepare_report_content(r)
        else:
            data["content"] = r.content
    return data


def list_templates(db: Session, *, active_only: bool = True) -> list[dict[str, Any]]:
    q = db.query(InspectionReportTemplate)
    if active_only:
        q = q.filter(InspectionReportTemplate.active.is_(True))
    rows = q.order_by(InspectionReportTemplate.name).all()
    return [serialize_template(t) for t in rows]


def create_template(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    slug = re.sub(r"[^a-z0-9_]+", "_", (payload.get("slug") or payload.get("name") or "custom").lower())
    slug = slug.strip("_")[:80] or f"tpl_{uuid.uuid4().hex[:8]}"
    tpl = InspectionReportTemplate(
        slug=slug,
        name=payload.get("name") or slug,
        description=payload.get("description"),
        discipline_hint=payload.get("discipline_hint") or "GERAL",
        chapters=payload.get("chapters") or list(DEFAULT_CHAPTERS),
        system_prompt=payload.get("system_prompt") or SYSTEM_PROMPT_BASE,
        active=bool(payload.get("active", True)),
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return serialize_template(tpl)


def update_template(db: Session, template_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    tpl = db.get(InspectionReportTemplate, template_id)
    if not tpl:
        return None
    for key in ("name", "description", "discipline_hint", "system_prompt"):
        if key in payload and payload[key] is not None:
            setattr(tpl, key, payload[key])
    if "chapters" in payload and payload["chapters"] is not None:
        tpl.chapters = payload["chapters"]
    if "active" in payload:
        tpl.active = bool(payload["active"])
    db.commit()
    db.refresh(tpl)
    return serialize_template(tpl)


def list_reports(
    db: Session,
    *,
    user_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    limit: int = 50,
    include_orphans: bool = True,
) -> list[dict[str, Any]]:
    q = db.query(InspectionReport).options(
        joinedload(InspectionReport.template),
        joinedload(InspectionReport.assets),
    )
    if user_id:
        if include_orphans:
            q = q.filter(
                (InspectionReport.user_id == user_id) | (InspectionReport.user_id.is_(None))
            )
        else:
            q = q.filter(InspectionReport.user_id == user_id)
    if project_id:
        q = q.filter(InspectionReport.project_id == project_id)
    rows = q.order_by(InspectionReport.updated_at.desc()).limit(limit).all()
    return [serialize_report(r, include_content=False) for r in rows]


def get_report(db: Session, report_id: uuid.UUID) -> InspectionReport | None:
    return (
        db.query(InspectionReport)
        .options(joinedload(InspectionReport.template), joinedload(InspectionReport.assets))
        .filter(InspectionReport.id == report_id)
        .first()
    )


def create_report(
    db: Session,
    *,
    title: str,
    template_id: uuid.UUID | None,
    user_prompt: str,
    knowledge_mode: str,
    user_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    suggest_instrumented_tests: bool = False,
) -> dict[str, Any]:
    mode = knowledge_mode if knowledge_mode in ("attachments", "attachments_and_kb") else "attachments_and_kb"
    report = InspectionReport(
        title=title or "Laudo de vistoria",
        template_id=template_id,
        user_prompt=user_prompt or "",
        knowledge_mode=mode,
        suggest_instrumented_tests=bool(suggest_instrumented_tests),
        status="draft",
        user_id=user_id,
        project_id=project_id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    report_dir(report.id)
    _record_laudo_activity(
        report=report,
        event_type="created",
        title=f"Laudo criado: {report.title}",
        summary="Rascunho de laudo de vistoria",
    )
    return serialize_report(get_report(db, report.id) or report)


def update_report_meta(db: Session, report_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    from core.inspection_report.format_utils import normalize_parties, normalize_solicitante

    report = get_report(db, report_id)
    if not report:
        return None
    if "title" in payload and payload["title"]:
        report.title = str(payload["title"])[:300]
    if "user_prompt" in payload and payload["user_prompt"] is not None:
        report.user_prompt = str(payload["user_prompt"])
    if "knowledge_mode" in payload and payload["knowledge_mode"] in (
        "attachments",
        "attachments_and_kb",
    ):
        report.knowledge_mode = payload["knowledge_mode"]
    if "suggest_instrumented_tests" in payload and payload["suggest_instrumented_tests"] is not None:
        report.suggest_instrumented_tests = bool(payload["suggest_instrumented_tests"])
    if "template_id" in payload:
        report.template_id = uuid.UUID(str(payload["template_id"])) if payload["template_id"] else None
    if "project_id" in payload:
        report.project_id = uuid.UUID(str(payload["project_id"])) if payload["project_id"] else None

    content_keys = ("responsaveis_tecnicos", "responsaveis_imagens", "solicitante")
    content = dict(report.content or {})
    content_changed = False
    if any(k in payload for k in content_keys):
        if "responsaveis_tecnicos" in payload:
            content["responsaveis_tecnicos"] = normalize_parties(payload.get("responsaveis_tecnicos"))
        if "responsaveis_imagens" in payload:
            content["responsaveis_imagens"] = normalize_parties(payload.get("responsaveis_imagens"))
        if "solicitante" in payload:
            content["solicitante"] = normalize_solicitante(payload.get("solicitante"))
        content_changed = True

    # L7 — edição humana de capítulos / legendas sem re-Gemini
    if "chapters" in payload and payload["chapters"] is not None:
        content["chapters"] = payload["chapters"]
        content_changed = True
    if "photographic_report" in payload and payload["photographic_report"] is not None:
        content["photographic_report"] = payload["photographic_report"]
        content_changed = True
    if "content_patch" in payload and isinstance(payload["content_patch"], dict):
        for k, v in payload["content_patch"].items():
            content[k] = v
        content_changed = True

    if content_changed:
        report.content = content

    db.commit()
    return serialize_report(get_report(db, report_id) or report)


def _image_meta(path: Path) -> tuple[int | None, int | None, str | None]:
    try:
        from core.inspection_report.analytics import open_image_upright

        img = open_image_upright(path)
        w, h = img.size
        orient = "landscape" if w >= h else "portrait"
        return w, h, orient
    except Exception:
        return None, None, None


def _extract_pdf_text(path: Path, max_chars: int = 12000) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        parts: list[str] = []
        for page in reader.pages[:30]:
            parts.append(page.extract_text() or "")
            if sum(len(p) for p in parts) >= max_chars:
                break
        text = "\n".join(parts)[:max_chars]
        # PostgreSQL rejeita NUL (\x00) em colunas Text — comum em PDF.
        return text.replace("\x00", "").strip()
    except Exception as exc:
        logger.warning("PDF extract fail %s: %s", path, exc)
        return ""


def add_asset(
    db: Session,
    report_id: uuid.UUID,
    *,
    filename: str,
    content: bytes,
    mime_type: str | None = None,
    caption: str | None = None,
    kind_hint: str | None = None,
) -> dict[str, Any]:
    report = get_report(db, report_id)
    if not report:
        raise ValueError("Laudo não encontrado")

    if len(content) > MAX_ASSET_BYTES:
        raise ValueError(
            f"Arquivo excede o limite de {MAX_ASSET_BYTES // (1024 * 1024)} MB"
        )

    suffix = Path(filename).suffix.lower()
    if kind_hint in ("document", "image", "norm", "georef", "art", "signature"):
        kind = kind_hint
    elif suffix in IMAGE_EXTS:
        kind = "image"
    else:
        kind = "document"

    if kind == "georef" and suffix not in IMAGE_EXTS:
        raise ValueError("Imagem georreferenciada deve ser JPG/PNG/TIFF")
    if kind == "art" and suffix != ".pdf":
        raise ValueError("Anexo ART deve ser PDF")
    if kind == "signature" and suffix not in IMAGE_EXTS:
        raise ValueError("Imagem de assinatura deve ser JPG/PNG/TIFF")

    n_images = len([a for a in (report.assets or []) if a.kind == "image"])
    n_docs = len(
        [a for a in (report.assets or []) if a.kind in ("document", "norm", "art")]
    )
    if kind == "image" and n_images >= MAX_IMAGES_PER_REPORT:
        raise ValueError(f"Limite de {MAX_IMAGES_PER_REPORT} fotos por laudo atingido")
    if kind in ("document", "norm", "art") and n_docs >= MAX_DOCS_PER_REPORT:
        raise ValueError(f"Limite de {MAX_DOCS_PER_REPORT} documentos por laudo atingido")
    n_sigs = len([a for a in (report.assets or []) if a.kind == "signature"])
    if kind == "signature" and n_sigs >= 10:
        raise ValueError("Limite de 10 imagens de assinatura por laudo")

    # Substitui georef anterior (mantém só uma)
    if kind == "georef":
        for old in list(report.assets or []):
            if old.kind == "georef":
                old_path = report_dir(report_id) / old.stored_name
                db.delete(old)
                try:
                    if old_path.exists():
                        old_path.unlink(missing_ok=True)
                except Exception:
                    pass
        db.flush()

    safe = re.sub(r"[^\w.\-]+", "_", filename)[:180] or "arquivo.bin"
    stored = f"{uuid.uuid4().hex[:10]}_{safe}"
    dest = report_dir(report_id) / stored
    try:
        dest.write_bytes(content)
    except OSError as exc:
        raise RuntimeError(f"Falha ao gravar anexo: {exc}") from exc

    width = height = None
    orientation = None
    extracted = None
    photo_number = None
    sort_order = len([a for a in (report.assets or []) if a.kind != "georef"])

    if kind in ("image", "georef"):
        width, height, orientation = _image_meta(dest)
        if kind == "image":
            existing_photos = [a for a in (report.assets or []) if a.kind == "image"]
            photo_number = len(existing_photos) + 1
        else:
            from core.inspection_report.format_utils import inject_coordinates_into_object_tables
            from core.inspection_report.geo_utils import encode_gps_payload, extract_gps_from_image

            gps = extract_gps_from_image(dest)
            if gps:
                extracted = encode_gps_payload(gps)
                caption = caption or f"Imagem georreferenciada — {gps.get('label')}"
            else:
                extracted = encode_gps_payload(None, note="sem_gps_exif")
                caption = caption or "Imagem georreferenciada (EXIF sem GPS)"
            # Atualiza content do laudo com coordenadas
            content_dict = dict(report.content or {})
            if gps:
                content_dict = inject_coordinates_into_object_tables(
                    content_dict,
                    latitude=gps.get("latitude"),
                    longitude=gps.get("longitude"),
                    label=gps.get("label"),
                )
            content_dict["georreferencia"] = {
                **(content_dict.get("georreferencia") or {}),
                **(gps or {}),
                "filename": filename,
                "has_gps": bool(gps),
            }
            report.content = content_dict
    elif suffix == ".pdf":
        # Extração é best-effort — falha de parse não pode abortar o upload.
        try:
            extracted = _extract_pdf_text(dest) or None
        except Exception as exc:
            logger.warning("Ignorando falha de parse PDF %s: %s", filename, exc)
            extracted = None
    elif suffix in {".txt", ".md"}:
        try:
            extracted = content.decode("utf-8", errors="ignore").replace("\x00", "")[:12000] or None
        except Exception:
            extracted = None

    asset = InspectionReportAsset(
        report_id=report_id,
        kind=kind,
        filename=(filename or "arquivo.bin")[:260],
        stored_name=stored,
        mime_type=mime_type,
        caption=caption,
        photo_number=photo_number,
        sort_order=sort_order,
        width=width,
        height=height,
        orientation=orientation,
        extracted_text=extracted,
    )
    try:
        db.add(asset)
        db.commit()
        db.refresh(asset)
        if kind == "georef":
            # grava asset_id no content
            content_dict = dict(report.content or {})
            geo = dict(content_dict.get("georreferencia") or {})
            geo["asset_id"] = str(asset.id)
            content_dict["georreferencia"] = geo
            report.content = content_dict
            db.commit()
            db.refresh(report)
    except Exception:
        db.rollback()
        if dest.exists():
            dest.unlink(missing_ok=True)
        raise
    return serialize_asset(asset)


def update_asset_caption(
    db: Session,
    report_id: uuid.UUID,
    asset_id: uuid.UUID,
    caption: str | None,
) -> dict[str, Any] | None:
    """L7 — atualiza legenda do anexo sem regenerar o laudo."""
    asset = db.get(InspectionReportAsset, asset_id)
    if not asset or asset.report_id != report_id:
        return None
    asset.caption = caption
    report = get_report(db, report_id)
    if report and asset.kind == "image" and isinstance(report.content, dict):
        content = dict(report.content)
        photos = list(content.get("photographic_report") or [])
        for ph in photos:
            if not isinstance(ph, dict):
                continue
            if int(ph.get("photo_number") or 0) == int(asset.photo_number or 0) or (
                str(ph.get("filename") or "").lower() == asset.filename.lower()
            ):
                if caption:
                    ph["title"] = caption
                    ph["legend"] = caption
                break
        content["photographic_report"] = photos
        report.content = content
    db.commit()
    db.refresh(asset)
    return serialize_asset(asset)


def delete_report(db: Session, report_id: uuid.UUID) -> bool:
    report = get_report(db, report_id)
    if not report:
        return False
    folder = report_dir(report_id)
    db.delete(report)
    db.commit()
    try:
        import shutil

        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)
    except Exception as exc:
        logger.warning("Falha ao limpar pasta do laudo %s: %s", report_id, exc)
    return True


def delete_asset(db: Session, report_id: uuid.UUID, asset_id: uuid.UUID) -> bool:
    asset = db.get(InspectionReportAsset, asset_id)
    if not asset or asset.report_id != report_id:
        return False
    was_georef = asset.kind == "georef"
    path = report_dir(report_id) / asset.stored_name
    if path.exists():
        path.unlink(missing_ok=True)
    db.delete(asset)
    db.commit()
    # renumerar fotos
    report = get_report(db, report_id)
    if report:
        photos = sorted(
            [a for a in report.assets if a.kind == "image"],
            key=lambda a: a.sort_order,
        )
        for i, a in enumerate(photos, start=1):
            a.photo_number = i
        if was_georef and isinstance(report.content, dict):
            content = dict(report.content)
            content.pop("georreferencia", None)
            report.content = content
        db.commit()
    return True


def get_assay_results_view(db: Session, report_id: uuid.UUID) -> dict[str, Any] | None:
    from core.inspection_report.assay_results import build_assay_results_view

    report = get_report(db, report_id)
    if not report:
        return None
    return build_assay_results_view(report)


def save_assay_results(
    db: Session,
    report_id: uuid.UUID,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Persiste resultados L16 e re-aplica enriquecimento para export."""
    from core.inspection_report.assay_results import (
        build_assay_results_view,
        merge_assay_results,
        validate_assay_results,
    )
    from core.inspection_report.engineering_enrichment import apply_engineering_enrichment

    report = get_report(db, report_id)
    if not report:
        raise ValueError("Laudo não encontrado")

    errors = validate_assay_results(items)
    if errors:
        raise ValueError("; ".join(errors))

    content = merge_assay_results(dict(report.content or {}), items)
    slug = report.template.slug if report.template else None
    content = apply_engineering_enrichment(content, slug=slug)
    report.content = content
    db.commit()
    db.refresh(report)
    _record_laudo_activity(
        report=report,
        event_type="updated",
        title=f"Resultados de ensaio L16: {report.title}",
        summary=f"{len(items)} registro(s)",
    )
    return build_assay_results_view(report)


def get_visual_memory_view(db: Session, report_id: uuid.UUID) -> dict[str, Any] | None:
    from core.inspection_report.visual_memory import build_visual_memory_view

    report = get_report(db, report_id)
    if not report:
        return None
    return build_visual_memory_view(report)


def save_visual_memory(
    db: Session,
    report_id: uuid.UUID,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    from core.inspection_report.visual_memory import (
        build_visual_memory_view,
        merge_visual_memory,
        validate_visual_memory,
    )

    report = get_report(db, report_id)
    if not report:
        raise ValueError("Laudo não encontrado")
    errors = validate_visual_memory(items)
    if errors:
        raise ValueError("; ".join(errors))
    # Preenche photo_number a partir dos assets
    by_id = {str(a.id): a for a in (report.assets or []) if a.kind == "image"}
    enriched = []
    for item in items:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        asset = by_id.get(str(row.get("asset_id") or ""))
        if asset and row.get("photo_number") is None:
            row["photo_number"] = asset.photo_number
        enriched.append(row)
    report.content = merge_visual_memory(dict(report.content or {}), enriched)
    db.commit()
    db.refresh(report)
    _record_laudo_activity(
        report=report,
        event_type="updated",
        title=f"Croquis L17: {report.title}",
        summary=f"{len(enriched)} croqui(s)",
    )
    return build_visual_memory_view(report)


def save_signature_evidence(
    db: Session,
    report_id: uuid.UUID,
    patch: dict[str, Any],
) -> dict[str, Any]:
    from core.inspection_report.signature_evidence import (
        get_signature_evidence,
        merge_signature_evidence,
    )

    report = get_report(db, report_id)
    if not report:
        raise ValueError("Laudo não encontrado")
    content = merge_signature_evidence(dict(report.content or {}), patch)
    # Espelha signature_asset_id nos parties quando informado no mapa
    ids = (content.get("signature_evidence") or {}).get("rt_signature_asset_ids") or {}
    if ids:
        rts = list((content.get("responsaveis_tecnicos") or []))
        updated = []
        for rt in rts:
            if not isinstance(rt, dict):
                continue
            row = dict(rt)
            pid = str(row.get("id") or "")
            if pid in ids:
                row["signature_asset_id"] = ids[pid]
            updated.append(row)
        content["responsaveis_tecnicos"] = updated
    report.content = content
    db.commit()
    db.refresh(report)
    return get_signature_evidence(report.content)


def record_export_pdf_hash(
    db: Session,
    report: InspectionReport,
    pdf_bytes: bytes,
    *,
    method: str = "image_hash",
    pades_meta: dict[str, Any] | None = None,
) -> str:
    from core.inspection_report.signature_evidence import record_pdf_hash, sha256_hex

    digest = sha256_hex(pdf_bytes)
    report.content = record_pdf_hash(
        dict(report.content or {}),
        pdf_bytes,
        method=method,
        pades_meta=pades_meta,
    )
    db.commit()
    return digest


def assign_report_owner(
    db: Session,
    report_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> dict[str, Any] | None:
    report = get_report(db, report_id)
    if not report:
        return None
    report.user_id = owner_id
    db.commit()
    db.refresh(report)
    _record_laudo_activity(
        report=report,
        event_type="updated",
        title=f"Dono atribuído: {report.title}",
        summary=f"user_id={owner_id}",
    )
    return serialize_report(report)


def list_orphan_reports(db: Session, *, limit: int = 100) -> list[dict[str, Any]]:
    rows = (
        db.query(InspectionReport)
        .options(joinedload(InspectionReport.template), joinedload(InspectionReport.assets))
        .filter(InspectionReport.user_id.is_(None))
        .order_by(InspectionReport.updated_at.desc())
        .limit(limit)
        .all()
    )
    return [serialize_report(r, include_content=False) for r in rows]


def backfill_orphan_reports(db: Session, owner_id: uuid.UUID) -> dict[str, Any]:
    rows = (
        db.query(InspectionReport)
        .filter(InspectionReport.user_id.is_(None))
        .all()
    )
    for r in rows:
        r.user_id = owner_id
    db.commit()
    return {"assigned": len(rows), "user_id": str(owner_id)}


def prepare_report_content(report: InspectionReport, *, persist: bool = False, db: Session | None = None) -> dict[str, Any]:
    """
    Conteúdo pronto para export/preview: aplica ensaios instrumentados (se flag)
    e enriquecimento L10–L12 (classificação DNIT, inventário, metrologia).
    """
    from core.inspection_report.engineering_enrichment import apply_engineering_enrichment
    from core.inspection_report.instrumented_tests import (
        apply_instrumented_tests_to_content,
        report_wants_ensaios,
    )

    content = dict(report.content or {})
    slug = report.template.slug if report.template else None
    want = report_wants_ensaios(report, content)
    prepared = apply_instrumented_tests_to_content(
        content,
        slug=slug,
        enabled=want,
        user_prompt=report.user_prompt or "",
    )
    prepared = apply_engineering_enrichment(prepared, slug=slug)
    if persist and db is not None and prepared != (report.content or {}):
        report.content = prepared
        db.commit()
    return prepared


def _knowledge_context(query: str, discipline: str) -> str:
    """Fallback legado — preferir retrieve_laudo_normative_context (L15)."""
    try:
        from memory.rag_engine import get_rag_engine

        return get_rag_engine().build_context(
            query=query or "laudo de vistoria patologias engenharia civil",
            discipline=discipline if discipline != "GERAL" else None,
            doc_type="nbr",
            top_k=8,
        )
    except Exception as exc:
        logger.warning("RAG laudo falhou: %s", exc)
        return ""


def generate_report(
    db: Session,
    report_id: uuid.UUID,
    *,
    progress_cb: Any | None = None,
) -> dict[str, Any]:
    """
    Gera o laudo. `progress_cb(phase, percent, message)` é opcional.
    """

    def _progress(phase: str, percent: int, message: str) -> None:
        if progress_cb:
            progress_cb(phase, percent, message)

    report = get_report(db, report_id)
    if not report:
        raise ValueError("Laudo não encontrado")

    clear_cancel_generation(report_id)
    report.status = "generating"
    report.error_message = None
    db.commit()
    _progress("prepare", 8, "Preparando laudo e validando dados…")
    _check_cancelled(report_id)

    try:
        template = report.template
        slug = (template.slug if template else None) or None
        chapters = (template.chapters if template else None) or chapters_for_slug(slug)
        system_prompt = (template.system_prompt if template else None) or system_prompt_for_slug(
            slug,
            name=(template.name if template else "") or "",
            description=(template.description if template else "") or "",
        )
        discipline = (template.discipline_hint if template else "GERAL") or "GERAL"
        from core.inspection_report.engineering_enrichment import build_engineering_prompt_block

        want_ensaios = bool(getattr(report, "suggest_instrumented_tests", False))
        ensaios_block = ""
        if want_ensaios:
            from core.inspection_report.instrumented_tests import (
                build_ensaios_prompt_block,
                chapters_with_ensaios,
            )
            chapters = chapters_with_ensaios(chapters)
            ensaios_block = build_ensaios_prompt_block(slug, report.user_prompt or "")
            system_prompt = f"{system_prompt}\n\n{ensaios_block}"
        # L10–L12 sempre no prompt (classificação, inventário, metrologia)
        system_prompt = f"{system_prompt}\n\n{build_engineering_prompt_block(slug)}"

        company = get_company_profile()
        company_source = company.display_name() or company.razao_social or "Empresa responsável pelo laudo"

        _progress("attachments", 18, "Lendo documentos e fotografias anexadas…")
        docs: list[str] = []
        images: list[Path] = []
        photo_meta: list[dict[str, Any]] = []
        georef_path: Path | None = None
        georef_meta: dict[str, Any] | None = None
        for asset in sorted(report.assets or [], key=lambda a: (a.sort_order, a.filename)):
            path = report_dir(report_id) / asset.stored_name
            if asset.kind == "image" and path.exists():
                images.append(path)
                photo_meta.append(
                    {
                        "photo_number": asset.photo_number or len(photo_meta) + 1,
                        "filename": asset.filename,
                        "caption": asset.caption,
                        "orientation": asset.orientation,
                    }
                )
            elif asset.kind == "georef" and path.exists():
                georef_path = path
                from core.inspection_report.geo_utils import decode_gps_payload

                gps = decode_gps_payload(asset.extracted_text) or {}
                geo_content = (report.content or {}).get("georreferencia") or {}
                georef_meta = {
                    "filename": asset.filename,
                    "caption": asset.caption,
                    "latitude": gps.get("latitude", geo_content.get("latitude")),
                    "longitude": gps.get("longitude", geo_content.get("longitude")),
                    "label": gps.get("label") or geo_content.get("label"),
                }
            elif asset.extracted_text:
                docs.append(f"[{asset.filename}]\n{asset.extracted_text}")

        _check_cancelled(report_id)
        _progress(
            "attachments",
            28,
            f"Anexos prontos: {len(docs)} documento(s), {len(images)} foto(s)"
            + (", georref." if georef_path else "")
            + ".",
        )

        kb = ""
        normative_pack: dict[str, Any] | None = None
        if report.knowledge_mode == "attachments_and_kb":
            _progress("knowledge", 38, "Consultando base de conhecimento (RAG L15)…")
            try:
                from core.inspection_report.normative_rag import retrieve_laudo_normative_context

                normative_pack = retrieve_laudo_normative_context(
                    slug=slug,
                    query=report.user_prompt or report.title or "",
                    discipline_hint=discipline,
                    top_k=10,
                )
                kb = str(normative_pack.get("context_text") or "")
                if not kb:
                    kb = _knowledge_context(report.user_prompt or report.title, discipline)
            except Exception as exc:
                logger.warning("L15 RAG falhou, fallback legado: %s", exc)
                kb = _knowledge_context(report.user_prompt or report.title, discipline)
                normative_pack = None
            n_hits = int((normative_pack or {}).get("hits_count") or 0)
            _progress(
                "knowledge",
                48,
                (
                    f"Contexto normativo L15: {n_hits} trecho(s)."
                    if kb
                    else "RAG sem resultados — seguindo só com anexos."
                ),
            )
        else:
            _progress("knowledge", 45, "Modo somente anexos — pulando base de conhecimento.")

        _check_cancelled(report_id)
        _progress("gemini", 55, "Enviando documentos e fotos ao Gemini (análise detalhada)…")

        def _gemini_progress(phase: str, pct: int, msg: str) -> None:
            _check_cancelled(report_id)
            _progress(phase, pct, msg)

        content, model = generate_laudo_content(
            system_prompt=system_prompt,
            user_prompt=report.user_prompt,
            document_excerpts=docs,
            knowledge_context=kb,
            image_paths=images,
            photo_meta=photo_meta,
            company_source=company_source,
            chapters=chapters,
            progress_cb=_gemini_progress,
            georef_path=georef_path,
            georef_meta=georef_meta,
            instrumented_tests_hint=ensaios_block if want_ensaios else "",
        )
        _check_cancelled(report_id)
        _progress("structure", 85, "Estruturando capítulos, patologias e relatório fotográfico…")

        # Garantir que todas as fotos existam no relatório fotográfico (campos ricos)
        photo_report = list(content.get("photographic_report") or [])
        by_num = {
            int(p.get("photo_number") or 0): p
            for p in photo_report
            if p.get("photo_number") is not None
        }
        by_file = {str(p.get("filename") or "").lower(): p for p in photo_report}
        ensured: list[dict[str, Any]] = []
        for meta in photo_meta:
            key = meta["filename"].lower()
            entry = by_num.get(int(meta["photo_number"])) or by_file.get(key) or {}
            description = (
                entry.get("description")
                or meta.get("caption")
                or ""
            )
            if not description or str(description).lower().startswith("registro fotográfico"):
                description = (
                    f"Registro da diligência referente a {meta['filename']}. "
                    "Revisar legenda técnica com base na imagem original."
                )
            ensured.append(
                {
                    "photo_number": meta["photo_number"],
                    "filename": meta["filename"],
                    "title": entry.get("title")
                    or meta.get("caption")
                    or f"Foto {meta['photo_number']:02d}",
                    "description": description,
                    "legend": entry.get("legend") or "",
                    "severity": entry.get("severity") or "média",
                    "score": entry.get("score") or 3,
                    "source": entry.get("source") or company_source,
                    "pathology_refs": entry.get("pathology_refs") or [],
                    "orientation": meta.get("orientation"),
                }
            )
        content["photographic_report"] = ensured
        if not content.get("titulo"):
            content["titulo"] = report.title

        # Preserva responsáveis / solicitante / georref cadastrados na UI
        prev = report.content if isinstance(report.content, dict) else {}
        for key in ("responsaveis_tecnicos", "responsaveis_imagens", "solicitante", "georreferencia"):
            if key in prev and prev[key] is not None:
                content[key] = prev[key]
        # Reaplica coordenadas na ficha técnica gerada
        geo = content.get("georreferencia") or {}
        if geo.get("latitude") is not None and geo.get("longitude") is not None:
            from core.inspection_report.format_utils import inject_coordinates_into_object_tables

            content = inject_coordinates_into_object_tables(
                content,
                latitude=geo.get("latitude"),
                longitude=geo.get("longitude"),
                label=geo.get("label"),
            )

        from core.inspection_report.engineering_enrichment import apply_engineering_enrichment
        from core.inspection_report.instrumented_tests import apply_instrumented_tests_to_content

        if want_ensaios:
            _progress(
                "structure",
                88,
                "Etapa crítica: consolidando TODOS os ensaios por gravidade e template…",
            )
        content = apply_instrumented_tests_to_content(
            content,
            slug=slug,
            enabled=want_ensaios,
            user_prompt=report.user_prompt or "",
        )
        if want_ensaios:
            n_ensaios = len((content.get("instrumented_tests") or []))
            quality = content.get("ensaios_quality") or {}
            _progress(
                "structure",
                90,
                f"Ensaios instrumentados consolidados: {n_ensaios} item(ns)"
                + (
                    f" (Gemini: {quality.get('gemini_count', 0)}; "
                    f"gravidade máx.: {quality.get('max_severity', '—')})"
                    if quality
                    else ""
                )
                + ".",
            )

        _progress(
            "structure",
            91,
            "Aplicando L10–L20 (classificação, inventário, metrologia, RAG, editorial)…",
        )
        content = apply_engineering_enrichment(
            content, slug=slug, normative=normative_pack
        )
        cls = content.get("classification") or {}
        if cls.get("global_dnit_note") is not None:
            _progress(
                "structure",
                91,
                f"Classificação DNIT global: {cls.get('global_dnit_note')} "
                f"({cls.get('global_label') or '—'}); "
                f"{len(content.get('element_inventory') or [])} elemento(s) no inventário.",
            )
        ep = content.get("editorial_postprocess") or {}
        if ep.get("applied"):
            n_w = len(ep.get("warnings") or [])
            _progress(
                "structure",
                92,
                "L20 editorial institucional aplicado"
                + (f" ({n_w} aviso(s) de coerência)" if n_w else "")
                + ".",
            )
        n_cit = len(content.get("normative_citations") or [])
        if n_cit:
            _progress(
                "structure",
                91,
                f"L15: {n_cit} citação(ões) normativa(s) rastreável(is) no capítulo Referências.",
            )

        _check_cancelled(report_id)
        _progress("persist", 92, "Salvando laudo gerado…")
        report.content = content
        report.gemini_model = model
        report.status = "generated"
        report.title = str(content.get("titulo") or report.title)[:300]
        db.commit()
        _record_laudo_activity(
            report=report,
            event_type="generated",
            title=f"Laudo gerado: {report.title}",
            summary=f"Modelo {model}",
        )
        _progress("done", 100, "Laudo gerado com sucesso.")
    except GenerationCancelled as exc:
        logger.info("Geração cancelada laudo %s", report_id)
        report.status = "draft"
        report.error_message = str(exc)
        db.commit()
        _progress("error", 100, str(exc))
        raise
    except Exception as exc:
        logger.exception("Falha ao gerar laudo %s", report_id)
        report.status = "error"
        report.error_message = str(exc)
        db.commit()
        _progress("error", 100, f"Falha: {exc}")
        raise
    finally:
        clear_cancel_generation(report_id)

    return serialize_report(get_report(db, report_id) or report)


def iter_generate_report_events(report_id: uuid.UUID):
    """Gera eventos SSE de progresso + done/error (thread-safe com nova sessão)."""
    import queue as queue_mod
    import threading

    from core.database.connection import SessionLocal
    from core.stream_events import format_sse, format_sse_keepalive

    # Teto de % por fase — heartbeat sobe gradualmente até o teto enquanto a etapa roda
    phase_caps: dict[str, int] = {
        "start": 8,
        "prepare": 16,
        "attachments": 34,
        "knowledge": 52,
        "gemini": 82,
        "structure": 90,
        "persist": 97,
        "done": 100,
        "error": 100,
    }

    out_q: queue_mod.Queue[tuple[str, Any]] = queue_mod.Queue()

    def _worker() -> None:
        db = SessionLocal()
        try:

            def cb(phase: str, percent: int, message: str) -> None:
                out_q.put(
                    (
                        "progress",
                        {
                            "phase": phase,
                            "percent": percent,
                            "message": message,
                            "report_id": str(report_id),
                        },
                    )
                )

            result = generate_report(db, report_id, progress_cb=cb)
            out_q.put(("done", result))
        except Exception as exc:
            out_q.put(
                (
                    "error",
                    {
                        "message": str(exc),
                        "percent": 100,
                        "phase": "error",
                        "report_id": str(report_id),
                    },
                )
            )
        finally:
            db.close()
            out_q.put(("end", None))

    def _flush_pad() -> str:
        # Padding para forçar flush em proxies (Next.js rewrite / nginx)
        return f":{' ' * 2048}\n\n"

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()

    first = {
        "phase": "start",
        "percent": 2,
        "message": "Iniciando geração do laudo…",
        "report_id": str(report_id),
    }
    yield format_sse("progress", first)
    yield _flush_pad()

    last_progress: dict[str, Any] = dict(first)

    while True:
        try:
            kind, payload = out_q.get(timeout=2.0)
        except queue_mod.Empty:
            yield format_sse_keepalive()
            # Heartbeat: sobe 1% até o teto da fase (evita UI travada em 2%)
            phase = str(last_progress.get("phase") or "gemini")
            cap = phase_caps.get(phase, 80)
            cur = int(last_progress.get("percent") or 0)
            nxt = min(cap, cur + 1) if cur < cap else cur
            msg = str(last_progress.get("message") or "Processando…")
            if "(ainda" not in msg.lower():
                msg = f"{msg} (ainda em andamento…)"
            last_progress = {
                **last_progress,
                "percent": nxt,
                "message": msg,
            }
            yield format_sse("progress", last_progress)
            yield _flush_pad()
            continue
        if kind == "end":
            break
        if kind == "progress":
            # Nunca regride o percentual
            prev_pct = int(last_progress.get("percent") or 0)
            new_pct = max(prev_pct, int(payload.get("percent") or 0))
            last_progress = {**payload, "percent": new_pct}
            yield format_sse("progress", last_progress)
            yield _flush_pad()
        elif kind == "done":
            yield format_sse("done", {"ok": True, "report": payload})
            yield _flush_pad()
        elif kind == "error":
            yield format_sse("error", payload)
            yield _flush_pad()

    thread.join(timeout=2)


def prepare_correction(db: Session, report_id: uuid.UUID, correction_prompt: str) -> InspectionReport:
    """Prepara histórico + prompt truncado antes da regeneração (L2)."""
    report = get_report(db, report_id)
    if not report:
        raise ValueError("Laudo não encontrado")
    if not report.content:
        raise ValueError("Gere o laudo antes de solicitar correções")

    history = list(report.correction_history or [])
    history.append({"prompt": correction_prompt, "previous_status": report.status})
    report.correction_history = history
    summary = _summarize_content_for_correction(
        report.content if isinstance(report.content, dict) else {}
    )
    report.user_prompt = (
        (report.user_prompt or "")
        + "\n\n--- CORREÇÃO SOLICITADA PELO PROFISSIONAL ---\n"
        + correction_prompt
        + "\n\nRESUMO DO LAUDO ATUAL PARA REVISAR:\n"
        + summary
    )
    report.status = "correcting"
    db.commit()
    return report


def correct_report(db: Session, report_id: uuid.UUID, correction_prompt: str) -> dict[str, Any]:
    prepare_correction(db, report_id, correction_prompt)
    result = generate_report(db, report_id)
    report = get_report(db, report_id)
    if report:
        _record_laudo_activity(
            report=report,
            event_type="corrected",
            title=f"Laudo corrigido: {report.title}",
            summary=correction_prompt[:200],
        )
    return result


def iter_correct_report_events(report_id: uuid.UUID, correction_prompt: str):
    """SSE da correção — prepara prompt e reutiliza o stream de geração (L2)."""
    from core.database.connection import SessionLocal

    db = SessionLocal()
    try:
        prepare_correction(db, report_id, correction_prompt.strip())
    finally:
        db.close()
    yield from iter_generate_report_events(report_id)


def asset_path(report_id: uuid.UUID, asset: InspectionReportAsset) -> Path:
    return report_dir(report_id) / asset.stored_name
