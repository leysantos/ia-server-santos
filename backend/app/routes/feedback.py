import logging

from fastapi import APIRouter, HTTPException

from app.schemas.feedback import FeedbackRequest, FeedbackResponse
from core.learning.feedback_service import save_feedback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["Learning Loop"])


@router.post("", response_model=FeedbackResponse)
def submit_feedback(request: FeedbackRequest):
    """
    Feedback explícito do usuário (fire-and-forget).

    Falha de DB retorna 200 com saved=false — não bloqueia o fluxo principal.
    """
    try:
        result = save_feedback(
            conversation_id=request.conversation_id,
            agent_name=request.agent_name,
            discipline=request.discipline,
            input_text=request.input_text,
            response_text=request.response_text,
            rating=request.rating,
            feedback_text=request.feedback_text,
            corrected_answer=request.corrected_answer,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not result:
        logger.warning(
            "Feedback não persistido agent=%s conversation=%s",
            request.agent_name,
            request.conversation_id,
        )
        return FeedbackResponse(
            id="",
            agent_name=request.agent_name,
            discipline=request.discipline,
            input_text=request.input_text or "",
            response_text=request.response_text,
            rating=request.rating,
            feedback_text=request.feedback_text,
            corrected_answer=request.corrected_answer,
            saved=False,
        )

    return FeedbackResponse(**result, saved=True)
