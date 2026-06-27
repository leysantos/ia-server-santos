"""Gráficos analíticos para PDF — espelho de frontend/components/BudgetChartPrimitives.tsx."""

from __future__ import annotations

from typing import Any, Callable

from reportlab.lib import colors
from reportlab.platypus import Flowable

from pricing.budget.budget_analytics import (
    AbcItem,
    build_abc_curve,
    build_stacked_histogram,
)
from pricing.budget.budget_analytics import flatten_budget_items
from pricing.models.budget_item import BudgetItem
from pricing.models.budget_metadata import BudgetProjectMetadata
from pricing.schedule.schedule_curves import build_schedule_curves_by_month
from pricing.schedule.schedule_models import ProjectSchedule

# Cores alinhadas ao frontend
ABC_CLASS_COLORS = {"A": "#10b981", "B": "#f59e0b", "C": "#64748b"}
SCURVE_PHYSICAL = "#10b981"
SCURVE_FINANCIAL = "#38bdf8"
CUMULATIVE_LINE = "#38bdf8"
HIST_STACK_COLORS = {
    "insumo": "#10b981",
    "equipamento": "#f59e0b",
    "mao_obra": "#38bdf8",
}
HIST_REF_BDI = "#f472b6"
HIST_SEGMENT_STROKE = "#1e293b"
GRID_COLOR = colors.HexColor("#94a3b8")
LABEL_COLOR = colors.HexColor("#64748b")
CHART_HEIGHT = 185.0


class AnalyticsChartFlowable(Flowable):
    """Flowable que desenha gráfico SVG-like diretamente no canvas ReportLab."""

    def __init__(self, width: float, height: float, render: Callable) -> None:
        super().__init__()
        self.width = width
        self.height = height
        self._render = render

    def draw(self) -> None:
        self._render(self.canv, self.width, self.height)


def _hex(value: str) -> colors.Color:
    return colors.HexColor(value)


def _scale_linear(value: float, domain_max: float, range_max: float) -> float:
    if domain_max <= 0:
        return 0.0
    return (value / domain_max) * range_max


