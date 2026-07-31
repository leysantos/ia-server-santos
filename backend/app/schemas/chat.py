from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    text: str = Field(default="", description="Mensagem ou problema de engenharia")
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
    attachment_ids: Optional[list[str]] = Field(
        default=None,
        description="IDs de anexos preparados via POST /chat/attachments",
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


class ChatExportRequest(BaseModel):
    text: str = Field(..., min_length=40, description="Texto da resposta do assistente")
    kind: Literal[
        "memoria",
        "trd",
        "memorial",
        "parecer",
        "especificacao",
        "checklist",
        "nota_orcamento",
        "resposta",
    ] = Field(
        default="memoria",
        description="Tipo de documento a gerar a partir da resposta",
    )
    format: Literal["pdf", "docx"] = Field(default="pdf")
    title: Optional[str] = None
    discipline: Optional[str] = None
    source_question: Optional[str] = Field(
        default=None,
        description="Pergunta do usuário que originou a resposta",
    )


class ChatSuggestDocumentsRequest(BaseModel):
    text: str = Field(..., min_length=40)
    discipline: Optional[str] = None
    source_question: Optional[str] = None
    route_mode: Optional[str] = None


class ChatCroquiRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=40,
        description="Texto técnico da resposta (base para o croqui)",
    )
    source_question: Optional[str] = None
    llm_model: Optional[str] = Field(
        default=None,
        description="Modelo Gemini selecionado no chat (informativo)",
    )
