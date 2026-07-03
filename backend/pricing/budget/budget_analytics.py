"""Curva ABC, Curva S e Histograma — cálculo e tabelas de exportação."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pricing.budget.budget_export_tables import (
    ExportTableData,
    _cell_money,
    _cell_qty,
    _fetch_open_composition_items,
    _grand_total_for_mode,
    _resolve_open_composition_lookup,
    budget_desoneracao_mode,
)
from pricing.budget.ppd_layout import ROW_TYPE_SERVICO
from pricing.models.budget_item import BudgetItem, BudgetItemType
from pricing.models.budget_metadata import BudgetProjectMetadata
from pricing.schedule.schedule_curves import (
    _days_between,
    build_schedule_curves_by_month,
)
from pricing.schedule.schedule_models import ProjectSchedule, ScheduleTask

from pricing.budget.budget_resource_classification import (
    ResourceCategory,
    resolve_resource_category,
)

PriceMode = Literal["comd", "semd"]
AbcClass = Literal["A", "B", "C"]


@dataclass
class AbcItem:
    row_id: str
    code: str
    name: str
    value: float
    pct: float
    cumulative_pct: float
    abc_class: AbcClass


@dataclass
class StackedHistogramMonth:
    month_index: int
    label: str
    period_day: int
    equipamento_qty: float
    equipamento: float
    mao_obra_qty: float
    mao_obra: float
    insumo: float = 0.0
    total: float = 0.0
    total_qty: float = 0.0
    total_with_bdi: float = 0.0


HOURS_PER_WORKER_MONTH = 22 * 8


def _is_service_item(item: BudgetItem) -> bool:
    return (
        item.row_type in (ROW_TYPE_SERVICO, "SERVICO")
        or item.item_type == BudgetItemType.COMPOSITION
    ) and item.row_type not in ("ETAPA", "SUB-ETAPA")


def iter_service_items(roots: list[BudgetItem]) -> list[BudgetItem]:
    out: list[BudgetItem] = []

    def walk(node: BudgetItem) -> None:
        if node.metadata.get("is_memory_row") or node.row_type == "MEMORIA":
            return
        if _is_service_item(node):
            out.append(node)
        for child in node.children:
            walk(child)

    for root in roots:
        walk(root)
    return out


def flatten_budget_items(roots: list[BudgetItem]) -> list[BudgetItem]:
    """Lista plana de todos os itens (para lookup por row_id)."""
    rows: list[BudgetItem] = []

    def walk(node: BudgetItem) -> None:
        rows.append(node)
        for child in node.children:
            if child.metadata.get("is_memory_row") or child.row_type == "MEMORIA":
                continue
            walk(child)

    for root in roots:
        walk(root)
    return rows


def _service_value(item: BudgetItem) -> float:
    return max(0.0, item.effective_total())


def _classify_abc(cumulative_pct: float) -> AbcClass:
    if cumulative_pct <= 80:
        return "A"
    if cumulative_pct <= 95:
        return "B"
    return "C"


def build_abc_curve(roots: list[BudgetItem]) -> list[AbcItem]:
    services = iter_service_items(roots)
    sorted_items = sorted(services, key=lambda r: _service_value(r), reverse=True)
    total = sum(_service_value(r) for r in sorted_items) or 1.0
    cumulative = 0.0
    result: list[AbcItem] = []
    for row in sorted_items:
        value = _service_value(row)
        pct = (value / total) * 100
        cumulative += pct
        result.append(
            AbcItem(
                row_id=row.row_id,
                code=str(row.code or ""),
                name=str(row.name or ""),
                value=value,
                pct=pct,
                cumulative_pct=cumulative,
                abc_class=_classify_abc(cumulative),
            )
        )
    return result


def _task_for_service(schedule: ProjectSchedule, row_id: str) -> ScheduleTask | None:
    for task in schedule.tasks:
        if (
            task.budget_row_id == row_id
            and not task.is_summary
            and task.early_start
            and task.early_finish
        ):
            return task
    return None


def _item_cost_for_service(
    cpu_item: dict[str, Any],
    service_qty: float,
    mode: PriceMode,
) -> float:
    if mode == "semd":
        unit_partial = cpu_item.get("partial_cost_sem")
        if unit_partial is None:
            unit_partial = cpu_item.get("partial_cost")
    else:
        unit_partial = cpu_item.get("partial_cost")
    return max(0.0, float(unit_partial or 0) * max(0.0, service_qty))


def _category_totals_from_composition(
    items: list[dict[str, Any]],
    service_qty: float,
    mode: PriceMode,
) -> dict[ResourceCategory, float]:
    totals: dict[ResourceCategory, float] = {
        "equipamento": 0.0,
        "insumo": 0.0,
        "mao_obra": 0.0,
    }
    composicao_cost = 0.0
    for item in items:
        cat = resolve_resource_category(item)
        cost = _item_cost_for_service(item, service_qty, mode)
        if cat:
            totals[cat] += cost
        elif str(item.get("item_type") or "").lower() == "composicao":
            composicao_cost += cost
    direct_sum = totals["equipamento"] + totals["insumo"] + totals["mao_obra"]
    if composicao_cost > 0 and direct_sum > 0:
        for cat in ("equipamento", "insumo", "mao_obra"):
            totals[cat] += composicao_cost * (totals[cat] / direct_sum)
    elif composicao_cost > 0:
        totals["insumo"] += composicao_cost
    return totals


def _service_bdi_factor(item: BudgetItem, analytical_cost: float) -> float:
    effective = _service_value(item)
    if analytical_cost > 0:
        return effective / analytical_cost
    unit_base = max(0.0, float(item.unit_cost or 0) * max(0.0, float(item.quantity or 0)))
    return effective / unit_base if unit_base > 0 else 1.0


def _overlap_days(
    range_start: str,
    range_end: str,
    period_start: str,
    period_end: str,
) -> int:
    from datetime import date

    def parse(iso: str) -> date:
        y, m, d = iso[:10].split("-")
        return date(int(y), int(m), int(d))

    rs = parse(range_start)
    re = parse(range_end)
    ps = parse(period_start)
    pe = parse(period_end)
    start = max(rs, ps)
    end = min(re, pe)
    if end < start:
        return 0
    return (end - start).days + 1


def _is_hour_unit(unit: str) -> bool:
    u = (unit or "").strip().upper()
    return u in ("H", "HH", "CH", "H/H") or "HORA" in u


def _item_coef_qty(cpu_item: dict[str, Any], service_qty: float) -> float:
    return max(0.0, float(cpu_item.get("coefficient") or 0) * max(0.0, service_qty))


def _histogram_item_quantity(
    cpu_item: dict[str, Any],
    service_qty: float,
    category: ResourceCategory,
) -> float:
    qty = _item_coef_qty(cpu_item, service_qty)
    unit = str(cpu_item.get("unit") or "")
    if category == "mao_obra" and _is_hour_unit(unit):
        return qty / HOURS_PER_WORKER_MONTH
    return qty


def build_stacked_histogram(
    roots: list[BudgetItem],
    meta: BudgetProjectMetadata,
    schedule: ProjectSchedule | None,
    *,
    price_mode: PriceMode | None = None,
) -> tuple[list[StackedHistogramMonth], float, float, float, float, float]:
    """Retorna meses MO+equipamento (qtd e R$), totais EQ/MO/total qty/total R$/legacy bdi=0."""
    if not schedule or not schedule.project_start:
        return [], 0.0, 0.0, 0.0, 0.0, 0.0

    mode: PriceMode = price_mode or budget_desoneracao_mode(roots)  # type: ignore[assignment]
    schedule_months, _, _ = build_schedule_curves_by_month(schedule, flatten_budget_items(roots))
    if not schedule_months:
        return [], 0.0, 0.0, 0.0, 0.0, 0.0

    project_start = schedule.project_start
    buckets: list[dict[str, float]] = [
        {
            "equipamento_qty": 0.0,
            "equipamento": 0.0,
            "mao_obra_qty": 0.0,
            "mao_obra": 0.0,
        }
        for _ in schedule_months
    ]

    comp_cache: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    services_with_cpu = 0

    for service in iter_service_items(roots):
        lookup = _resolve_open_composition_lookup(service, meta)
        if not lookup or not service.source_code:
            continue
        items = _fetch_open_composition_items(service.source_code, lookup, comp_cache)
        if not items:
            continue
        services_with_cpu += 1

        service_qty = float(service.quantity or 1)
        task = _task_for_service(schedule, service.row_id)

        for item in items:
            cat = resolve_resource_category(item)
            if cat not in ("mao_obra", "equipamento"):
                continue
            qty = _histogram_item_quantity(item, service_qty, cat)
            val = _item_cost_for_service(item, service_qty, mode)
            if qty <= 0 and val <= 0:
                continue

            def _apply(factor: float, bucket: dict[str, float]) -> None:
                if cat == "equipamento":
                    bucket["equipamento_qty"] += qty * factor
                    bucket["equipamento"] += val * factor
                else:
                    bucket["mao_obra_qty"] += qty * factor
                    bucket["mao_obra"] += val * factor

            if not task or not task.early_start or not task.early_finish:
                _apply(1.0, buckets[0])
                continue

            duration = max(1, task.duration_days)
            for i, m in enumerate(schedule_months):
                overlap = _overlap_days(
                    task.early_start,
                    task.early_finish,
                    m.month_start_iso,
                    m.month_end_iso,
                )
                if overlap <= 0:
                    continue
                _apply(overlap / duration, buckets[i])

    months: list[StackedHistogramMonth] = []
    for i, m in enumerate(schedule_months):
        period_day = _days_between(project_start, m.month_end_iso) + 1
        b = buckets[i]
        eq_v = b["equipamento"]
        mo_v = b["mao_obra"]
        eq_q = b["equipamento_qty"]
        mo_q = b["mao_obra_qty"]
        months.append(
            StackedHistogramMonth(
                month_index=i,
                label=m.label,
                period_day=period_day,
                equipamento_qty=eq_q,
                equipamento=eq_v,
                mao_obra_qty=mo_q,
                mao_obra=mo_v,
                insumo=0.0,
                total=eq_v + mo_v,
                total_qty=eq_q + mo_q,
                total_with_bdi=0.0,
            )
        )

    totals_eq = sum(m.equipamento for m in months)
    totals_mo = sum(m.mao_obra for m in months)
    totals_all = sum(m.total for m in months)
    totals_eq_qty = sum(m.equipamento_qty for m in months)
    totals_mo_qty = sum(m.mao_obra_qty for m in months)
    return months, totals_eq_qty, totals_mo_qty, totals_eq, totals_mo, totals_all


def _fmt_pct(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def build_curva_abc_export_table(roots: list[BudgetItem]) -> ExportTableData:
    items = build_abc_curve(roots)
    headers = ["Item", "Código", "Descrição", "Valor (R$)", "% Individual", "% Acumulado", "Classe"]
    rows: list[list[Any]] = []
    bold_rows: set[int] = set()

    for idx, item in enumerate(items):
        if item.abc_class == "A":
            bold_rows.add(idx)
        rows.append([
            str(idx + 1),
            item.code,
            item.name,
            _cell_money(item.value),
            _fmt_pct(item.pct),
            _fmt_pct(item.cumulative_pct),
            item.abc_class,
        ])

    total = sum(i.value for i in items)
    summary: list[Any] = ["", "", "TOTAL", _cell_money(total), "100,00", "100,00", ""]
    rows.append(summary)
    bold_rows.add(len(rows) - 1)

    return ExportTableData(
        headers=headers,
        rows=rows,
        center_cols=(0, 1, 6),
        right_cols=(3, 4, 5),
        summary_rows=1,
        bold_rows=bold_rows,
    )


@dataclass
class CurvaSDesoneracaoMeta:
    adopted_mode: str
    adopted_label: str
    total_comd: float
    total_semd: float
    adopted_total: float
    total_financial_curve: float
    bdi_rate_comd: float
    bdi_rate_semd: float


def build_curva_s_desoneracao_meta(
    roots: list[BudgetItem],
    meta: BudgetProjectMetadata | None,
    total_financial_curve: float,
) -> CurvaSDesoneracaoMeta:
    adopted_mode = budget_desoneracao_mode(roots)
    total_comd = _grand_total_for_mode(roots, "comd")
    total_semd = _grand_total_for_mode(roots, "semd")
    adopted_total = total_semd if adopted_mode == "semd" else total_comd
    bdi = meta.bdi if meta else BudgetProjectMetadata().bdi
    adopted_label = (
        "Sem desoneração" if adopted_mode == "semd" else "Com desoneração"
    )
    return CurvaSDesoneracaoMeta(
        adopted_mode=adopted_mode,
        adopted_label=adopted_label,
        total_comd=total_comd,
        total_semd=total_semd,
        adopted_total=adopted_total,
        total_financial_curve=total_financial_curve,
        bdi_rate_comd=bdi.rate_com_desoneracao,
        bdi_rate_semd=bdi.rate_sem_desoneracao,
    )


def format_curva_s_scenario_block(
    scenario: CurvaSDesoneracaoMeta,
) -> tuple[str, list[str]]:
    mode_short = "SemD" if scenario.adopted_mode == "semd" else "ComD"
    bdi_comd_pct = f"{scenario.bdi_rate_comd * 100:.2f}%".replace(".", ",")
    bdi_semd_pct = f"{scenario.bdi_rate_semd * 100:.2f}%".replace(".", ",")
    extra = (
        f"Cenário adotado: {scenario.adopted_label} ({mode_short}) — "
        "critério menor valor integral entre ComD e SemD"
    )
    body = [
        f"Total com desoneração (ComD, BDI {bdi_comd_pct}): {_cell_money(scenario.total_comd)}",
        f"Total sem desoneração (SemD, BDI {bdi_semd_pct}): {_cell_money(scenario.total_semd)}",
        f"Total adotado ({mode_short}): {_cell_money(scenario.adopted_total)}",
        (
            "Base financeira da curva (soma efetiva por serviço, rateada pelo cronograma): "
            f"{_cell_money(scenario.total_financial_curve)}"
        ),
    ]
    return extra, body


def build_curva_s_export_table(
    roots: list[BudgetItem],
    schedule: ProjectSchedule | None,
    meta: BudgetProjectMetadata | None = None,
) -> tuple[str | None, list[str], ExportTableData]:
    if not schedule or not schedule.project_start:
        raise ValueError("Cronograma não sincronizado — sincronize na aba Cronograma antes de exportar.")

    flat = flatten_budget_items(roots)
    months, total_financial, _ = build_schedule_curves_by_month(schedule, flat)
    if not months:
        raise ValueError("Cronograma sem meses válidos.")

    fin_denom = total_financial if total_financial > 0 else 1.0
    headers = [
        "Mês",
        "Dia acum.",
        "Físico mensal (%)",
        "Físico acum. (%)",
        "Financeiro mensal (R$)",
        "Financeiro acum. (R$)",
        "Financeiro acum. (%)",
    ]
    rows: list[list[Any]] = []
    project_start = schedule.project_start

    for m in months:
        period_day = _days_between(project_start, m.month_end_iso) + 1
        fin_cum_pct = (m.financial_cumulative / fin_denom) * 100
        rows.append([
            m.label,
            period_day,
            _fmt_pct(m.physical_monthly_pct),
            _fmt_pct(m.physical_cumulative_pct),
            _cell_money(m.financial_monthly),
            _cell_money(m.financial_cumulative),
            _fmt_pct(fin_cum_pct),
        ])

    extra = f"Valor total do orçamento: {_cell_money(total_financial)}"
    scenario = build_curva_s_desoneracao_meta(roots, meta, total_financial)
    extra, body = format_curva_s_scenario_block(scenario)
    return extra, body, ExportTableData(
        headers=headers,
        rows=rows,
        right_cols=(1, 2, 3, 4, 5, 6),
    )


def build_histograma_export_table(
    roots: list[BudgetItem],
    meta: BudgetProjectMetadata,
    schedule: ProjectSchedule | None,
) -> tuple[str | None, ExportTableData]:
    months, _, _, total_eq, total_mo, total_val = build_stacked_histogram(
        roots, meta, schedule
    )
    if not months:
        raise ValueError(
            "Histograma indisponível — sincronize o cronograma e verifique CPUs dos serviços."
        )

    mode = budget_desoneracao_mode(roots)
    mode_label = "Com desoneração" if mode == "comd" else "Sem desoneração"
    headers = [
        "Mês",
        "Dia acum.",
        "Equip. (qtd)",
        "Equip. (R$)",
        "MO (qtd)",
        "MO (R$)",
        "Total qtd",
        "Total (R$)",
    ]
    rows: list[list[Any]] = []
    for m in months:
        rows.append([
            m.label,
            m.period_day,
            _cell_qty(m.equipamento_qty),
            _cell_money(m.equipamento),
            _cell_qty(m.mao_obra_qty),
            _cell_money(m.mao_obra),
            _cell_qty(m.total_qty),
            _cell_money(m.total),
        ])

    rows.append([
        "TOTAL",
        "",
        _cell_qty(sum(m.equipamento_qty for m in months)),
        _cell_money(total_eq),
        _cell_qty(sum(m.mao_obra_qty for m in months)),
        _cell_money(total_mo),
        _cell_qty(sum(m.total_qty for m in months)),
        _cell_money(total_val),
    ])

    extra = f"Preços: {mode_label} · MO e equipamentos rateados pelo cronograma"
    return extra, ExportTableData(
        headers=headers,
        rows=rows,
        right_cols=(1, 2, 3, 4, 5, 6, 7),
        summary_rows=1,
        bold_rows={len(rows) - 1},
    )


@dataclass
class AggregatedResourceLine:
    code: str
    description: str
    unit: str
    quantity: float
    unit_price: float
    direct_total: float
    total_with_bdi: float


def _matches_resource_target(item: dict[str, Any], target: ResourceCategory) -> bool:
    return resolve_resource_category(item) == target


def build_resource_rollup(
    roots: list[BudgetItem],
    meta: BudgetProjectMetadata,
    *,
    target: ResourceCategory,
) -> tuple[list[AggregatedResourceLine], int, int, PriceMode]:
    """Agrega insumos/materiais ou mão de obra de todas as CPUs dos serviços."""
    mode: PriceMode = budget_desoneracao_mode(roots)  # type: ignore[assignment]
    comp_cache: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    services = iter_service_items(roots)
    services_with_cpu = 0

    buckets: dict[tuple[str, str], dict[str, Any]] = {}

    for service in services:
        lookup = _resolve_open_composition_lookup(service, meta)
        if not lookup or not service.source_code:
            continue
        items = _fetch_open_composition_items(service.source_code, lookup, comp_cache)
        if not items:
            continue

        service_qty = float(service.quantity or 1)
        category_totals = _category_totals_from_composition(items, service_qty, mode)
        category_sum = sum(category_totals.values())
        if category_sum <= 0:
            continue

        has_target = False
        for item in items:
            if not _matches_resource_target(item, target):
                continue
            has_target = True
            code = str(item.get("code") or "").strip()
            unit = str(item.get("unit") or "").strip()
            key = (code, unit)
            coef = float(item.get("coefficient") or 0)
            qty = coef * service_qty
            direct = _item_cost_for_service(item, service_qty, mode)
            bdi_factor = _service_bdi_factor(service, category_sum)
            with_bdi = direct * bdi_factor

            if key not in buckets:
                buckets[key] = {
                    "code": code,
                    "description": str(item.get("description") or "").strip(),
                    "unit": unit,
                    "quantity": 0.0,
                    "direct_total": 0.0,
                    "total_with_bdi": 0.0,
                }
            bucket = buckets[key]
            if not bucket["description"]:
                bucket["description"] = str(item.get("description") or "").strip()
            bucket["quantity"] += qty
            bucket["direct_total"] += direct
            bucket["total_with_bdi"] += with_bdi

        if has_target:
            services_with_cpu += 1

    lines: list[AggregatedResourceLine] = []
    for bucket in sorted(buckets.values(), key=lambda b: (b["code"], b["unit"])):
        qty = bucket["quantity"]
        direct = bucket["direct_total"]
        unit_price = direct / qty if qty > 0 else 0.0
        lines.append(
            AggregatedResourceLine(
                code=bucket["code"],
                description=bucket["description"],
                unit=bucket["unit"],
                quantity=qty,
                unit_price=unit_price,
                direct_total=direct,
                total_with_bdi=bucket["total_with_bdi"],
            )
        )
    return lines, len(services), services_with_cpu, mode


def _build_resource_report_export_table(
    roots: list[BudgetItem],
    meta: BudgetProjectMetadata,
    *,
    target: ResourceCategory,
    empty_message: str,
) -> tuple[str | None, ExportTableData]:
    lines, total_services, services_with_cpu, mode = build_resource_rollup(
        roots, meta, target=target
    )
    if not lines:
        raise ValueError(empty_message)

    mode_label = "Com desoneração" if mode == "comd" else "Sem desoneração"
    skipped = total_services - services_with_cpu
    extra_parts = [f"Preços: {mode_label}", f"Serviços com CPU: {services_with_cpu}"]
    if skipped > 0:
        extra_parts.append(f"Serviços sem CPU: {skipped}")
    extra = " · ".join(extra_parts)

    headers = [
        "Item",
        "Código",
        "Descrição",
        "Un",
        "Qtd",
        "Valor unit.",
        "Total linha (R$)",
    ]
    rows: list[list[Any]] = []
    for idx, line in enumerate(lines):
        rows.append([
            str(idx + 1),
            line.code,
            line.description,
            line.unit,
            _cell_qty(line.quantity),
            _cell_money(line.unit_price),
            _cell_money(line.direct_total),
        ])

    direct_grand = sum(line.direct_total for line in lines)
    with_bdi_grand = sum(line.total_with_bdi for line in lines)
    bdi_val = with_bdi_grand - direct_grand

    summary_start = len(rows)
    rows.append(["", "", "TOTAL SEM BDI", "", "", "", _cell_money(direct_grand)])
    rows.append(["", "", "VALOR BDI", "", "", "", _cell_money(bdi_val)])
    rows.append(["", "", "TOTAL COM BDI", "", "", "", _cell_money(with_bdi_grand)])

    return extra, ExportTableData(
        headers=headers,
        rows=rows,
        right_cols=(4, 5, 6),
        summary_rows=3,
        bold_rows={summary_start, summary_start + 1, summary_start + 2},
    )


def build_insumos_export_table(
    roots: list[BudgetItem],
    meta: BudgetProjectMetadata,
) -> tuple[str | None, ExportTableData]:
    return _build_resource_report_export_table(
        roots,
        meta,
        target="insumo",
        empty_message=(
            "Relatório de insumos indisponível — verifique CPUs dos serviços "
            "(código de composição e bases de preço)."
        ),
    )


def build_mao_obra_export_table(
    roots: list[BudgetItem],
    meta: BudgetProjectMetadata,
) -> tuple[str | None, ExportTableData]:
    return _build_resource_report_export_table(
        roots,
        meta,
        target="mao_obra",
        empty_message=(
            "Relatório de mão de obra indisponível — verifique CPUs dos serviços "
            "(código de composição e bases de preço)."
        ),
    )
