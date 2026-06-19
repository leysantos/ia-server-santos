from typing import Optional

from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    conversation_id: Optional[str] = Field(
        default=None, description="UUID da conversa associada"
    )
    agent_name: str = Field(..., min_length=1, description="Nome do agente avaliado")
    discipline: Optional[str] = Field(default=None, description="Disciplina de engenharia")
    input_text: Optional[str] = Field(default=None, description="Texto original (opcional)")
    response_text: Optional[str] = Field(default=None, description="Resposta avaliada (opcional)")
    rating: Optional[int] = Field(default=None, ge=1, le=5, description="Nota 1–5")
    feedback_text: Optional[str] = Field(default=None, description="Comentário do usuário")
    corrected_answer: Optional[str] = Field(
        default=None, description="Resposta corrigida sugerida pelo usuário"
    )


class FeedbackResponse(BaseModel):
    id: str
    conversation_id: Optional[str] = None
    agent_name: str
    discipline: Optional[str] = None
    input_text: str
    response_text: Optional[str] = None
    rating: Optional[int] = None
    feedback_text: Optional[str] = None
    corrected_answer: Optional[str] = None
    created_at: Optional[str] = None
    saved: bool = True
