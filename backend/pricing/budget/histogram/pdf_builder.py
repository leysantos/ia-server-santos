"""Story PDF — histograma MO + equipamentos (tabela + gráfico empilhado)."""

from __future__ import annotations

import html
from typing import Any

from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from pricing.budget.budget_pdf_charts import (
    HISTOGRAM_ITEM_COLORS,
    AnalyticsChartFlowable,
    _stacked_bar_chart,
    CHART_HEIGHT,
)
from pricing.budget.budget_pdf_landscape_template import cell_styles, para, zebra_style_commands
from pricing.budget.histogram.section_mapper import HistogramReport, HistogramSection, build_histogram_report
from pricing.models.budget_item import BudgetItem
from pricing.models.budget_metadata import BudgetProjectMetadata
from pricing.schedule.schedule_models import ProjectSchedule


def _section_table(section: HistogramSection, usable_width: float) -> Table:
    styles = cell_styles()
    n_periods = section.period_count
    col_count = 3 + n_periods
    label_w = usable_width * 0.28
    item_w = usable_width * 0.04
    period_w = (usable_width - label_w - item_w - usable_width * 0.06) / max(1, n_periods)
    total_w = usable_width * 0.06
    col_widths = [item_w, label_w] + [period_w] * n_periods + [total_w]

    headers = ["ITENS", "DISCRIMINAÇÃO", *[str(d) for d in section.period_labels], "TOTAL"]
    data: list[list[Any]] = [
        [para(h, styles["header"] if i < 2 else styles["header_right"]) for i, h in enumerate(headers)]
    ]

    for item in section.items:
        row_cells = [
            para(str(item.index), styles["cell_center"]),
            para(item.description, styles["cell"]),
        ]
        for v in item.values:
            display = f"{v:.2f}".replace(".", ",") if abs(v - round(v)) > 0.01 else str(int(round(v)))
            row_cells.append(para(display, styles["cell_right"]))
        total_display = (
            f"{item.total:.2f}".replace(".", ",")
            if abs(item.total - round(item.total)) > 0.01
            else str(int(round(item.total)))
        )
        row_cells.append(para(total_display, styles["cell_right"]))
        data.append(row_cells)

    total_row = [
        para("", styles["cell"]),
        para("TOTAL", styles["cell"], bold=True),
    ]
    for v in section.monthly_totals:
        display = f"{v:.2f}".replace(".", ",") if abs(v - round(v)) > 0.01 else str(int(round(v)))
        total_row.append(para(display, styles["cell_right"], bold=True))
    grand = sum(section.monthly_totals)
    grand_display = (
        f"{grand:.2f}".replace(".", ",") if abs(grand - round(grand)) > 0.01 else str(int(round(grand)))
    )
    total_row.append(para(grand_display, styles["cell_right"], bold=True))
    data.append(total_row)

    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            zebra_style_commands(
                len(data),
                summary_rows=1,
                right_cols=tuple(range(2, col_count)),
                center_cols=(0,),
            )
        )
    )
    return table


def _section_chart(section: HistogramSection, width: float) -> AnalyticsChartFlowable | None:
    if not section.items:
        return None
    period_labels = [str(d) for d in section.period_labels]
    stacks = [
        (
            item.description[:24],
            HISTOGRAM_ITEM_COLORS[i % len(HISTOGRAM_ITEM_COLORS)],
            item.values,
        )
        for i, item in enumerate(section.items)
    ]

    def render(canv: Any, w: float, h: float) -> None:
        _stacked_bar_chart(
            canv,
            w,
            h,
            period_labels=period_labels,
            stacks=stacks,
            reference_values=None,
        )

    return AnalyticsChartFlowable(width, CHART_HEIGHT + 40, render)


def _section_legend(section: HistogramSection, usable_width: float) -> list[Any]:
    styles = cell_styles()
    parts: list[str] = []
    for i, item in enumerate(section.items):
        color = HISTOGRAM_ITEM_COLORS[i % len(HISTOGRAM_ITEM_COLORS)]
        label = html.escape(item.description[:40])
        parts.append(f'<font color="{color}">■</font> <font size="7">{label}</font>&nbsp;&nbsp;')
    return [Spacer(1, 4), Paragraph("".join(parts), styles["cell"])]


def _append_section_story(
    story: list[Any],
    section: HistogramSection,
    *,
    usable_width: float,
) -> None:
    styles = cell_styles()
    story.append(Paragraph(f"<b>{html.escape(section.title)}</b>", styles["cell"]))
    story.append(Spacer(1, 6))
    story.append(_section_table(section, usable_width))
    story.append(Spacer(1, 10))

    chart = _section_chart(section, usable_width)
    if chart:
        story.append(chart)
        story.extend(_section_legend(section, usable_width))
        story.append(
            Paragraph(
                '<font size="7" color="#64748b">Gráfico empilhado — uma cor por tipo · eixo X = dia acumulado</font>',
                styles["cell"],
            )
        )
        story.append(Spacer(1, 14))


def build_histogram_pdf_story(
    roots: list[BudgetItem],
    *,
    meta: BudgetProjectMetadata,
    schedule: ProjectSchedule | None,
    usable_width: float,
) -> list[Any]:
    report = build_histogram_report(roots, meta, schedule)
    story: list[Any] = []

    if report.mao_obra and report.mao_obra.items:
        _append_section_story(story, report.mao_obra, usable_width=usable_width)
    if report.equipamento and report.equipamento.items:
        _append_section_story(story, report.equipamento, usable_width=usable_width)

    if not story:
        styles = cell_styles()
        story.append(
            Paragraph(
                "Histograma indisponível — sincronize o cronograma e verifique CPUs dos serviços.",
                styles["cell"],
            )
        )
    return story
