"""Rotas HTTP — módulo Workflow Projetos."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.schemas.delivery_wizard import (
    DeliveryItemUpdateRequest,
    DeliveryPackageCreateRequest,
    DeliveryPackageUpdateRequest,
    DeliverySelectionRequest,
    NomenclatureStandardsResponse,
)
from app.schemas.workflow import (
    CompanyCreateRequest,
    WorkflowDashboardResponse,
    WorkflowProjectUpdateRequest,
)
from app.services.workflow_service import WorkflowService
from core.database import get_db
from core.workflow.delivery.wizard_service import get_delivery_wizard_service
from core.workflow.nomenclature.standards import (
    DISCIPLINE_CODES,
    DOCUMENT_FOLDERS,
    SHEET_FORMATS,
)

router = APIRouter(tags=["Workflow"])
workflow_service = WorkflowService()
wizard_service = get_delivery_wizard_service()


@router.get("/workflow/dashboard", response_model=WorkflowDashboardResponse)
def workflow_dashboard(
    company_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    return WorkflowDashboardResponse(**workflow_service.get_dashboard(db, company_id=company_id))


@router.get("/projects/{project_id}/workflow")
def get_project_workflow(project_id: str, db: Session = Depends(get_db)):
    return workflow_service.get_project_workflow(project_id, db)


@router.post("/projects/{project_id}/workflow/init")
def init_project_workflow(
    project_id: str,
    empresa_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    return workflow_service.initialize_project(project_id, db, empresa_id=empresa_id)


@router.post("/projects/{project_id}/workflow/process")
def process_project_workflow(
    project_id: str,
    sync: bool = Query(default=False),
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    return workflow_service.process_project(project_id, db, sync=sync, force=force)


@router.post("/projects/{project_id}/workflow/process/{file_id}")
def process_file_workflow(
    project_id: str,
    file_id: str,
    sync: bool = Query(default=False),
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    return workflow_service.process_file(project_id, file_id, db, sync=sync, force=force)


@router.get("/workflow/jobs/{job_id}")
def get_workflow_job(job_id: str, db: Session = Depends(get_db)):
    return workflow_service.get_job(job_id, db)


@router.get("/projects/{project_id}/workflow/jobs")
def list_project_workflow_jobs(
    project_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return workflow_service.list_project_jobs(project_id, db, limit=limit)


@router.get("/workflow/artifacts/download")
def download_workflow_artifact(key: str = Query(..., min_length=1)):
    """Download unificado — local (stream) ou MinIO (redirect presigned)."""
    from pathlib import Path

    from fastapi.responses import FileResponse, RedirectResponse, Response

    from core.workflow.storage.client import (
        WORKFLOW_LOCAL_ROOT,
        get_workflow_storage,
        sanitize_storage_key,
        stream_artifact,
    )

    safe_key = sanitize_storage_key(key)
    storage = get_workflow_storage()

    if storage.backend == "minio":
        presigned = storage.presigned_get_url(safe_key)
        if presigned:
            return RedirectResponse(presigned, status_code=307)
        data, filename = stream_artifact(safe_key)
        return Response(
            content=data,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    path = WORKFLOW_LOCAL_ROOT / safe_key
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Artefato não encontrado")
    return FileResponse(path, filename=Path(safe_key).name)


@router.patch("/projects/{project_id}/workflow")
def update_project_workflow_metadata(
    project_id: str,
    body: WorkflowProjectUpdateRequest,
    db: Session = Depends(get_db),
):
    return workflow_service.update_project_metadata(
        project_id,
        db,
        codigo=body.codigo,
        cliente=body.cliente,
        responsavel=body.responsavel,
        disciplina=body.disciplina,
        status=body.status,
        empresa_id=body.empresa_id,
    )


@router.get("/workflow/companies")
def list_companies(db: Session = Depends(get_db)):
    return workflow_service.list_companies(db)


@router.post("/workflow/companies")
def create_company(body: CompanyCreateRequest, db: Session = Depends(get_db)):
    return workflow_service.create_company(db, nome=body.nome, slug=body.slug)


# --- Fase 3: Wizard de Entrega ---


@router.get("/workflow/nomenclature/standards", response_model=NomenclatureStandardsResponse)
def nomenclature_standards():
    return NomenclatureStandardsResponse(
        pattern="{DISC}-FL{nn}-{TIPO}-{DESC}-{REV}",
        discipline_codes=DISCIPLINE_CODES,
        document_folders=DOCUMENT_FOLDERS,
        sheet_formats=list(SHEET_FORMATS),
    )


@router.get("/workflow/sheet-templates")
def list_sheet_templates(db: Session = Depends(get_db)):
    return wizard_service.list_sheet_templates(db)


@router.get("/workflow/stamps")
def list_stamps(
    empresa_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    return wizard_service.list_stamps(db, empresa_id=empresa_id)


@router.get("/projects/{project_id}/workflow/packages")
def list_delivery_packages(project_id: str, db: Session = Depends(get_db)):
    return wizard_service.list_packages(project_id, db)


@router.post("/projects/{project_id}/workflow/packages")
def create_delivery_package(
    project_id: str,
    body: DeliveryPackageCreateRequest,
    db: Session = Depends(get_db),
):
    try:
        return wizard_service.create_package(project_id, db, titulo=body.titulo)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/projects/{project_id}/workflow/packages/{package_id}")
def get_delivery_package(project_id: str, package_id: str, db: Session = Depends(get_db)):
    try:
        return wizard_service.get_package(project_id, package_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/projects/{project_id}/workflow/packages/{package_id}")
def update_delivery_package(
    project_id: str,
    package_id: str,
    body: DeliveryPackageUpdateRequest,
    db: Session = Depends(get_db),
):
    try:
        return wizard_service.update_package(
            project_id,
            package_id,
            db,
            titulo=body.titulo,
            codigo_emissao=body.codigo_emissao,
            formato_padrao=body.formato_padrao,
            orientacao_padrao=body.orientacao_padrao,
            template_id=body.template_id,
            stamp_id=body.stamp_id,
            observacoes=body.observacoes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/projects/{project_id}/workflow/packages/{package_id}/selection")
def update_delivery_selection(
    project_id: str,
    package_id: str,
    body: DeliverySelectionRequest,
    db: Session = Depends(get_db),
):
    try:
        return wizard_service.update_selection(project_id, package_id, db, file_ids=body.file_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{project_id}/workflow/packages/{package_id}/analyze")
def analyze_delivery_package(project_id: str, package_id: str, db: Session = Depends(get_db)):
    try:
        return wizard_service.analyze_package(project_id, package_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/projects/{project_id}/workflow/packages/{package_id}/norm-gaps.csv")
def export_delivery_norm_gaps_csv(project_id: str, package_id: str, db: Session = Depends(get_db)):
    """CSV de pendências normativas da entrega (disciplinas selecionadas)."""
    from fastapi.responses import Response

    from app.services.knowledge_service import KnowledgeService

    try:
        detail = wizard_service.get_package(project_id, package_id, db)
        gaps = detail.get("norm_gaps") or {}
        filename, content = KnowledgeService().export_project_norm_gaps_csv(gaps)
        return Response(
            content=content.encode("utf-8"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/projects/{project_id}/workflow/packages/{package_id}/items/{item_id}")
def update_delivery_item(
    project_id: str,
    package_id: str,
    item_id: str,
    body: DeliveryItemUpdateRequest,
    db: Session = Depends(get_db),
):
    try:
        return wizard_service.update_item(
            project_id,
            package_id,
            item_id,
            db,
            **body.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/projects/{project_id}/workflow/packages/{package_id}/publish")
def publish_delivery_package(project_id: str, package_id: str, db: Session = Depends(get_db)):
    try:
        return wizard_service.publish_package(project_id, package_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
