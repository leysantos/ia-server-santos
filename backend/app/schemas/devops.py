"""Schemas da API de serviços locais e console shell."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ServiceStatus = Literal["running", "stopped", "unknown"]


class DevServiceItem(BaseModel):
    id: str
    label: str
    description: str
    group: str
    port: int | None = None
    managed: bool = True
    status: ServiceStatus
    detail: str = ""
    pid: int | None = None
    log_file: str | None = None
    can_start: bool = False
    can_stop: bool = False


class DevServicesResponse(BaseModel):
    services: list[DevServiceItem]
    repo_root: str
    hints: dict[str, str] = Field(default_factory=dict)


class DevServiceActionResponse(BaseModel):
    id: str
    status: str
    message: str = ""
    pid: int | None = None
    log_file: str | None = None
    services: list[DevServiceItem] = Field(default_factory=list)


class DevStackStartResponse(BaseModel):
    results: list[dict[str, Any]]
    services: list[DevServiceItem]


class ShellRunRequest(BaseModel):
    command: str = Field(..., min_length=1, max_length=4000)
    cwd: str | None = None
    timeout_sec: int = Field(default=120, ge=1, le=300)


class ShellRunResponse(BaseModel):
    ts: str
    command: str
    cwd: str
    exit_code: int
    output: str
    success: bool
    truncated: bool = False


class ShellHistoryResponse(BaseModel):
    items: list[dict[str, Any]]
