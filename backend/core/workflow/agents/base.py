"""Agentes base do workflow."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.orm import Session

from core.workflow.llm.provider import LLMProvider, get_default_llm


class BaseWorkflowAgent(ABC):
    name: str = "base"

    def __init__(self, llm: LLMProvider | None = None) -> None:
        self.llm = llm or get_default_llm()

    @abstractmethod
    def run(self, context: dict[str, Any], db: Session | None = None) -> dict[str, Any]:
        ...
