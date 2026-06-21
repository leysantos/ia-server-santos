from typing import Any, Optional

from pydantic import BaseModel, Field


class ActivityEventItem(BaseModel):
    id: str
    project_id: Optional[str] = None
    source: str
    event_type: str
    title: str
    summary: Optional[str] = None
    agent_name: Optional[str] = None
    discipline: Optional[str] = None
    phase: Optional[str] = None
    meta: Optional[dict[str, Any]] = None
    created_at: Optional[str] = None


class ActivityListResponse(BaseModel):
    total: int
    items: list[ActivityEventItem]


class DecisionItem(BaseModel):
    id: str
    project_id: Optional[str] = None
    source: str
    title: str
    description: Optional[str] = None
    rationale: Optional[str] = None
    disciplines: Optional[list[str]] = None
    meta: Optional[dict[str, Any]] = None
    created_at: Optional[str] = None


class DecisionListResponse(BaseModel):
    total: int
    items: list[DecisionItem]


class ConsoleAgentRunItem(BaseModel):
    id: str
    agent_name: Optional[str] = None
    discipline: Optional[str] = None
    result_text: Optional[str] = None
    had_context: bool = False
    created_at: Optional[str] = None


class ConsoleLogItem(BaseModel):
    id: str
    conversation_id: Optional[str] = None
    project_id: Optional[str] = None
    input_text: str
    disciplines: list[str] = Field(default_factory=list)
    final_report: Optional[str] = None
    synthesis: Optional[dict[str, Any]] = None
    use_rag: bool = True
    agent_count: int = 0
    created_at: Optional[str] = None
    agent_runs: list[ConsoleAgentRunItem] = Field(default_factory=list)


class ConsoleLogsResponse(BaseModel):
    total: int
    items: list[ConsoleLogItem]


class ConsoleStatsResponse(BaseModel):
    orchestrator_logs: int = 0
    agent_runs: int = 0
    activity_events: int = 0
    decisions: int = 0


class OllamaRunningModel(BaseModel):
    name: str
    size_vram_mb: float = 0
    context_length: Optional[int] = None
    expires_at: Optional[str] = None


class RuntimeJobItem(BaseModel):
    id: str
    kind: str
    label: str
    project_id: Optional[str] = None
    model: Optional[str] = None
    phase: Optional[str] = None
    message: Optional[str] = None
    percent: Optional[int] = None
    current: Optional[int] = None
    total: Optional[int] = None
    started_at: Optional[float] = None
    updated_at: Optional[float] = None
    cancel_requested: bool = False
    status: str = "running"
    elapsed_sec: Optional[float] = None
    meta: Optional[dict[str, Any]] = None


class OllamaQueueItem(BaseModel):
    job_id: str
    kind: str
    label: str
    model: Optional[str] = None
    state: str  # on_gpu | running | queued
    position: int = 1
    message: Optional[str] = None
    phase: Optional[str] = None


class OllamaQueueSnapshot(BaseModel):
    depth: int = 0
    waiting_count: int = 0
    on_gpu_count: int = 0
    loaded_slots: int = 0
    items: list[OllamaQueueItem] = Field(default_factory=list)


class OpsLogItem(BaseModel):
    id: str
    ts: float
    source: str
    level: str = "info"
    message: str
    project_id: Optional[str] = None
    job_id: Optional[str] = None
    phase: Optional[str] = None
    meta: Optional[dict[str, Any]] = None
    elapsed_sec: Optional[float] = None


class VramModelSegment(BaseModel):
    name: str
    size_vram_mb: float = 0
    percent_of_total: float = 0


class VramSnapshot(BaseModel):
    available: bool = False
    total_mb: Optional[float] = None
    used_mb: Optional[float] = None
    free_mb: Optional[float] = None
    utilization_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    ollama_allocated_mb: float = 0
    other_mb: Optional[float] = None
    models: list[VramModelSegment] = Field(default_factory=list)


class ConsoleLiveResponse(BaseModel):
    timestamp: Optional[float] = None
    ollama_reachable: bool = False
    ollama_error: Optional[str] = None
    loaded_models: list[OllamaRunningModel] = Field(default_factory=list)
    gpu: Optional[dict[str, Any]] = None
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    active_jobs: list[RuntimeJobItem] = Field(default_factory=list)
    recent_jobs: list[RuntimeJobItem] = Field(default_factory=list)
    active_job_count: int = 0
    loaded_model_count: int = 0
    ollama_queue: Optional[OllamaQueueSnapshot] = None
    ops_logs: list[OpsLogItem] = Field(default_factory=list)
    vram: Optional[VramSnapshot] = None


class UnloadModelRequest(BaseModel):
    model: str


class UnloadResponse(BaseModel):
    ok: bool
    unloaded: list[str] = Field(default_factory=list)
    errors: list[dict[str, str]] = Field(default_factory=list)
    error: Optional[str] = None
