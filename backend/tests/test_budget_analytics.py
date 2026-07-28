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
    # Item único com 100% acumulado cai em C (>95%); dois itens deixam o maior em A.
    etapa = session.roots[0]
    etapa.children.append(
        BudgetItem(
            code="1.2",
            name="Serviço menor",
            item_type=BudgetItemType.COMPOSITION,
            row_type="S",
            level=1,
            quantity=1.0,
            unit="m²",
            unit_price=50.0,
            total_price=50.0,
        )
    )
    etapa.children[0].metadata["total_effective"] = 1000.0
    etapa.children[1].metadata["total_effective"] = 250.0
    items = build_abc_curve(session.roots)
    assert len(items) == 2
    assert items[0].abc_class == "A"
    assert abs(items[0].cumulative_pct - 80.0) < 0.1


def test_curva_abc_export_table_total_row():
    session = _sample_session()
    table = build_curva_abc_export_table(session.roots)
    assert table.headers[0] == "Item"
    assert table.rows[-1][2] == "TOTAL"
    assert 0 in table.center_cols
    assert 1 in table.center_cols
    assert 6 in table.center_cols
    assert 3 in table.right_cols
    assert len(table.rows) - 1 in table.bold_rows


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

    extra, body, table = build_curva_s_export_table(session.roots, schedule)
    assert extra and "Cenário adotado" in extra
    assert body and any("ComD" in line for line in body)
    assert body and any("SemD" in line for line in body)
    assert len(table.rows) >= 1


def test_curva_s_scenario_meta_adopted_semd():
    from pricing.budget.budget_analytics import (
        build_curva_s_desoneracao_meta,
        format_curva_s_scenario_block,
    )
    from pricing.budget.ppd_template import create_empty_ppd_metadata
    from pricing.models.budget_item import BudgetItem, BudgetItemType

    meta = create_empty_ppd_metadata()
    etapa = BudgetItem(
        code="1.0",
        name="ETAPA",
        item_type=BudgetItemType.GROUP,
        row_type="ETAPA",
        level=0,
        quantity=0,
        unit="",
        unit_price=0,
        total_price=1200.0,
        total_price_semd=1000.0,
    )
    scenario = build_curva_s_desoneracao_meta([etapa], meta, 1000.0)
    assert scenario.adopted_mode == "semd"
    extra, body = format_curva_s_scenario_block(scenario)
    assert "Sem desoneração" in extra
    assert "SemD" in extra
    assert any("Total adotado (SemD)" in line for line in body)


def _session_with_cpu_items(cpu_items: list[dict]):
    from unittest.mock import patch

    from pricing.budget.budget_export_tables import _EXPORT_COMPOSITION_CACHE

    _EXPORT_COMPOSITION_CACHE.clear()

    from pricing.budget.budget_analytics import build_insumos_export_table, build_mao_obra_export_table
    from pricing.budget.ppd_template import create_empty_ppd_metadata
    from pricing.models.budget_item import BudgetItem, BudgetItemType

    meta = create_empty_ppd_metadata(projeto="Obra Recursos")
    meta.price_bases = [
        {"source": "sinapi", "label": "SINAPI", "enabled": True, "uf": "AM", "reference": "BR-2026-05"}
    ]
    servico = BudgetItem(
        code="1.1",
        name="Serviço teste",
        item_type=BudgetItemType.COMPOSITION,
        row_type="S",
        level=1,
        quantity=10.0,
        unit="m²",
        unit_price=100.0,
        unit_cost=78.0,
        source_code="12345",
        total_price=1000.0,
    )
    servico.metadata["total_effective"] = 1000.0
    etapa = BudgetItem(
        code="1.0",
        name="ETAPA",
        item_type=BudgetItemType.GROUP,
        row_type="ETAPA",
        level=0,
        quantity=0,
        unit="",
        unit_price=0,
        total_price=1000.0,
        children=[servico],
    )
    fake_cpu = {"items": cpu_items}
    return meta, [etapa], fake_cpu, build_insumos_export_table, build_mao_obra_export_table


def test_insumos_export_table_totals():
    from unittest.mock import patch

    cpu_items = [
        {
            "item_type": "insumo",
            "code": "88316",
            "description": "Cimento Portland",
            "unit": "kg",
            "coefficient": 5.2,
            "unit_price": 1.5,
            "partial_cost": 7.8,
            "classificacao": "MATERIAL",
        },
        {
            "item_type": "insumo",
            "code": "40813",
            "description": "ENGENHEIRO CIVIL DE OBRA PLENO (MENSALISTA)",
            "unit": "MES",
            "coefficient": 0.5,
            "unit_price": 20000.0,
            "partial_cost": 10000.0,
        },
        {
            "item_type": "mao_obra",
            "code": "0101",
            "description": "Pedreiro",
            "unit": "h",
            "coefficient": 0.5,
            "unit_price": 20.0,
            "partial_cost": 10.0,
        },
    ]
    meta, roots, fake_cpu, build_insumos, _ = _session_with_cpu_items(cpu_items)
    with patch(
        "pricing.budget.composition_lookup.resolve_composition_detail",
        return_value=fake_cpu,
    ), patch(
        "pricing.tools.budget_pricing_tools.BudgetPricingTools.get_open_composition",
        return_value=fake_cpu,
    ):
        extra, table = build_insumos(roots, meta)

    assert extra and "Com desoneração" in extra
    assert table.headers[-1] == "Total linha (R$)"
    assert len(table.rows) == 4  # 1 insumo + 3 footer rows
    assert table.rows[0][1] == "88316"
    assert all("40813" not in str(cell) for row in table.rows[:-3] for cell in row)
    assert table.rows[-3][2] == "TOTAL SEM BDI"
    assert table.rows[-1][2] == "TOTAL COM BDI"


def test_mao_obra_export_table_totals():
    from unittest.mock import patch

    cpu_items = [
        {
            "item_type": "insumo",
            "code": "40813",
            "description": "ENGENHEIRO CIVIL DE OBRA PLENO (MENSALISTA)",
            "unit": "MES",
            "coefficient": 0.5,
            "unit_price": 20000.0,
            "partial_cost": 10000.0,
        },
        {
            "item_type": "mao_obra",
            "code": "0101",
            "description": "Pedreiro",
            "unit": "h",
            "coefficient": 0.5,
            "unit_price": 20.0,
            "partial_cost": 10.0,
        },
    ]
    meta, roots, fake_cpu, _, build_mao_obra = _session_with_cpu_items(cpu_items)
    with patch(
        "pricing.budget.composition_lookup.resolve_composition_detail",
        return_value=fake_cpu,
    ), patch(
        "pricing.tools.budget_pricing_tools.BudgetPricingTools.get_open_composition",
        return_value=fake_cpu,
    ):
        extra, table = build_mao_obra(roots, meta)

    assert extra
    codes = {row[1] for row in table.rows[:-3]}
    assert "40813" in codes
    assert "0101" in codes
    assert table.rows[-2][2] == "VALOR BDI"
    assert table.summary_rows == 3
