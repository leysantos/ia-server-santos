from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pricing.budget.budget_calculator import BudgetCalculator
from pricing.budget.budget_excel import export_budget_xlsx
from pricing.budget.ppd_exporter import export_ppd_xlsx
from pricing.models.budget_item import BudgetItem
from pricing.models.budget_metadata import BudgetProjectMetadata
from pricing.schedule.schedule_models import ProjectSchedule


def _deserialize_item(data: dict[str, Any]) -> BudgetItem:
    from pricing.models.budget_item import BudgetItemType

    children = [_deserialize_item(c) for c in data.get("children") or []]
    return BudgetItem(
        code=data["code"],
        name=data["name"],
        row_id=str(data.get("row_id") or uuid.uuid4().hex[:12]),
        level=data["level"],
        quantity=float(data.get("quantity") or 0),
        unit=str(data.get("unit") or ""),
        unit_cost=float(data.get("unit_cost") or 0),
        unit_cost_semd=float(data.get("unit_cost_semd") or 0),
        unit_price=float(data.get("unit_price") or 0),
        unit_price_semd=float(data.get("unit_price_semd") or 0),
        total_price=float(data.get("total_price") or 0),
        total_price_semd=float(data.get("total_price_semd") or 0),
        source_base=str(data.get("source_base") or ""),
        source_code=str(data.get("source_code") or ""),
        parent_code=data.get("parent_code"),
        item_type=BudgetItemType(data.get("item_type", "composition")),
        row_type=str(data.get("row_type") or ""),
        bdi_rate=float(data.get("bdi_rate") or 0.2426),
        bdi_label=str(data.get("bdi_label") or "BDI1"),
        calculation_note=str(data.get("calculation_note") or ""),
        children=children,
        metadata=dict(data.get("metadata") or {}),
        pricing_query=data.get("pricing_query"),
    )


