from typing import Any, Optional

from pydantic import BaseModel, Field


class CopilotRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Solicitação de engenharia civil")
    use_rag: bool = Field(default=True, description="Ativar RAG v2 por disciplina via dispatcher")
    persist: bool = Field(default=False, description="Persistir execuções no PostgreSQL")


class CopilotEvaluation(BaseModel):
    score: float = Field(..., ge=0.0, le=1.0)
    grade: str
    factors: dict[str, float] = Field(default_factory=dict)
    completed_steps: int = 0
    total_steps: int = 0
    error_steps: int = 0
    recommendations: list[str] = Field(default_factory=list)


class EvaluationLoopV2(BaseModel):
    intent_accuracy: float = Field(..., ge=0.0, le=1.0)
    plan_quality: float = Field(..., ge=0.0, le=1.0)
    execution_completeness: float = Field(..., ge=0.0, le=1.0)
    response_quality: float = Field(..., ge=0.0, le=1.0)
    final_score: float = Field(..., ge=0.0, le=1.0)
    grade: str
    issues: list[str] = Field(default_factory=list)
    stages: list[dict[str, Any]] = Field(default_factory=list)
    saved: bool = False


class CopilotResponse(BaseModel):
    input: str
    intent: str
    intent_confidence: float
    matched_categories: list[str] = Field(default_factory=list)
    plan: list[dict[str, Any]]
    disciplines: list[str]
    result: dict[str, Any]
    evaluation: CopilotEvaluation
    evaluation_v2: Optional[EvaluationLoopV2] = None
    context_graph: dict[str, Any] = Field(default_factory=dict)
    conversation_id: Optional[str] = None
