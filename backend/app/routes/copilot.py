from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.schemas.copilot import CopilotRequest, CopilotResponse
from app.services.copilot_service import CopilotService
from core.evaluation_v2.evaluation_engine import evaluate
from core.evaluation_v2.evaluation_logger import save_evaluation

router = APIRouter(prefix="/copilot", tags=["Copilot"])
copilot_service = CopilotService()


def _save_evaluation_background(evaluation: dict) -> None:
    try:
        save_evaluation(evaluation)
    except Exception:
        pass


def _run_self_improving_background(copilot_output: dict, evaluation: dict) -> None:
    try:
        from core.self_improving.system_insights import run_self_improving_loop
        run_self_improving_loop(copilot_output, evaluation)
    except Exception:
        pass


@router.post("", response_model=CopilotResponse)
def copilot(request: CopilotRequest, background_tasks: BackgroundTasks):
    """
    Copilot v1 — planeja, executa multi-agente, sintetiza e avalia qualidade.

    Pipeline: input → intent → plan → execute → synthesize → evaluate
    Evaluation Loop v2: scores na resposta; persistência PostgreSQL em background.
    """
    try:
        result = copilot_service.process(
            text=request.text,
            use_rag=request.use_rag,
            persist=request.persist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        evaluation_v2 = evaluate(result)
        evaluation_v2["saved"] = False
        result["evaluation_v2"] = evaluation_v2
        background_tasks.add_task(_save_evaluation_background, evaluation_v2)
        background_tasks.add_task(_run_self_improving_background, result, evaluation_v2)
    except Exception:
        pass

    return CopilotResponse(**result)
