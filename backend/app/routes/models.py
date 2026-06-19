from fastapi import APIRouter

from app.schemas.models import ModelsStatusResponse
from app.services.models_status_service import ModelsStatusService

router = APIRouter(tags=["Models"])
models_service = ModelsStatusService()


@router.get("/models/status", response_model=ModelsStatusResponse)
def models_status():
    """Modelos instalados, ativos por módulo e uso recente por request."""
    return ModelsStatusResponse(**models_service.check())
