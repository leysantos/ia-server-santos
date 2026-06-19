from typing import Any, Optional

from pydantic import BaseModel, Field


class ModelsStatusResponse(BaseModel):
    router_enabled: bool
    evaluation_enabled: bool = False
    model_map: dict[str, str] = Field(default_factory=dict)
    learned_overrides: dict[str, str] = Field(default_factory=dict)
    performance_profiles: list[dict[str, Any]] = Field(default_factory=list)
    installed_models: list[str] = Field(default_factory=list)
    active_by_module: dict[str, str] = Field(default_factory=dict)
    recent_requests: list[dict[str, Any]] = Field(default_factory=list)
    legacy_models: dict[str, str] = Field(default_factory=dict)
    ollama: str = "unknown"
