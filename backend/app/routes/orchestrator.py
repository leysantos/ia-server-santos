from fastapi import APIRouter, Depends

from app.schemas import OrchestrateRequest, OrchestrateResponse
from app.services import OrchestratorService
from core.auth.dependencies import get_current_user
from core.database.models import User
from core.llm_override import llm_model_scope

router = APIRouter(prefix="/orchestrate", tags=["Orchestrator"])
orchestrator_service = OrchestratorService()


@router.post("", response_model=OrchestrateResponse)
def orchestrate(
    request: OrchestrateRequest,
    user: User | None = Depends(get_current_user),
):
    """
    Execução multidisciplinar via orchestrator v1.
    """
    with llm_model_scope(request.llm_model):
        result = orchestrator_service.process(
            text=request.text,
            use_rag=request.use_rag,
            persist=request.persist,
            user=user,
        )
    return OrchestrateResponse(**result)
