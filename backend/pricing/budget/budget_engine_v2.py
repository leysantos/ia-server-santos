from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pricing.budget.budget_builder import BudgetBuilder, PricingEventCallback
from pricing.budget.budget_session import SESSION_STORE, BudgetSession
from pricing.core.pricing_engine import PricingEngine
from pricing.models.budget_metadata import BudgetProjectMetadata


class BudgetEngineV2:
    """
    Editor de planilha em tempo real:
    gera sessão editável, recálculo automático, export Excel.
    """

    def __init__(
        self,
        engine: PricingEngine | None = None,
        builder: BudgetBuilder | None = None,
    ) -> None:
        self.engine = engine or PricingEngine()
        self.builder = builder or BudgetBuilder(engine=self.engine)

    def generate_session(
        self,
        intent: dict[str, Any],
        source_priority: list[str] | None = None,
        title: str | None = None,
        project: BudgetProjectMetadata | None = None,
        session_id: str | None = None,
        on_pricing_event: PricingEventCallback | None = None,
    ) -> BudgetSession:
        roots = self.builder.build(intent, source_priority, on_pricing_event=on_pricing_event)
        session_title = title or intent.get("title") or intent.get("scope") or "Orçamento"
        proj = project or BudgetProjectMetadata.from_dict(intent.get("project"))
        if intent.get("title"):
            proj.objeto = str(intent["title"])
        return SESSION_STORE.create(
            roots=roots,
            title=str(session_title),
            intent=intent,
            source_priority=source_priority,
            project=proj,
            session_id=session_id,
        )

    def get_session(self, session_id: str) -> BudgetSession | None:
        return SESSION_STORE.get(session_id)

    def update_cell(
        self,
        session_id: str,
        row_id: str,
        field: str,
        value: Any,
        code: str | None = None,
    ) -> BudgetSession:
        return SESSION_STORE.update_cell(session_id, row_id, field, value, code=code)

    def set_obra_type(self, session_id: str, obra_type: str) -> BudgetSession:
        return SESSION_STORE.set_obra_type(session_id, obra_type)

    def update_project(self, session_id: str, fields: dict[str, Any]) -> BudgetSession:
        return SESSION_STORE.update_project(session_id, fields)

    def add_etapa(self, session_id: str, name: str) -> BudgetSession:
        return SESSION_STORE.add_etapa(session_id, name)

    def update_etapa(self, session_id: str, etapa_code: str, name: str) -> BudgetSession:
        return SESSION_STORE.update_etapa(session_id, etapa_code, name)

    def delete_row(self, session_id: str, row_id: str) -> BudgetSession:
        return SESSION_STORE.delete_row(session_id, row_id)

    def compose_etapa(
        self,
        session_id: str,
        etapa_code: str,
        prompt: str,
        source_priority: list[str] | None = None,
        default_quantity: float | None = None,
        replace_existing: bool = False,
    ) -> tuple[BudgetSession, list[dict[str, Any]], int]:
        return SESSION_STORE.compose_etapa(
            session_id,
            etapa_code,
            prompt,
            self.engine,
            source_priority=source_priority,
            default_quantity=default_quantity,
            replace_existing=replace_existing,
        )

    def get_group_compose_prompt(self, session_id: str, group_code: str) -> tuple[str, int]:
        return SESSION_STORE.get_group_compose_prompt(session_id, group_code)

    def replace_service(
        self,
        session_id: str,
        row_id: str,
        price_data: dict[str, Any],
    ) -> BudgetSession:
        return SESSION_STORE.replace_service(session_id, row_id, price_data)

    def apply_group_quantity(
        self,
        session_id: str,
        group_code: str,
        quantity: float,
        *,
        include_subgroups: bool = True,
    ) -> tuple[BudgetSession, int]:
        return SESSION_STORE.apply_group_quantity(
            session_id,
            group_code,
            quantity,
            include_subgroups=include_subgroups,
        )

    def add_subetapa(self, session_id: str, parent_code: str, name: str) -> BudgetSession:
        return SESSION_STORE.add_subetapa(session_id, parent_code, name)

    def update_group(self, session_id: str, group_code: str, name: str) -> BudgetSession:
        return SESSION_STORE.update_group(session_id, group_code, name)

    def generate_memories(
        self,
        session_id: str,
        *,
        group_code: str | None = None,
        use_llm: bool = False,
    ) -> tuple[BudgetSession, list[dict[str, Any]]]:
        llm_client = None
        if use_llm:
            try:
                from config.settings import OLLAMA_BUDGET_TIMEOUT
                from models.ollama_client import OllamaClient

                llm_client = OllamaClient(timeout=OLLAMA_BUDGET_TIMEOUT)
                if not llm_client.ping():
                    llm_client = None
            except Exception:
                llm_client = None
        return SESSION_STORE.generate_memories(
            session_id,
            group_code=group_code,
            use_llm=use_llm and llm_client is not None,
            llm_client=llm_client,
        )

    def add_service(
        self,
        session_id: str,
        etapa_code: str,
        price_data: dict[str, Any],
        quantity: float = 1.0,
    ) -> BudgetSession:
        return SESSION_STORE.add_service(session_id, etapa_code, price_data, quantity=quantity)
