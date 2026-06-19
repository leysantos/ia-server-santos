from typing import Any, Optional

from pydantic import BaseModel, Field


class AedRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Problema de engenharia para análise AED")
    use_rag: bool = Field(default=True, description="Usar RAG v2 na simulação normativa")
    persist: bool = Field(default=False, description="Persistir execução em aed_runs")


class AedResponse(BaseModel):
    input: str
    conversation_id: Optional[str] = None
    understanding: dict[str, Any]
    structural_selection: Optional[dict[str, Any]] = None
    designs: list[dict[str, Any]]
    simulations: list[dict[str, Any]]
    comparison: dict[str, Any]
    selection: dict[str, Any]
    report: dict[str, Any]
    use_rag: bool = True
    aed_run_id: Optional[str] = None
