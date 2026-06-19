from fastapi import APIRouter, HTTPException

from app.schemas.aed import AedRequest, AedResponse
from app.services.aed_service import AedService

router = APIRouter(prefix="/aed", tags=["AED"])
aed_service = AedService()


@router.post("", response_model=AedResponse)
def aed_design(request: AedRequest):
    """
    Autonomous Engineering Designer v1.

    Pipeline: understanding → designs → simulation → comparison → selection → report
    """
    try:
        result = aed_service.process(
            text=request.text,
            use_rag=request.use_rag,
            persist=request.persist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return AedResponse(**result)
