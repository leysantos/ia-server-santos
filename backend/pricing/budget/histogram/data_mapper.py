"""Mapeamento de dados — template MO, períodos e integração cronograma/CPU."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Literal

from pricing.budget.budget_analytics import iter_service_items
from pricing.budget.budget_export_tables import (
    _fetch_open_composition_items,
    _resolve_open_composition_lookup,
    budget_desoneracao_mode,
)
from pricing.budget.budget_resource_classification import resolve_resource_category
from pricing.models.budget_item import BudgetItem
from pricing.models.budget_metadata import BudgetProjectMetadata
from pricing.schedule.schedule_models import ProjectSchedule, ScheduleTask

PriceMode = Literal["comd", "semd"]

# Períodos padrão construtora (dias de avanço temporal)
DEFAULT_PERIOD_DAYS: tuple[int, ...] = (
    30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330, 360,
)

# Funções padronizadas — ordem fixa do template executivo
STANDARD_MO_ROLES: tuple[str, ...] = (
    "Mestre de Obras",
    "Almoxarife",
    "Engenheiro Residente",
    "Técnico de Segurança",
    "Oficial de Produção",
    "Servente",
    "Encarregado",
    "Montador",
    "Auxiliar de Montagem",
    "Operador de Guindaste",
    "Operador",
    "Soldador",
)

HOURS_PER_WORKER_MONTH = 22 * 8

# Palavras-chave para mapear descrições de CPU → função padrão
_ROLE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Mestre de Obras", ("mestre de obra", "mestre obra", "master")),
    ("Almoxarife", ("almoxarife", "almoxarif")),
    ("Engenheiro Residente", ("engenheiro residente", "eng. residente", "residente")),
    ("Técnico de Segurança", ("tecnico de seguranca", "técnico de segurança", "tecnico seguranca", "tss")),
    ("Oficial de Produção", ("oficial de producao", "oficial de produção", "pedreiro", "carpinteiro", "armador")),
    ("Servente", ("servente", "ajudante", "auxiliar geral")),
    ("Encarregado", ("encarregado", "supervisor")),
    ("Montador", ("montador", "montagem", "estrutura metalica", "estrutura metálica")),
    ("Auxiliar de Montagem", ("auxiliar de montagem", "aux montagem")),
    ("Operador de Guindaste", ("operador de guindaste", "guindaste", "guindasteiro")),
    ("Operador", ("operador", "operador de maquina", "operador de máquina", "motorista", "eletricista")),
    ("Soldador", ("soldador", "solda")),
)


def _normalize_text(value: str) -> str:
    text = (value or "").lower()
    text = text.replace("á", "a").replace("à", "a").replace("ã", "a")
    text = text.replace("é", "e").replace("ê", "e")
    text = text.replace("í", "i")
    text = text.replace("ó", "o").replace("ô", "o").replace("õ", "o")
    text = text.replace("ú", "u").replace("ç", "c")
    return re.sub(r"\s+", " ", text).strip()


def map_description_to_role(description: str) -> str | None:
    """Mapeia descrição de item CPU para função padronizada."""
    norm = _normalize_text(description)
    if not norm:
        return None
    for role, keywords in _ROLE_KEYWORDS:
        for kw in keywords:
            if kw in norm:
                return role
    return None


def _is_hour_unit(unit: str) -> bool:
    u = (unit or "").strip().upper()
    return u in ("H", "HH", "CH", "H/H") or "HORA" in u


def _to_headcount(quantity: float, unit: str) -> float:
    if _is_hour_unit(unit):
        return quantity / HOURS_PER_WORKER_MONTH
    return quantity


def _parse_iso(iso: str) -> date:
    y, m, d = iso[:10].split("-")
    return date(int(y), int(m), int(d))


def _add_days(iso: str, days: int) -> str:
    dt = _parse_iso(iso) + timedelta(days=days)
    return dt.isoformat()


def _overlap_days(range_start: str, range_end: str, period_start: str, period_end: str) -> int:
    rs, re = _parse_iso(range_start), _parse_iso(range_end)
    ps, pe = _parse_iso(period_start), _parse_iso(period_end)
    start = max(rs, ps)
    end = min(re, pe)
    if end < start:
        return 0
    return (end - start).days + 1


def build_period_windows(
    project_start: str,
    period_days: tuple[int, ...] | None = None,
) -> list[tuple[str, str, int]]:
    """Janelas [início, fim] por coluna (ex.: dias 1–30, 31–60…)."""
    days = period_days or DEFAULT_PERIOD_DAYS
    windows: list[tuple[str, str, int]] = []
    prev_end = 0
    for end_day in days:
        w_start = _add_days(project_start, prev_end)
        w_end = _add_days(project_start, end_day - 1)
        windows.append((w_start, w_end, end_day))
        prev_end = end_day
    return windows


def _task_for_service(schedule: ProjectSchedule, row_id: str) -> ScheduleTask | None:
    for task in schedule.tasks or []:
        if task.budget_row_id == row_id:
            return task
    return None


@dataclass
class HistogramMoRow:
    index: int
    role: str
    values: list[float] = field(default_factory=list)

    @property
    def total(self) -> float:
        return sum(self.values)


@dataclass
class HistogramMoModel:
    """Modelo reutilizável — suporta múltiplas obras via metadados + template."""

    title: str = "HISTOGRAMA DE MÃO DE OBRA DIRETA"
    empresa: str = ""
    cliente: str = ""
    obra: str = ""
    emission_date: str = ""
    period_labels: list[int] = field(default_factory=lambda: list(DEFAULT_PERIOD_DAYS))
    rows: list[HistogramMoRow] = field(default_factory=list)
    has_schedule: bool = False
    services_with_cpu: int = 0
    template_id: str = "mo_direta_v2"
    notes: str = ""

    @property
    def period_count(self) -> int:
        return len(self.period_labels)


def _empty_template_model(meta: BudgetProjectMetadata) -> HistogramMoModel:
    period_labels = list(DEFAULT_PERIOD_DAYS)
    rows = [
        HistogramMoRow(index=i + 1, role=role, values=[0.0] * len(period_labels))
        for i, role in enumerate(STANDARD_MO_ROLES)
    ]
    return HistogramMoModel(
        empresa=meta.empresa or meta.orgao or "",
        cliente=meta.orgao or meta.empresa or "",
        obra=meta.projeto or meta.objeto or "",
        period_labels=period_labels,
        rows=rows,
        notes="Template editável — preencha os efetivos por período ou sincronize o cronograma.",
    )


def build_histogram_mo_model(
    roots: list[BudgetItem],
    meta: BudgetProjectMetadata,
    schedule: ProjectSchedule | None,
    *,
    period_days: tuple[int, ...] | None = None,
    price_mode: PriceMode | None = None,
) -> HistogramMoModel:
    """
    Monta modelo MO a partir do cronograma + CPUs (mão de obra).
    Sem cronograma, retorna template vazio editável com funções padronizadas.
    """
    period_labels = list(period_days or DEFAULT_PERIOD_DAYS)
    accum: dict[str, list[float]] = {role: [0.0] * len(period_labels) for role in STANDARD_MO_ROLES}

    if not schedule or not schedule.project_start:
        model = _empty_template_model(meta)
        model.period_labels = period_labels
        model.rows = [
            HistogramMoRow(index=i + 1, role=role, values=list(accum[role]))
            for i, role in enumerate(STANDARD_MO_ROLES)
        ]
        return model

    mode: PriceMode = price_mode or budget_desoneracao_mode(roots)  # type: ignore[assignment]
    windows = build_period_windows(schedule.project_start, tuple(period_labels))
    comp_cache: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    services_with_cpu = 0

    for service in iter_service_items(roots):
        lookup = _resolve_open_composition_lookup(service, meta)
        if not lookup or not service.source_code:
            continue
        items = _fetch_open_composition_items(service.source_code, lookup, comp_cache)
        if not items:
            continue

        mo_items = [
            it for it in items if resolve_resource_category(it) == "mao_obra"
        ]
        if not mo_items:
            continue

        services_with_cpu += 1
        service_qty = float(service.quantity or 1)
        task = _task_for_service(schedule, service.row_id)

        for item in mo_items:
            role = map_description_to_role(str(item.get("description") or ""))
            if not role:
                role = "Servente"
            coef = float(item.get("coefficient") or 0)
            unit = str(item.get("unit") or "")
            total_qty = _to_headcount(coef * service_qty, unit)
            if total_qty <= 0:
                continue

            if not task or not task.early_start or not task.early_finish:
                accum[role][0] += total_qty
                continue

            duration = max(1, task.duration_days)
            for i, (w_start, w_end, _) in enumerate(windows):
                overlap = _overlap_days(task.early_start, task.early_finish, w_start, w_end)
                if overlap <= 0:
                    continue
                accum[role][i] += total_qty * (overlap / duration)

    rows = [
        HistogramMoRow(
            index=i + 1,
            role=role,
            values=[round(v, 2) for v in accum[role]],
        )
        for i, role in enumerate(STANDARD_MO_ROLES)
    ]

    note = (
        f"Efetivos estimados a partir de {services_with_cpu} serviço(s) com CPU · "
        f"cronograma sincronizado · unidade hora convertida em profissionais (176 h/mês)"
        if services_with_cpu
        else "Template editável — vincule CPUs e cronograma para pré-preenchimento automático."
    )

    return HistogramMoModel(
        empresa=meta.empresa or meta.orgao or "",
        cliente=meta.orgao or meta.empresa or "",
        obra=meta.projeto or meta.objeto or "",
        period_labels=period_labels,
        rows=rows,
        has_schedule=True,
        services_with_cpu=services_with_cpu,
        notes=note,
    )
