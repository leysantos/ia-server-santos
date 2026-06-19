from typing import Any, Optional

from pydantic import BaseModel, Field


class OrchestrateRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Problema multidisciplinar de engenharia")
    use_rag: bool = Field(default=True, description="Ativar contexto RAG v2 por disciplina")
    persist: bool = Field(default=True, description="Persistir conversa e logs no PostgreSQL")
    llm_model: Optional[str] = Field(
        default=None,
        description='Modelo Ollama. Use "auto" ou omita para roteamento automático.',
    )


class OrchestrateResponse(BaseModel):
    input: str
    disciplines: list[str]
    results: dict[str, Any]
    final_report: str
    synthesis: dict[str, Any]
    context_graph: dict[str, Any] = Field(default_factory=dict)
    conversation_id: Optional[str] = None
    orchestrator_log_id: Optional[str] = None
