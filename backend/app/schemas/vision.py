"""Schemas REST — Vision Analysis Engine."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class VisionModeItem(BaseModel):
    value: str
    label: str


class VisionStatusResponse(BaseModel):
    available: bool
    ollama_reachable: bool = False
    vision_models_ready: list[str] = Field(default_factory=list)
    primary: str = ""
    technical_model: str = "qwen3:14b"
    error: Optional[str] = None


class VisionAnalyzeRequest(BaseModel):
    file_ids: list[str] = Field(default_factory=list, description="Vazio = todas as imagens/PDFs do projeto")
    mode: str = Field(
        default="obra",
        description="obra|laudo|relatorio_fotografico|planta|pci|estrutural",
    )
    extra_context: str = ""
    skip_technical: bool = Field(
        default=False,
        description="Análise rápida: OCR + Gemma3 Vision apenas (pula relatório Qwen3)",
    )


class VisionAnalysisItem(BaseModel):
    project_file_id: str
    filename: str
    analysis_mode: str
    analyzer: Optional[str] = None
    skipped: bool = False
    error: Optional[str] = None
    model_used: Optional[str] = None
    technical_model_used: Optional[str] = None
    analyzed_at: Optional[str] = None
    analysis: Optional[dict[str, Any]] = None
    technical_report: Optional[dict[str, Any]] = None
    rag_sources: list[dict[str, Any]] = Field(default_factory=list)
    normative_context: Optional[dict[str, Any]] = None


class PciChecklistResponse(BaseModel):
    project_id: str
    modo: str = "pci"
    total_itens: int = 0
    conformes: int = 0
    parciais: int = 0
    pendentes: int = 0
    nao_aplicaveis: int = 0
    score_percent: float = 0.0
    pronto_cbmam: bool = False
    arquivos_analisados: int = 0
    rag_audit: dict[str, Any] = Field(default_factory=dict)
    itens: list[dict[str, Any]] = Field(default_factory=list)


class VisionAnalyzeResponse(BaseModel):
    project_id: str
    mode: str
    total: int
    analyzed: int
    errors: int
    skipped: int
    items: list[VisionAnalysisItem]
    summary: dict[str, Any] = Field(default_factory=dict)
    pci_checklist: Optional[PciChecklistResponse] = None


class VisionReportRequest(BaseModel):
    report_type: str = Field(
        ...,
        description=(
            "relatorio_fotografico|laudo|correcoes|tecnico|review|nc|parecer|memorial|tdr"
        ),
    )
    file_ids: list[str] = Field(default_factory=list)
    obra_info: str = ""
    solicitante: str = ""
    objeto: str = ""
    discipline: str = ""
    prazo: str = ""


class VisionAnalysisListResponse(BaseModel):
    total: int
    items: list[VisionAnalysisItem]


class WorkspaceToolItem(BaseModel):
    id: str
    label: str
    available: bool
    supports: list[str] = Field(default_factory=list)


class WorkspaceReportItem(BaseModel):
    id: str
    label: str
    route: str


class VisionWorkspaceStatusResponse(BaseModel):
    ready: bool
    ollama_reachable: bool
    vision_model: str
    vision_model_ready: bool
    technical_model: str
    technical_model_ready: bool
    installed_models: list[str] = Field(default_factory=list)
    analyzers: list[WorkspaceToolItem] = Field(default_factory=list)
    reports: list[WorkspaceReportItem] = Field(default_factory=list)
    dependencies: dict[str, bool] = Field(default_factory=dict)
    pipeline: list[str] = Field(default_factory=list)
    frontend_routes: list[str] = Field(default_factory=list)
