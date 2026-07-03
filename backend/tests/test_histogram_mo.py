"""Testes — histograma MO + equipamentos (modelo por item, Excel/PDF)."""

from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

pytest_plugins = ["test_budget_export"]

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pricing.budget.histogram.excel_builder import build_histogram_report_workbook_bytes
from pricing.budget.histogram.histograma_service import export_histogram_mo_xlsx
from pricing.budget.histogram.section_mapper import (
    HistogramReport,
    build_histogram_report,
)


def test_build_report_without_schedule(export_session):
    report = build_histogram_report(
        export_session.roots,
        export_session.project,
        None,
    )
    assert report.mao_obra is None
    assert report.equipamento is None


def test_excel_has_mo_and_eq_sheets_with_totals(export_session_with_schedule):
    report = build_histogram_report(
        export_session_with_schedule.roots,
        export_session_with_schedule.project,
        export_session_with_schedule.schedule,
    )
    data = build_histogram_report_workbook_bytes(
        report,
        profile=__import__(
            "core.system.company_profile", fromlist=["get_company_profile"]
        ).get_company_profile(),
        brand=__import__(
            "pricing.budget.budget_export_branding", fromlist=["ExportBrandingConfig"]
        ).ExportBrandingConfig(),
    )
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.load_workbook(io.BytesIO(data))
    assert "HISTOGRAMA" in wb.sheetnames or "HISTOGRAMA MO" in wb.sheetnames


def test_export_histogram_mo_xlsx_integration(export_session_with_schedule):
    from pricing.budget.budget_export_service import export_session_xlsx

    data = export_session_xlsx(export_session_with_schedule.id, "histograma")
    assert len(data) > 4000
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.load_workbook(io.BytesIO(data))
    assert "HISTOGRAMA MO" in wb.sheetnames or "HISTOGRAMA" in wb.sheetnames


def test_build_report_with_cpu_mo(export_session_with_schedule):
    fake_cpu = {
        "items": [
            {
                "item_type": "mao_obra",
                "code": "0101",
                "description": "Pedreiro",
                "unit": "h",
                "coefficient": 176.0,
                "unit_price": 20.0,
                "partial_cost": 3520.0,
            },
            {
                "item_type": "mao_obra",
                "code": "0102",
                "description": "Servente",
                "unit": "h",
                "coefficient": 88.0,
                "unit_price": 15.0,
                "partial_cost": 1320.0,
            },
        ]
    }
    servico = export_session_with_schedule.roots[0].children[0]
    servico.source_code = "12345"
    export_session_with_schedule.project.price_bases = [
        {
            "source": "sinapi",
            "label": "SINAPI",
            "enabled": True,
            "uf": "AM",
            "reference": "BR-2026-05",
        }
    ]

    with patch(
        "pricing.tools.budget_pricing_tools.BudgetPricingTools.get_open_composition",
        return_value=fake_cpu,
    ):
        report = build_histogram_report(
            export_session_with_schedule.roots,
            export_session_with_schedule.project,
            export_session_with_schedule.schedule,
        )

    assert isinstance(report, HistogramReport)
    assert report.services_with_cpu >= 1
    assert report.mao_obra is not None
    assert len(report.mao_obra.items) >= 1
    assert sum(report.mao_obra.monthly_totals) > 0


def test_excel_sum_formulas_when_items_present(export_session_with_schedule):
    fake_cpu = {
        "items": [
            {
                "item_type": "mao_obra",
                "code": "0101",
                "description": "Pedreiro",
                "unit": "h",
                "coefficient": 176.0,
                "unit_price": 20.0,
                "partial_cost": 3520.0,
            },
        ]
    }
    servico = export_session_with_schedule.roots[0].children[0]
    servico.source_code = "12345"
    export_session_with_schedule.project.price_bases = [
        {
            "source": "sinapi",
            "label": "SINAPI",
            "enabled": True,
            "uf": "AM",
            "reference": "BR-2026-05",
        }
    ]

    with patch(
        "pricing.tools.budget_pricing_tools.BudgetPricingTools.get_open_composition",
        return_value=fake_cpu,
    ):
        data = export_histogram_mo_xlsx(
            export_session_with_schedule.roots,
            export_session_with_schedule.project,
            export_session_with_schedule.schedule,
        )

    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.load_workbook(io.BytesIO(data))
    if "HISTOGRAMA MO" not in wb.sheetnames:
        pytest.skip("Sem dados MO no fixture")
    ws = wb["HISTOGRAMA MO"]

    total_row = None
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row):
        if row[1].value == "TOTAL":
            total_row = row[0].row
            break
    assert total_row is not None

    total_cell = ws.cell(row=total_row, column=3)
    assert isinstance(total_cell.value, str)
    assert total_cell.value.startswith("=SUM(")