def _nice_ceil(value: float) -> float:
    if value <= 10:
        return 10.0
    if value <= 50:
        return float(int((value + 4) // 5) * 5)
    if value <= 100:
        return float(int((value + 9) // 10) * 10)
    return float(int((value + 49) // 50) * 50)


def _format_axis_tick(value: float) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.0f}k"
    return str(int(value)) if value == int(value) else f"{value:.1f}"


def _truncate_label(text: str, max_len: int = 10) -> str:
    t = str(text or "")
    return t if len(t) <= max_len else f"{t[: max_len - 1]}…"


def _y_at_value(value: float, domain_max: float, plot_bottom: float, inner_h: float) -> float:
    """Coordenada Y no canvas ReportLab (origem embaixo, valores sobem)."""
    return plot_bottom + _scale_linear(value, domain_max, inner_h)


def _stack_segments_for_bar(
    stacks: list[tuple[str, str, list[float]]],
    bar_index: int,
    *,
    y_max: float,
    plot_bottom: float,
    inner_h: float,
) -> list[tuple[str, float, float]]:
    """
    Segmentos empilhados sem sobreposição — base/topo derivados do valor acumulado.
    Retorna (cor, y_base, altura) de baixo para cima.
    """
    segments: list[tuple[str, float, float]] = []
    cum_value = 0.0
    for _, color, values in stacks:
        value = values[bar_index] if bar_index < len(values) else 0.0
        if value <= 0:
            continue
        y_base = _y_at_value(cum_value, y_max, plot_bottom, inner_h)
        y_top = _y_at_value(cum_value + value, y_max, plot_bottom, inner_h)
        seg_h = y_top - y_base
        if seg_h >= 0.4:
            segments.append((color, y_base, seg_h))
        cum_value += value
    return segments


def _draw_stacked_bar(
    canv: Any,
    *,
    slot_x: float,
    bar_w: float,
    segments: list[tuple[str, float, float]],
) -> None:
    """Desenha coluna empilhada — cada faixa encosta na anterior, sem overlap."""
    stroke_w = 0.4
    for color, y_base, seg_h in segments:
        canv.setFillColor(_hex(color))
        # Contorno escuro entre faixas — separa cores sem sobrepor preenchimento
        canv.setStrokeColor(colors.HexColor(HIST_SEGMENT_STROKE))
        canv.setLineWidth(stroke_w)
        canv.rect(
            slot_x - bar_w / 2,
            y_base,
            bar_w,
            seg_h,
            stroke=1,
            fill=1,
        )


def _draw_grid_h(
    canv: Any,
    *,
    left: float,
    plot_bottom: float,
    inner_w: float,
    inner_h: float,
    ticks: list[float],
    domain_max: float,
    fmt: Callable[[float], str],
    right_labels: list[tuple[float, str, colors.Color]] | None = None,
    right_domain_max: float = 100.0,
) -> None:
    canv.setStrokeColor(GRID_COLOR)
    canv.setStrokeAlpha(0.25)
    canv.setFont("Helvetica", 7)
    for tick in ticks:
        y = _y_at_value(tick, domain_max, plot_bottom, inner_h)
        canv.line(left, y, left + inner_w, y)
        canv.setFillColor(LABEL_COLOR)
        canv.drawRightString(left - 4, y - 3, fmt(tick))
    canv.setStrokeAlpha(1)

    if right_labels:
        for tick, label, color in right_labels:
            y = _y_at_value(tick, right_domain_max, plot_bottom, inner_h)
            canv.setFillColor(color)
            canv.drawString(left + inner_w + 4, y - 3, label)


def _pareto_chart(
    canv: Any,
    width: float,
    height: float,
    *,
    labels: list[str],
    bar_values: list[float],
    cumulative_pct: list[float],
    bar_colors: list[str],
) -> None:
    m_left, m_right, m_top, m_bottom = 52.0, 48.0, 16.0, 36.0
    inner_w = width - m_left - m_right
    inner_h = height - m_top - m_bottom
    plot_bottom = m_bottom
    n = max(1, len(labels))
    slot_w = inner_w / n
    bar_w = min(28.0, slot_w * 0.7)
    bar_max = max(1.0, max(bar_values, default=0))

    y_ticks = [bar_max * f for f in (0.0, 0.25, 0.5, 0.75, 1.0)]
    _draw_grid_h(
        canv,
        left=m_left,
        plot_bottom=plot_bottom,
        inner_w=inner_w,
        inner_h=inner_h,
        ticks=y_ticks,
        domain_max=bar_max,
        fmt=lambda t: _format_axis_tick(t) if t >= 1000 else str(int(round(t))),
        right_labels=[(p, f"{p:.0f}%", _hex(CUMULATIVE_LINE)) for p in (0, 25, 50, 75, 100)],
    )

    # Linha acumulada (%)
    canv.setStrokeColor(_hex(CUMULATIVE_LINE))
    canv.setLineWidth(1.5)
    path = canv.beginPath()
    for i, pct in enumerate(cumulative_pct):
        x = m_left + i * slot_w + slot_w / 2
        y = _y_at_value(pct, 100.0, plot_bottom, inner_h)
        if i == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
    canv.drawPath(path, stroke=1, fill=0)

    for i, pct in enumerate(cumulative_pct):
        x = m_left + i * slot_w + slot_w / 2
        y = _y_at_value(pct, 100.0, plot_bottom, inner_h)
        canv.setFillColor(_hex(CUMULATIVE_LINE))
        canv.circle(x, y, 2.5, stroke=0, fill=1)

    # Barras (base no eixo X, crescimento para cima)
    for i, label in enumerate(labels):
        slot_x = m_left + i * slot_w + slot_w / 2
        value = bar_values[i] if i < len(bar_values) else 0.0
        bar_h = _scale_linear(value, bar_max, inner_h)
        color = bar_colors[i] if i < len(bar_colors) else ABC_CLASS_COLORS["C"]
        canv.setFillColor(_hex(color))
        canv.roundRect(
            slot_x - bar_w / 2,
            plot_bottom,
            bar_w,
            max(0.0, bar_h),
            2,
            stroke=0,
            fill=1,
        )
        canv.setFillColor(LABEL_COLOR)
        canv.setFont("Helvetica", 6)
        canv.drawCentredString(slot_x, 8, _truncate_label(label))


def _line_chart(
    canv: Any,
    width: float,
    height: float,
    *,
    labels: list[str],
    series: list[tuple[str, str, list[float]]],
    y_max: float = 100.0,
    y_suffix: str = "%",
) -> None:
    m_left, m_right, m_top, m_bottom = 52.0, 16.0, 16.0, 36.0
    inner_w = width - m_left - m_right
    inner_h = height - m_top - m_bottom
    plot_bottom = m_bottom
    n = max(1, len(labels))
    step_x = inner_w / max(1, n - 1)

    y_ticks = [t for t in (0, 25, 50, 75, 100) if t <= y_max]
    _draw_grid_h(
        canv,
        left=m_left,
        plot_bottom=plot_bottom,
        inner_w=inner_w,
        inner_h=inner_h,
        ticks=y_ticks,
        domain_max=y_max,
        fmt=lambda t: f"{int(t)}{y_suffix}",
    )

    for name, color, values in series:
        canv.setStrokeColor(_hex(color))
        canv.setLineWidth(1.5)
        path = canv.beginPath()
        for i, v in enumerate(values):
            x = m_left + i * step_x
            y = _y_at_value(v, y_max, plot_bottom, inner_h)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        canv.drawPath(path, stroke=1, fill=0)
        for i, v in enumerate(values):
            x = m_left + i * step_x
            y = _y_at_value(v, y_max, plot_bottom, inner_h)
            canv.setFillColor(_hex(color))
            canv.circle(x, y, 2.5, stroke=0, fill=1)

    canv.setFillColor(LABEL_COLOR)
    canv.setFont("Helvetica", 6)
    for i, label in enumerate(labels):
        x = m_left + i * step_x
        canv.drawCentredString(x, 8, _truncate_label(label, 8))


def _stacked_bar_chart(
    canv: Any,
    width: float,
    height: float,
    *,
    period_labels: list[str],
    stacks: list[tuple[str, str, list[float]]],
    reference_values: list[float] | None = None,
) -> None:
    m_left, m_right, m_top, m_bottom = 52.0, 16.0, 16.0, 36.0
    inner_w = width - m_left - m_right
    inner_h = height - m_top - m_bottom
    plot_bottom = m_bottom
    n = max(1, len(period_labels))
    slot_w = inner_w / n
    bar_w = min(40.0, slot_w * 0.7)

    stacked_totals = [
        sum(stack[2][i] if i < len(stack[2]) else 0.0 for stack in stacks)
        for i in range(n)
    ]
    ref_max = max(reference_values or [0.0], default=0.0)
    data_max = max(1.0, max(stacked_totals, default=0.0), ref_max)
    y_max = _nice_ceil(data_max * 1.1)
    y_ticks = [y_max * f for f in (0.0, 0.25, 0.5, 0.75, 1.0)]

    _draw_grid_h(
        canv,
        left=m_left,
        plot_bottom=plot_bottom,
        inner_w=inner_w,
        inner_h=inner_h,
        ticks=y_ticks,
        domain_max=y_max,
        fmt=_format_axis_tick,
    )

    # Barras empilhadas primeiro; linha de referência por cima (sem cobrir faixas)
    for i, label in enumerate(period_labels):
        slot_x = m_left + i * slot_w + slot_w / 2
        segments = _stack_segments_for_bar(
            stacks,
            i,
            y_max=y_max,
            plot_bottom=plot_bottom,
            inner_h=inner_h,
        )
        if segments:
            _draw_stacked_bar(canv, slot_x=slot_x, bar_w=bar_w, segments=segments)
        canv.setFillColor(LABEL_COLOR)
        canv.setFont("Helvetica", 6)
        canv.drawCentredString(slot_x, 8, str(label))

    if reference_values:
        canv.setStrokeColor(_hex(HIST_REF_BDI))
        canv.setLineWidth(1.5)
        canv.setDash(5, 4)
        path = canv.beginPath()
        started = False
        for i, value in enumerate(reference_values):
            if value <= 0:
                continue
            slot_x = m_left + i * slot_w + slot_w / 2
            y = _y_at_value(value, y_max, plot_bottom, inner_h)
            if not started:
                path.moveTo(slot_x, y)
                started = True
            else:
                path.lineTo(slot_x, y)
        if started:
            canv.drawPath(path, stroke=1, fill=0)
        canv.setDash()
        for i, value in enumerate(reference_values):
            if value <= 0:
                continue
            slot_x = m_left + i * slot_w + slot_w / 2
            y = _y_at_value(value, y_max, plot_bottom, inner_h)
            canv.setFillColor(_hex(HIST_REF_BDI))
            canv.setStrokeColor(colors.white)
            canv.setLineWidth(0.75)
            canv.circle(slot_x, y, 3, stroke=1, fill=1)


def build_analytics_chart_flowable(
    doc_type: str,
    roots: list[BudgetItem],
    *,
    meta: BudgetProjectMetadata,
    schedule: ProjectSchedule | None,
    width: float,
) -> tuple[AnalyticsChartFlowable | None, bool]:
    """Retorna (flowable, include_bdi_ref) para legenda do histograma."""
    key = doc_type.strip().lower()
    if key == "curva_abc":
        return _build_abc_chart(roots, width), False
    if key == "curva_s":
        return _build_s_curve_chart(roots, schedule, width), False
    if key == "histograma":
        chart, include_bdi = _build_histogram_chart(roots, meta, schedule, width)
        return chart, include_bdi
    return None, False


def analytics_chart_legend(doc_type: str, *, include_bdi_ref: bool = True) -> list[tuple[str, str]]:
    key = doc_type.strip().lower()
    if key == "curva_abc":
        return [
            ("Valor por serviço (barras)", ABC_CLASS_COLORS["A"]),
            ("A — até 80% acum.", ABC_CLASS_COLORS["A"]),
            ("B — até 95% acum.", ABC_CLASS_COLORS["B"]),
            ("C — restante", ABC_CLASS_COLORS["C"]),
            ("% acumulado (linha)", CUMULATIVE_LINE),
        ]
    if key == "curva_s":
        return [
            ("Avanço físico acumulado", SCURVE_PHYSICAL),
            ("Desembolso financeiro acumulado", SCURVE_FINANCIAL),
        ]
    if key == "histograma":
        items = [
            ("Insumos", HIST_STACK_COLORS["insumo"]),
            ("Equipamentos", HIST_STACK_COLORS["equipamento"]),
            ("Mão de obra", HIST_STACK_COLORS["mao_obra"]),
        ]
        if include_bdi_ref:
            items.append(("Ref. com BDI (tracejado)", HIST_REF_BDI))
        return items
    return []


def analytics_chart_caption(doc_type: str) -> str:
    key = doc_type.strip().lower()
    if key == "curva_abc":
        return "Gráfico: top 20 serviços · barras = valor · linha azul = % acumulado"
    if key == "curva_s":
        return "Evolução mensal acumulada — físico (verde) e financeiro (azul)"
    if key == "histograma":
        return "Eixo horizontal: dia acumulado da obra · Eixo vertical: custo (R$) · linha tracejada = referência com BDI"
    return ""


def _build_abc_chart(roots: list[BudgetItem], width: float) -> AnalyticsChartFlowable | None:
    items = build_abc_curve(roots)
    if not items:
        return None
    top: list[AbcItem] = items[:20]

    def render(canv: Any, w: float, h: float) -> None:
        _pareto_chart(
            canv,
            w,
            h,
            labels=[i.code for i in top],
            bar_values=[i.value for i in top],
            cumulative_pct=[i.cumulative_pct for i in top],
            bar_colors=[ABC_CLASS_COLORS[i.abc_class] for i in top],
        )

    return AnalyticsChartFlowable(width, CHART_HEIGHT, render)


def _build_s_curve_chart(
    roots: list[BudgetItem],
    schedule: ProjectSchedule | None,
    width: float,
) -> AnalyticsChartFlowable | None:
    if not schedule or not schedule.project_start:
        return None
    months, total_financial, _ = build_schedule_curves_by_month(schedule, flatten_budget_items(roots))
    if not months:
        return None
    fin_denom = total_financial if total_financial > 0 else 1.0
    labels = [m.label for m in months]
    physical = [m.physical_cumulative_pct for m in months]
    financial = [(m.financial_cumulative / fin_denom) * 100 for m in months]

    def render(canv: Any, w: float, h: float) -> None:
        _line_chart(
            canv,
            w,
            h,
            labels=labels,
            series=[
                ("Físico", SCURVE_PHYSICAL, physical),
                ("Financeiro", SCURVE_FINANCIAL, financial),
            ],
        )

    return AnalyticsChartFlowable(width, CHART_HEIGHT, render)


def _build_histogram_chart(
    roots: list[BudgetItem],
    meta: BudgetProjectMetadata,
    schedule: ProjectSchedule | None,
    width: float,
) -> tuple[AnalyticsChartFlowable | None, bool]:
    months, _, _, _, _, total_bdi = build_stacked_histogram(roots, meta, schedule)
    if not months or not any(m.total > 0 for m in months):
        return None, False

    period_labels = [str(m.period_day) for m in months]
    stacks = [
        ("insumo", HIST_STACK_COLORS["insumo"], [m.insumo for m in months]),
        ("equipamento", HIST_STACK_COLORS["equipamento"], [m.equipamento for m in months]),
        ("mao_obra", HIST_STACK_COLORS["mao_obra"], [m.mao_obra for m in months]),
    ]
    include_bdi = total_bdi > 0
    ref = [m.total_with_bdi for m in months] if include_bdi else None

    def render(canv: Any, w: float, h: float) -> None:
        _stacked_bar_chart(
            canv,
            w,
            h,
            period_labels=period_labels,
            stacks=stacks,
            reference_values=ref,
        )

    return AnalyticsChartFlowable(width, CHART_HEIGHT, render), include_bdi
