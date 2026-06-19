from fastapi import APIRouter

from app.schemas import OrchestrateRequest, OrchestrateResponse
from app.services import OrchestratorService

router = APIRouter(prefix="/orchestrate", tags=["Orchestrator"])
orchestrator_service = OrchestratorService()


@router.post("", response_model=OrchestrateResponse)
def orchestrate(request: OrchestrateRequest):
    """
    Execução multidisciplinar via orchestrator v1.
    """
    result = orchestrator_service.process(
        text=request.text,
        use_rag=request.use_rag,
        persist=request.persist,
    )
    return OrchestrateResponse(**result)
