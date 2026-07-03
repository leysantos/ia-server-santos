from __future__ import annotations

import re
import unicodedata

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from app.routes.pricing.schemas import ExportBrandingUpdateRequest
from app.routes.pricing.shared import _get_budget_engine

router = APIRouter()


def _ascii_export_slug(text: str, *, max_len: int = 40, fallback: str = "Orcamento") -> str:
    """Slug ASCII para Content-Disposition (evita § e acentos que quebram TestClient/HTTP)."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^\w\-.]+", "_", ascii_text.replace(" ", "_")).strip("._")
    return (slug or fallback)[:max_len]

@router.get("/budget/{session_id}/export")
def export_budget_excel_legacy(session_id: str):
    from pricing.budget.budget_export_service import export_session_workbook_xlsx

    engine = _get_budget_engine()
    if not engine.get_session(session_id):
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    try:
        content = export_session_workbook_xlsx(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    filename = f"Orcamento_{session_id[:8]}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/budget/{session_id}/export/xlsx/{doc_type}")
def export_budget_excel(session_id: str, doc_type: str):
    from pricing.budget.budget_export_branding import EXPORT_DOC_TYPES
    from pricing.budget.budget_export_service import export_session_xlsx

    key = doc_type.strip().lower()
    if key not in EXPORT_DOC_TYPES:
        raise HTTPException(status_code=400, detail=f"Tipo inválido. Use: {', '.join(EXPORT_DOC_TYPES)}")
    engine = _get_budget_engine()
    if not engine.get_session(session_id):
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    try:
        content = export_session_xlsx(session_id, key)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    filename = f"{key.upper()}_{session_id[:8]}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/budget/{session_id}/export/branding")
def get_export_branding(session_id: str):
    from core.system.company_profile import load_company_logo
    from pricing.budget.budget_export_service import get_export_branding as _get_branding

    engine = _get_budget_engine()
    if not engine.get_session(session_id):
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    branding = _get_branding(session_id)
    return {**branding.to_dict(), "has_logo": load_company_logo() is not None}


@router.patch("/budget/{session_id}/export/branding")
def update_export_branding(session_id: str, body: ExportBrandingUpdateRequest):
    from pricing.budget.budget_export_service import update_export_branding as _update

    engine = _get_budget_engine()
    if not engine.get_session(session_id):
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    branding = _update(session_id, body.model_dump(exclude_unset=True))
    return {"export_branding": branding.to_dict(), "session": engine.get_session(session_id).to_dict()}


@router.post("/budget/{session_id}/export/logo")
async def upload_export_logo(session_id: str, file: UploadFile = File(...)):
    from core.system.company_profile import save_company_logo

    engine = _get_budget_engine()
    if not engine.get_session(session_id):
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo vazio")
    content_type = file.content_type or "image/png"
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Envie uma imagem (PNG, JPG, etc.)")
    save_company_logo(content, content_type=content_type)
    from pricing.budget.budget_export_service import get_export_branding_status

    return {"export_branding": get_export_branding_status(), "session": engine.get_session(session_id).to_dict()}


@router.get("/budget/{session_id}/export/logo")
def get_export_logo(session_id: str):
    from core.system.company_profile import load_company_logo

    engine = _get_budget_engine()
    if not engine.get_session(session_id):
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    logo = load_company_logo()
    if not logo:
        raise HTTPException(status_code=404, detail="Logo não configurada")
    return Response(content=logo, media_type="image/png")


@router.post("/budget/{session_id}/workbook/sync")
def sync_budget_workbook(session_id: str, sync: bool = True):
    """Sincroniza sessão → template `.xlsm` oficial SEMINF (B19)."""
    from pricing.budget.ppd_workbook_service import sync_workbook

    engine = _get_budget_engine()
    if not engine.get_session(session_id):
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    try:
        binding = sync_workbook(session_id) if sync else {}
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"session_id": session_id, "ppd_workbook": binding}


@router.get("/budget/{session_id}/export/xlsm")
def export_budget_xlsm_official(session_id: str, sync: bool = True):
    """Exporta workbook `.xlsm` oficial com fórmulas VLOOKUP/MCQ (B19)."""
    from pricing.budget.ppd_workbook_service import get_workbook_bytes, sync_workbook

    engine = _get_budget_engine()
    session = engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    try:
        if sync:
            sync_workbook(session_id)
        content = get_workbook_bytes(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    projeto = _ascii_export_slug(session.project.projeto or session.title or "Orcamento")
    filename = f"PPD_{projeto}_{session_id[:8]}.xlsm"
    return Response(
        content=content,
        media_type="application/vnd.ms-excel.sheet.macroEnabled.12",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/budget/{session_id}/export/pdf/{doc_type}")
def export_budget_pdf(session_id: str, doc_type: str):
    from pricing.budget.budget_export_branding import EXPORT_DOC_TYPES
    from pricing.budget.budget_export_service import export_session_pdf

    key = doc_type.strip().lower()
    if key not in EXPORT_DOC_TYPES:
        raise HTTPException(status_code=400, detail=f"Tipo inválido. Use: {', '.join(EXPORT_DOC_TYPES)}")
    try:
        content = export_session_pdf(session_id, key)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    filename = f"{key.upper()}_{session_id[:8]}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/budget/{session_id}/export/compliance-pack.json")
def export_budget_compliance_pack(session_id: str):
    """Checklist Lei 14.133 / TCU + metadados de defesa (B22)."""
    from pricing.budget.budget_compliance_pack import compliance_pack_json

    engine = _get_budget_engine()
    session = engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    content = compliance_pack_json(session)
    filename = f"compliance_{session_id[:8]}.json"
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
