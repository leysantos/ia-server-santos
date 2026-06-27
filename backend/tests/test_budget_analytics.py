"""Testes das analíticas de orçamento (Curva ABC, S, Histograma)."""

from __future__ import annotations

from pricing.budget.budget_analytics import build_abc_curve, build_curva_abc_export_table
from pricing.budget.ppd_template import create_empty_ppd_metadata
from pricing.budget.budget_session import SESSION_STORE
from pricing.models.budget_item import BudgetItem, BudgetItemType
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


def test_build_abc_curve_classifies():
    session = _sample_session()
    items = build_abc_curve(session.roots)
    assert len(items) == 1
    assert items[0].abc_class == "A"
    assert abs(items[0].cumulative_pct - 100.0) < 0.01


def test_curva_abc_export_table_total_row():
    session = _sample_session()
    table = build_curva_abc_export_table(session.roots)
    assert table.headers[0] == "Item"
    assert table.rows[-1][2] == "TOTAL"


def test_curva_s_export_requires_schedule():
    session = _sample_session()
    from pricing.budget.budget_analytics import build_curva_s_export_table

    try:
        build_curva_s_export_table(session.roots, None)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "Cronograma" in str(exc)


def test_curva_s_export_with_schedule():
    session = _sample_session()
    servico = session.roots[0].children[0]
    schedule = ProjectSchedule(
        project_start="2026-06-01",
        project_end="2026-08-31",
        tasks=[
            ScheduleTask(
                task_id="t1",
                budget_row_id=servico.row_id,
                budget_code=servico.code,
                name=servico.name,
                row_type="S",
                duration_days=30,
                early_start="2026-06-01",
                early_finish="2026-06-30",
            )
        ],
    )
    from pricing.budget.budget_analytics import build_curva_s_export_table

    extra, table = build_curva_s_export_table(session.roots, schedule)
    assert extra and "Valor total" in extra
    assert len(table.rows) >= 1
