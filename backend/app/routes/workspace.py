from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.schemas.workspace import (
    ConversationDetail,
    ConversationListResponse,
    ConversationSummary,
    ConversationUpdateRequest,
    ProjectCreateRequest,
    ProjectDetail,
    ProjectListResponse,
    ProjectSummary,
    ProjectUpdateRequest,
    WorkspaceSearchResponse,
)
from app.services.workspace_service import WorkspaceService
from core.auth.dependencies import get_current_user
from core.database import get_db
from core.database.models import User

router = APIRouter(tags=["Workspace"])
workspace_service = WorkspaceService()


@router.get("/workspace/search", response_model=WorkspaceSearchResponse)
def search_workspace(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    return WorkspaceSearchResponse(**workspace_service.search(q, limit=limit, db=db, user=user))


@router.get("/projects/formats")
def project_supported_formats():
    from core.project_rag.project_file_extractors import PROJECT_UPLOAD_ACCEPT
    from core.project_rag.project_rag import supported_formats

    return {"formats": supported_formats(), "accept": PROJECT_UPLOAD_ACCEPT}


@router.get("/projects", response_model=ProjectListResponse)
def list_projects(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return ProjectListResponse(**workspace_service.list_projects(limit=limit, db=db))


@router.post("/projects", response_model=ProjectSummary)
def create_project(
    body: ProjectCreateRequest,
    db: Session = Depends(get_db),
):
    return ProjectSummary(**workspace_service.create_project(body.name, body.description, db=db))


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    return ProjectDetail(**workspace_service.get_project(project_id, db=db, user=user))


@router.patch("/projects/{project_id}", response_model=ProjectSummary)
def update_project(
    project_id: str,
    body: ProjectUpdateRequest,
    db: Session = Depends(get_db),
):
    return ProjectSummary(
        **workspace_service.update_project(
            project_id,
            name=body.name,
            description=body.description,
            db=db,
        )
    )


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db)):
    return workspace_service.delete_project(project_id, db=db)


@router.post("/projects/{project_id}/files")
async def upload_project_files(
    project_id: str,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    return await workspace_service.upload_project_files(project_id, files, db=db)


@router.post("/projects/{project_id}/reindex")
def reindex_project_files(project_id: str, db: Session = Depends(get_db)):
    return workspace_service.reindex_project(project_id, db=db)


@router.get("/projects/{project_id}/files/{file_id}/preview")
def preview_project_file(
    project_id: str,
    file_id: str,
    db: Session = Depends(get_db),
):
    """Preview de imagem ou 1ª página de PDF (para UI de análise visual)."""
    content, media_type, filename = workspace_service.get_file_preview(
        project_id, file_id, db=db
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Cache-Control": "private, max-age=3600",
            "Content-Disposition": f'inline; filename="{filename}"',
        },
    )


@router.delete("/projects/{project_id}/files/{file_id}")
def delete_project_file(
    project_id: str,
    file_id: str,
    db: Session = Depends(get_db),
):
    return workspace_service.delete_project_file(project_id, file_id, db=db)


@router.get("/conversations", response_model=ConversationListResponse)
def list_conversations(
    limit: int = Query(default=50, ge=1, le=200),
    project_id: Optional[str] = Query(default=None),
    unassigned_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    return ConversationListResponse(
        **workspace_service.list_conversations(
            limit=limit,
            project_id=project_id,
            unassigned_only=unassigned_only,
            db=db,
            user=user,
        )
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    return ConversationDetail(
        **workspace_service.get_conversation(conversation_id, db=db, user=user)
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationSummary)
def update_conversation(
    conversation_id: str,
    body: ConversationUpdateRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    unset = "project_id" in body.model_fields_set
    return ConversationSummary(
        **workspace_service.update_conversation(
            conversation_id,
            title=body.title,
            project_id=body.project_id,
            update_project=unset,
            db=db,
            user=user,
        )
    )


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    return workspace_service.delete_conversation(conversation_id, db=db, user=user)


@router.get("/projects/{project_id}/activity")
def project_activity(
    project_id: str,
    limit: int = Query(default=100, ge=1, le=300),
    db: Session = Depends(get_db),
):
    from app.schemas.activity import ActivityListResponse
    from core.project_memory.service import list_project_activity

    items = list_project_activity(db, project_id, limit=limit)
    return ActivityListResponse(total=len(items), items=items)


@router.get("/projects/{project_id}/decisions")
def project_decisions(
    project_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    from app.schemas.activity import DecisionListResponse
    from core.project_memory.service import list_project_decisions

    items = list_project_decisions(db, project_id, limit=limit)
    return DecisionListResponse(total=len(items), items=items)
