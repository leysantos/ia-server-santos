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