@dataclass
class BudgetSession:
    id: str
    title: str
    roots: list[BudgetItem]
    source_priority: list[str] = field(default_factory=list)
    intent: dict[str, Any] = field(default_factory=dict)
    project: BudgetProjectMetadata = field(default_factory=BudgetProjectMetadata)
    calculation_memory: list[dict[str, Any]] = field(default_factory=list)
    schedule: ProjectSchedule | None = None
    tech_spec: dict[str, Any] | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def grand_total(self) -> float:
        """Total efetivo — menor custo ComD/SemD por linha (administração pública)."""
        return round(sum(r.effective_total() for r in self.roots), 2)

    @property
    def grand_total_comd(self) -> float:
        return round(sum(r.total_price for r in self.roots), 2)

    @property
    def grand_total_semd(self) -> float:
        return round(sum(r.total_price_semd for r in self.roots), 2)

    @property
    def desoneracao_mode(self) -> str:
        comd = self.grand_total_comd
        semd = self.grand_total_semd
        if semd > 0 and semd < comd:
            return "semd"
        return "comd"

    def to_dict(self) -> dict[str, Any]:
        calc = BudgetCalculator()
        rows: list[dict[str, Any]] = []
        for root in self.roots:
            rows.extend(calc.flatten_rows(root))
        return {
            "session_id": self.id,
            "title": self.title,
            "items": [r.to_dict() for r in self.roots],
            "rows": rows,
            "grand_total": self.grand_total,
            "grand_total_comd": self.grand_total_comd,
            "grand_total_semd": self.grand_total_semd,
            "desoneracao_mode": self.desoneracao_mode,
            "currency": "BRL",
            "project": self.project.to_dict(),
            "calculation_memory": self.calculation_memory,
            "schedule": self.schedule.to_dict() if self.schedule else None,
            "tech_spec": self.tech_spec,
            "source_priority": self.source_priority,
            "intent": self.intent,
            "template": self.project.template,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def export_xlsx(self, format: str = "ppd") -> bytes:
        if format == "ppd" or self.project.template == "PPD_MC_OR":
            return export_ppd_xlsx(self.roots, self.project)
        return export_budget_xlsx(
            self.roots,
            title=self.title,
            metadata={
                "session_id": self.id,
                "grand_total": self.grand_total,
                "source_priority": self.source_priority,
            },
        )


class BudgetSessionStore:
    """Store em memória de sessões editáveis (Budget Engine v2)."""

    def __init__(self) -> None:
        self._sessions: dict[str, BudgetSession] = {}

    def create(
        self,
        roots: list[BudgetItem],
        title: str,
        intent: dict[str, Any],
        source_priority: list[str] | None = None,
        project: BudgetProjectMetadata | None = None,
        session_id: str | None = None,
    ) -> BudgetSession:
        sid = session_id or str(uuid.uuid4())
        calc = BudgetCalculator()
        memory: list[dict[str, Any]] = []
        for root in roots:
            memory.extend(calc.build_calculation_memory(root))

        proj = project or BudgetProjectMetadata.from_dict(intent.get("project"))
        if not proj.projeto:
            proj.projeto = title

        existing = self._sessions.get(sid)
        if existing:
            existing.roots = roots
            existing.title = title
            existing.intent = intent
            existing.source_priority = source_priority or []
            existing.project = proj
            existing.calculation_memory = memory
            existing.updated_at = datetime.now(timezone.utc).isoformat()
            return existing

        session = BudgetSession(
            id=sid,
            title=title,
            roots=roots,
            source_priority=source_priority or [],
            intent=intent,
            project=proj,
            calculation_memory=memory,
        )
        self._sessions[sid] = session
        return session

    def get(self, session_id: str) -> BudgetSession | None:
        return self._sessions.get(session_id)

    def update_cell(
        self,
        session_id: str,
        row_id: str,
        field: str,
        value: Any,
        code: str | None = None,
    ) -> BudgetSession:
        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(f"Sessão não encontrada: {session_id}")

        calc = BudgetCalculator()
        edit_memory: list[dict[str, Any]] = []
        for root in session.roots:
            _, mem = calc.apply_cell_edit(root, row_id, field, value, code=code)
            edit_memory.extend(mem)

        session.calculation_memory = edit_memory
        session.updated_at = datetime.now(timezone.utc).isoformat()
        return session

    def set_obra_type(self, session_id: str, obra_type: str) -> BudgetSession:
        from pricing.budget.bdi_calculator import BdiCalculator

        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(f"Sessão não encontrada: {session_id}")

        session.project.set_obra_type(obra_type)
        bdi_calc = BdiCalculator(session.project.bdi)
        for root in session.roots:
            bdi_calc.apply_tree(root)
            root.recompute_total()

        session.calculation_memory = [
            {
                "step": "bdi_obra_type_change",
                "obra_type": session.project.obra_type,
                "obra_label": session.project.bdi.obra_label,
                "rate_comd": session.project.bdi.rate_com_desoneracao,
                "rate_semd": session.project.bdi.rate_sem_desoneracao,
                "grand_total": session.grand_total,
            }
        ]
        session.updated_at = datetime.now(timezone.utc).isoformat()
        return session

    def update_project(
        self,
        session_id: str,
        fields: dict[str, Any],
    ) -> BudgetSession:
        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(f"Sessão não encontrada: {session_id}")

        mapping = {
            "projeto": "projeto",
            "nome_obra": "projeto",
            "objeto": "objeto",
            "local": "local",
            "endereco": "local",
            "empresa": "empresa",
            "orgao": "orgao",
            "responsavel_tecnico": "responsavel_tecnico",
            "base_preco": "base_preco",
            "orcamento": "orcamento",
            "data_ref": "data_ref",
            "processo": "processo",
        }
        for key, attr in mapping.items():
            if key in fields and fields[key] is not None:
                setattr(session.project, attr, str(fields[key]).strip())

        if "price_bases" in fields and fields["price_bases"] is not None:
            from pricing.budget.price_base_session import apply_price_bases_selection

            selections = list(fields["price_bases"])
            session.project.price_bases = selections
            if selections:
                applied = apply_price_bases_selection(selections)
                session.project.base_preco = str(applied.get("base_preco") or session.project.base_preco)
                session.source_priority = list(applied.get("source_priority") or session.source_priority)

        if fields.get("projeto") or fields.get("nome_obra"):
            session.title = str(fields.get("projeto") or fields.get("nome_obra")).strip()
        session.updated_at = datetime.now(timezone.utc).isoformat()
        return session

    def add_etapa(self, session_id: str, name: str) -> BudgetSession:
        from pricing.budget.budget_structure import add_etapa, refresh_calculation_memory

        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(f"Sessão não encontrada: {session_id}")
        add_etapa(session.roots, name, session.project)
        session.calculation_memory = refresh_calculation_memory(session.roots)
        session.updated_at = datetime.now(timezone.utc).isoformat()
        return session

    def update_group(self, session_id: str, group_code: str, name: str) -> BudgetSession:
        from pricing.budget.budget_structure import find_group, refresh_calculation_memory, update_group_name

        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(f"Sessão não encontrada: {session_id}")
        group = find_group(session.roots, group_code)
        if not group:
            raise ValueError(f"Grupo não encontrado: {group_code}")
        update_group_name(group, name)
        session.calculation_memory = refresh_calculation_memory(session.roots)
        session.updated_at = datetime.now(timezone.utc).isoformat()
        return session

    def update_etapa(self, session_id: str, etapa_code: str, name: str) -> BudgetSession:
        return self.update_group(session_id, etapa_code, name)

    def add_subetapa(self, session_id: str, parent_code: str, name: str) -> BudgetSession:
        from pricing.budget.budget_structure import add_subetapa, refresh_calculation_memory

        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(f"Sessão não encontrada: {session_id}")
        add_subetapa(session.roots, parent_code, name, session.project)
        session.calculation_memory = refresh_calculation_memory(session.roots)
        session.updated_at = datetime.now(timezone.utc).isoformat()
        return session

    def _apply_wbs_renumber(self, session: BudgetSession) -> dict[str, str]:
        from pricing.budget.budget_calculator import BudgetCalculator
        from pricing.budget.budget_structure import renumber_wbs, refresh_calculation_memory
        from pricing.schedule.schedule_builder import sync_schedule_from_budget

        mapping = renumber_wbs(session.roots)
        session.calculation_memory = refresh_calculation_memory(session.roots)
        if session.schedule and mapping:
            calc = BudgetCalculator()
            rows: list[dict[str, Any]] = []
            for root in session.roots:
                rows.extend(calc.flatten_rows(root))
            session.schedule = sync_schedule_from_budget(
                rows,
                existing=session.schedule,
                project_start=session.schedule.project_start,
            )
        return mapping

    def delete_row(self, session_id: str, row_id: str) -> BudgetSession:
        from pricing.budget.budget_structure import delete_item

        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(f"Sessão não encontrada: {session_id}")
        if not delete_item(session.roots, row_id):
            raise ValueError(f"Linha não encontrada: {row_id}")
        self._apply_wbs_renumber(session)
        session.updated_at = datetime.now(timezone.utc).isoformat()
        return session

    def renumber_itemization(self, session_id: str) -> tuple[BudgetSession, dict[str, str]]:
        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(f"Sessão não encontrada: {session_id}")
        mapping = self._apply_wbs_renumber(session)
        session.updated_at = datetime.now(timezone.utc).isoformat()
        return session, mapping

    def compose_etapa(
        self,
        session_id: str,
        etapa_code: str,
        prompt: str,
        engine: Any,
        source_priority: list[str] | None = None,
        default_quantity: float | None = None,
        replace_existing: bool = False,
    ) -> tuple[BudgetSession, list[dict[str, Any]], int]:
        from pricing.budget.budget_structure import (
            compose_group_from_prompt,
            find_group,
            recompose_group_from_prompt,
            refresh_calculation_memory,
        )

        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(f"Sessão não encontrada: {session_id}")
        group = find_group(session.roots, etapa_code)
        if not group:
            raise ValueError(f"Grupo não encontrado: {etapa_code}")
        removed = 0
        if replace_existing:
            _, log, removed = recompose_group_from_prompt(
                group,
                prompt,
                engine,
                session.project,
                source_priority=source_priority,
                default_quantity=default_quantity,
            )
        else:
            _, log = compose_group_from_prompt(
                group,
                prompt,
                engine,
                session.project,
                source_priority=source_priority,
                default_quantity=default_quantity,
            )
        session.calculation_memory = refresh_calculation_memory(session.roots)
        session.updated_at = datetime.now(timezone.utc).isoformat()
        return session, log, removed

    def get_group_compose_prompt(self, session_id: str, group_code: str) -> tuple[str, int]:
        from pricing.budget.budget_structure import find_group, group_services_to_prompt
        from pricing.budget.ppd_layout import ROW_TYPE_SERVICO

        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(f"Sessão não encontrada: {session_id}")
        group = find_group(session.roots, group_code)
        if not group:
            raise ValueError(f"Grupo não encontrado: {group_code}")
        services = [c for c in group.children if c.row_type == ROW_TYPE_SERVICO]
        return group_services_to_prompt(group), len(services)

    def replace_service(
        self,
        session_id: str,
        row_id: str,
        price_data: dict[str, Any],
    ) -> BudgetSession:
        from pricing.budget.budget_structure import (
            refresh_calculation_memory,
            replace_service_from_price,
        )
        from pricing.models.price_item import PriceItem

        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(f"Sessão não encontrada: {session_id}")
        price = PriceItem(
            code=str(price_data.get("code") or ""),
            description=str(price_data.get("description") or price_data.get("name") or ""),
            unit=str(price_data.get("unit") or ""),
            price=float(price_data.get("price") or 0),
            source=str(price_data.get("source") or "sinapi"),
            metadata=price_data.get("metadata") or {},
        )
        replace_service_from_price(
            session.roots,
            row_id,
            price,
            session.project,
            unit_hint=price_data.get("unit_hint"),
            pricing_query=str(price_data.get("pricing_query") or price_data.get("query") or ""),
        )
        session.calculation_memory = refresh_calculation_memory(session.roots)
        session.updated_at = datetime.now(timezone.utc).isoformat()
        return session

    def apply_group_quantity(
        self,
        session_id: str,
        group_code: str,
        quantity: float,
        *,
        include_subgroups: bool = True,
    ) -> tuple[BudgetSession, int]:
        from pricing.budget.budget_structure import (
            apply_quantity_to_group,
            find_group,
            refresh_calculation_memory,
        )

        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(f"Sessão não encontrada: {session_id}")
        group = find_group(session.roots, group_code)
        if not group:
            raise ValueError(f"Grupo não encontrado: {group_code}")
        count = apply_quantity_to_group(
            group,
            quantity,
            session.project,
            include_subgroups=include_subgroups,
        )
        for root in session.roots:
            root.recompute_total()
        session.calculation_memory = refresh_calculation_memory(session.roots)
        session.updated_at = datetime.now(timezone.utc).isoformat()
        return session, count

    def add_service(
        self,
        session_id: str,
        etapa_code: str,
        price_data: dict[str, Any],
        quantity: float = 1.0,
    ) -> BudgetSession:
        from pricing.budget.budget_structure import (
            add_service_to_group,
            find_group,
            refresh_calculation_memory,
        )
        from pricing.models.price_item import PriceItem

        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(f"Sessão não encontrada: {session_id}")
        group = find_group(session.roots, etapa_code)
        if not group:
            raise ValueError(f"Grupo não encontrado: {etapa_code}")
        price = PriceItem(
            code=str(price_data.get("code") or ""),
            description=str(price_data.get("description") or price_data.get("name") or ""),
            unit=str(price_data.get("unit") or ""),
            price=float(price_data.get("price") or 0),
            source=str(price_data.get("source") or "sinapi"),
            region=price_data.get("region"),
            metadata=dict(price_data.get("metadata") or {}),
        )
        unit_hint = str(price_data.get("unit_hint") or "").strip() or None
        add_service_to_group(
            group,
            price,
            session.project,
            quantity=quantity,
            unit_hint=unit_hint,
        )
        session.calculation_memory = refresh_calculation_memory(session.roots)
        session.updated_at = datetime.now(timezone.utc).isoformat()
        return session

    def generate_memories(
        self,
        session_id: str,
        *,
        group_code: str | None = None,
        use_llm: bool = False,
        llm_client: Any = None,
    ) -> tuple[BudgetSession, list[dict[str, Any]]]:
        from pricing.budget.budget_structure import refresh_calculation_memory
        from pricing.budget.memory_generator import generate_memories_for_session

        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(f"Sessão não encontrada: {session_id}")
        obra = session.project.projeto or session.title
        log = generate_memories_for_session(
            session.roots,
            group_code=group_code,
            use_llm=use_llm,
            llm_client=llm_client,
            obra_context=obra,
        )
        session.calculation_memory = refresh_calculation_memory(session.roots)
        session.updated_at = datetime.now(timezone.utc).isoformat()
        return session, log

    def sync_schedule(self, session_id: str) -> BudgetSession:
        from pricing.schedule.schedule_builder import sync_schedule_from_budget

        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(f"Sessão não encontrada: {session_id}")
        calc = BudgetCalculator()
        rows: list[dict[str, Any]] = []
        for root in session.roots:
            rows.extend(calc.flatten_rows(root))
        session.schedule = sync_schedule_from_budget(
            rows,
            existing=session.schedule,
            project_start=session.schedule.project_start if session.schedule else None,
        )
        session.updated_at = datetime.now(timezone.utc).isoformat()
        return session

    def get_schedule(self, session_id: str) -> BudgetSession:
        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(f"Sessão não encontrada: {session_id}")
        if not session.schedule:
            return self.sync_schedule(session_id)
        return session

    def update_schedule_task(
        self,
        session_id: str,
        task_id: str,
        *,
        duration_days: int | None = None,
        manual_start: str | None = None,
    ) -> BudgetSession:
        from pricing.schedule.cpm_engine import run_cpm
        from pricing.schedule.schedule_builder import update_task_duration

        session = self._sessions.get(session_id)
        if not session or not session.schedule:
            raise KeyError(f"Sessão não encontrada: {session_id}")
        if duration_days is not None:
            session.schedule = update_task_duration(session.schedule, task_id, duration_days)
        else:
            task = session.schedule.task_by_id(task_id)
            if not task:
                raise ValueError(f"Tarefa não encontrada: {task_id}")
            if manual_start is not None:
                task.manual_start = manual_start[:10] if manual_start else None
            session.schedule = run_cpm(session.schedule)
        session.updated_at = datetime.now(timezone.utc).isoformat()
        return session

    def update_schedule_settings(
        self,
        session_id: str,
        *,
        project_start: str,
    ) -> BudgetSession:
        from pricing.schedule.schedule_builder import update_project_start

        session = self._sessions.get(session_id)
        if not session or not session.schedule:
            raise KeyError(f"Sessão não encontrada: {session_id}")
        session.schedule = update_project_start(session.schedule, project_start)
        session.updated_at = datetime.now(timezone.utc).isoformat()
        return session

    def add_schedule_link(
        self,
        session_id: str,
        predecessor_id: str,
        successor_id: str,
        link_type: str = "FS",
        lag_days: int = 0,
    ) -> BudgetSession:
        from pricing.schedule.schedule_builder import add_link

        session = self._sessions.get(session_id)
        if not session or not session.schedule:
            raise KeyError(f"Sessão não encontrada: {session_id}")
        session.schedule = add_link(
            session.schedule,
            predecessor_id,
            successor_id,
            link_type=link_type,
            lag_days=lag_days,
        )
        session.updated_at = datetime.now(timezone.utc).isoformat()
        return session

    def remove_schedule_link(self, session_id: str, link_id: str) -> BudgetSession:
        from pricing.schedule.schedule_builder import remove_link

        session = self._sessions.get(session_id)
        if not session or not session.schedule:
            raise KeyError(f"Sessão não encontrada: {session_id}")
        session.schedule = remove_link(session.schedule, link_id)
        session.updated_at = datetime.now(timezone.utc).isoformat()
        return session

    def recalculate_schedule(self, session_id: str) -> BudgetSession:
        from pricing.schedule.cpm_engine import run_cpm

        session = self._sessions.get(session_id)
        if not session or not session.schedule:
            raise KeyError(f"Sessão não encontrada: {session_id}")
        session.schedule = run_cpm(session.schedule)
        session.updated_at = datetime.now(timezone.utc).isoformat()
        return session

    def compose_schedule(
        self,
        session_id: str,
        prompt: str,
        *,
        use_llm: bool = True,
        replace_links: bool = False,
        llm_client: Any | None = None,
    ) -> tuple[BudgetSession, list[dict[str, str]], str, str | None]:
        from pricing.budget.budget_calculator import BudgetCalculator
        from pricing.schedule.schedule_agent import compose_schedule_from_prompt

        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(f"Sessão não encontrada: {session_id}")
        if not session.schedule:
            session = self.sync_schedule(session_id)

        calc = BudgetCalculator()
        rows: list[dict[str, Any]] = []
        for root in session.roots:
            rows.extend(calc.flatten_rows(root))

        result = compose_schedule_from_prompt(
            session.schedule,
            prompt,
            use_llm=use_llm,
            replace_links=replace_links,
            llm_client=llm_client,
            budget_rows=rows,
        )
        session.schedule = result.schedule
        session.updated_at = datetime.now(timezone.utc).isoformat()
        return session, result.log_dicts(), result.summary, result.llm_model

    def get_tech_spec(self, session_id: str) -> dict[str, Any] | None:
        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(f"Sessão não encontrada: {session_id}")
        return session.tech_spec

    def update_tech_spec(self, session_id: str, payload: dict[str, Any]) -> BudgetSession:
        from pricing.spec.tech_spec_models import TechSpecDocument

        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(f"Sessão não encontrada: {session_id}")
        current = TechSpecDocument.from_dict(session.tech_spec) or TechSpecDocument()
        if payload.get("title"):
            current.title = str(payload["title"])
        if payload.get("markdown") is not None:
            current.markdown = str(payload["markdown"])
        if payload.get("html_content") is not None:
            current.html_content = str(payload["html_content"])
        if payload.get("formatting"):
            current.formatting = dict(payload["formatting"])
        current.touch()
        session.tech_spec = current.to_dict()
        session.updated_at = datetime.now(timezone.utc).isoformat()
        return session

    def export_tech_spec_docx(self, session_id: str) -> bytes:
        from pricing.spec.tech_spec_docx import export_tech_spec_docx
        from pricing.spec.tech_spec_models import TechSpecDocument

        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(f"Sessão não encontrada: {session_id}")
        doc = TechSpecDocument.from_dict(session.tech_spec)
        if not doc or not (doc.markdown.strip() or doc.html_content.strip()):
            raise ValueError("Especificação técnica vazia — gere o documento primeiro.")
        return export_tech_spec_docx(doc)

    @classmethod
    def roots_from_dict(cls, items: list[dict[str, Any]]) -> list[BudgetItem]:
        return [_deserialize_item(i) for i in items]


SESSION_STORE = BudgetSessionStore()
