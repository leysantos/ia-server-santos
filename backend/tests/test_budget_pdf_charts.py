"""Testes dos gráficos analíticos em PDF."""

from __future__ import annotations

from pricing.budget.budget_analytics import build_abc_curve
from pricing.budget.budget_pdf_charts import (
    analytics_chart_legend,
    build_analytics_chart_flowable,
)
from pricing.budget.ppd_template import create_empty_ppd_metadata
from pricing.budget.budget_session import SESSION_STORE
from pricing.models.budget_item import BudgetItem, BudgetItemType
from pricing.models.budget_metadata import BudgetProjectMetadata
from pricing.schedule.schedule_models import ProjectSchedule, ScheduleTask


def _sample_session():
    meta = create_empty_ppd_metadata(projeto="Obra ABC")
    etapa = BudgetItem(
        code="1.0",
        name="ETAPA GERAL",
        item_type=BudgetItemType.GROUP,
        row_type="ETAPA",
        level=0,
        quantity=0,
        unit="",
        unit_price=0,
        total_price=1000.0,
    )
    servico = BudgetItem(
        code="1.1",
        name="Serviço teste",
        item_type=BudgetItemType.COMPOSITION,
        row_type="S",
        level=1,
        quantity=10.0,
        unit="m²",
        unit_price=100.0,
        total_price=1000.0,
    )
    servico.metadata["total_effective"] = 1000.0
    etapa.children = [servico]
    return SESSION_STORE.create(roots=[etapa], title="Obra ABC", intent={}, project=meta)


def _session_with_schedule():
    session = _sample_session()
    servico = session.roots[0].children[0]
    session.schedule = ProjectSchedule(
        project_start="2026-06-01",
        project_end="2026-12-31",
        tasks=[
            ScheduleTask(
                task_id="t1",
                budget_row_id=servico.row_id,
                budget_code="1.1",
                name=servico.name,
                row_type="S",
                duration_days=30,
                early_start="2026-06-01",
                early_finish="2026-06-30",
            )
        ],
    )
    return session


def _meta(session) -> BudgetProjectMetadata:
    p = session.project
    if isinstance(p, BudgetProjectMetadata):
        return p
    return BudgetProjectMetadata.from_dict(p or {})


def test_abc_chart_flowable_from_session():
    session = _sample_session()
    meta = _meta(session)
    chart, include_bdi = build_analytics_chart_flowable(
        "curva_abc",
        session.roots,
        meta=meta,
        schedule=session.schedule,
        width=720,
    )
    assert chart is not None
    assert chart.width == 720
    assert chart.height > 0
    assert include_bdi is False
    assert len(analytics_chart_legend("curva_abc")) >= 4


def test_abc_chart_none_when_empty():
    meta = create_empty_ppd_metadata()
    chart, _ = build_analytics_chart_flowable(
        "curva_abc",
        [],
        meta=meta,
        schedule=None,
        width=720,
    )
    assert chart is None


def test_s_curve_chart_with_schedule():
    session = _session_with_schedule()
    meta = _meta(session)
    chart, _ = build_analytics_chart_flowable(
        "curva_s",
        session.roots,
        meta=meta,
        schedule=session.schedule,
        width=720,
    )
    assert chart is not None


def test_build_abc_curve_has_items():
    session = _sample_session()
    items = build_abc_curve(session.roots)
    assert len(items) >= 1


def test_y_at_value_grows_upward_from_plot_bottom():
    from pricing.budget.budget_pdf_charts import _y_at_value

    plot_bottom = 36.0
    inner_h = 113.0
    y_zero = _y_at_value(0, 100, plot_bottom, inner_h)
    y_half = _y_at_value(50, 100, plot_bottom, inner_h)
    y_full = _y_at_value(100, 100, plot_bottom, inner_h)
    assert y_zero == plot_bottom
    assert y_half > y_zero
    assert y_full == plot_bottom + inner_h


def test_stack_segments_tile_without_overlap():
    from pricing.budget.budget_pdf_charts import _stack_segments_for_bar

    stacks = [
        ("insumo", "#10b981", [100.0]),
        ("equipamento", "#f59e0b", [50.0]),
        ("mao_obra", "#38bdf8", [30.0]),
    ]
    segs = _stack_segments_for_bar(
        stacks, 0, y_max=200.0, plot_bottom=36.0, inner_h=113.0
    )
    assert len(segs) == 3
    for i in range(len(segs) - 1):
        _, y_base, h = segs[i]
        _, y_next, _ = segs[i + 1]
        assert abs((y_base + h) - y_next) < 0.02
