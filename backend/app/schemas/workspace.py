"""Schemas — workspace (projetos, conversas, arquivos)."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)


class ConversationUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    project_id: Optional[str] = Field(default=None, description="UUID do projeto ou null para desvincular")


class ConversationMessageSchema(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    meta: Optional[dict[str, Any]] = None
    created_at: Optional[str] = None


class ConversationSummary(BaseModel):
    id: str
    title: Optional[str] = None
    input_text: str
    mode: str
    message_count: int = 0
    project_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ConversationDetail(ConversationSummary):
    messages: list[ConversationMessageSchema] = Field(default_factory=list)
    orchestrator_logs: list[dict[str, Any]] = Field(default_factory=list)
    agent_runs: list[dict[str, Any]] = Field(default_factory=list)


class ConversationListResponse(BaseModel):
    total: int
    items: list[ConversationSummary]


class ProjectFileSchema(BaseModel):
    id: str
    project_id: str
    filename: str
    storage_path: str
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    created_at: Optional[str] = None


class ProjectSummary(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    conversation_count: int = 0
    file_count: int = 0


class ProjectDetail(ProjectSummary):
    conversations: list[ConversationSummary] = Field(default_factory=list)
    files: list[ProjectFileSchema] = Field(default_factory=list)


class ProjectListResponse(BaseModel):
    total: int
    items: list[ProjectSummary]


class WorkspaceSearchResponse(BaseModel):
    query: str
    total: int
    projects: list[ProjectSummary] = Field(default_factory=list)
    conversations: list[ConversationSummary] = Field(default_factory=list)
