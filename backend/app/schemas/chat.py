from typing import Any, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Mensagem ou problema de engenharia")
    use_rag: bool = Field(default=True, description="Ativar contexto RAG v2")
    persist: bool = Field(default=True, description="Persistir execução no PostgreSQL")
    conversation_id: Optional[str] = Field(
        default=None,
        description="UUID de conversa existente — continua o thread multi-turn",
    )
    project_id: Optional[str] = Field(
        default=None,
        description="UUID do projeto — vincula nova conversa ou move conversa",
    )
    llm_model: Optional[str] = Field(
        default=None,
        description='Modelo Ollama (ex.: qwen3:14b). Use "auto" ou omita para roteamento automático.',
    )


class ChatResponse(BaseModel):
    input: str
    discipline: Optional[str] = None
    agent: Optional[str] = None
    result: Optional[str] = None
    response: Optional[str] = None
    extra: Optional[dict[str, Any]] = None
    conversation_id: Optional[str] = None
    route: Optional[dict[str, Any]] = None
    intent: Optional[dict[str, Any]] = None
    segments: Optional[list[dict[str, Any]]] = None
    error: Optional[bool] = None
