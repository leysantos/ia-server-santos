from __future__ import annotations

import io
from typing import Any

from pricing.budget.ppd_layout import (
    COL_DESCRIPTION,
    COL_ITEM,
    COL_QUANTITY,
    COL_ROW_TYPE,
    COL_SOURCE_CODE,
    COL_TOTAL_COMD,
    COL_TOTAL_SEMD,
    COL_UNIT,
    COL_UNIT_COST_COMD,
    COL_UNIT_COST_SEMD,
    COL_UNIT_PRICE_BDI_COMD,
    COL_UNIT_PRICE_BDI_SEMD,
    ROW_TYPE_ETAPA,
    ROW_TYPE_SERVICO,
    ROW_TYPE_SUB_ETAPA,
)
from pricing.models.budget_item import BudgetItem
from pricing.models.budget_metadata import BudgetProjectMetadata


def export_ppd_xlsx(
    roots: list[BudgetItem],
    metadata: BudgetProjectMetadata | None = None,
) -> bytes:
    """Exporta no layout PPD municipal (PLANILHA + MCQ)."""
    try:
        import openpyxl
    except ImportError as exc:
        raise ImportError("openpyxl necessário") from exc

    meta = metadata or BudgetProjectMetadata()
    wb = openpyxl.Workbook()

    ws_plan = wb.active
    ws_plan.title = "PLANILHA"
    ws_mcq = wb.create_sheet("MCQ")

    for ws in (ws_plan, ws_mcq):
        _write_ppd_header(ws, meta)
        _write_ppd_column_headers(ws, meta)
        row_idx = 21
        for root in roots:
            row_idx = _write_ppd_tree(ws, root, row_idx, meta)

        total = sum(r.total_price for r in roots)
        total_semd = sum(r.total_price_semd for r in roots)
        total_effective = sum(r.effective_total() for r in roots)
        ws.cell(row=row_idx + 1, column=COL_TOTAL_COMD + 1, value=round(total, 2))
        ws.cell(row=row_idx + 1, column=COL_TOTAL_SEMD + 1, value=round(total_semd, 2))
        ws.cell(row=row_idx + 2, column=COL_DESCRIPTION + 1, value="TOTAL EFETIVO (MENOR CUSTO)")
        ws.cell(row=row_idx + 2, column=COL_TOTAL_COMD + 1, value=round(total_effective, 2))

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _write_ppd_header(ws, meta: BudgetProjectMetadata) -> None:
    ws.cell(row=6, column=10, value=meta.orgao or "SEMINF")
    ws.cell(row=11, column=8, value="PROJETO:")
    ws.cell(row=11, column=9, value=meta.projeto)
    ws.cell(row=12, column=8, value="OBJETO:")
    ws.cell(row=12, column=9, value=meta.objeto)
    ws.cell(row=13, column=8, value="LOCAL:")
    ws.cell(row=13, column=9, value=meta.local)
    ws.cell(row=14, column=8, value="ORÇAMENTO:")
    ws.cell(row=14, column=9, value=meta.orcamento)
    ws.cell(row=14, column=15, value=meta.obra_type)
    ws.cell(row=16, column=8, value=f"BASE DE PREÇO UTILIZADA: {meta.base_preco}")
    ws.cell(row=18, column=10, value="MEMÓRIA DE CÁLCULO")
    ws.cell(row=18, column=15, value=0)
    ws.cell(row=18, column=14, value=meta.bdi.rate_com_desoneracao)
    ws.cell(row=18, column=18, value=meta.bdi.rate_sem_desoneracao)


def _write_ppd_column_headers(ws, meta: BudgetProjectMetadata) -> None:
    headers = {
        COL_ROW_TYPE + 1: "TIPO",
        COL_ITEM + 1: "ITEM",
        COL_SOURCE_CODE + 1: "CÓDIGO",
        COL_DESCRIPTION + 1: "DESCRIÇÃO",
        COL_UNIT + 1: "UNID",
        COL_QUANTITY + 1: "QUANT",
        COL_UNIT_COST_COMD + 1: "CUSTO UNIT. (R$) COM D",
        COL_UNIT_PRICE_BDI_COMD + 1: f"PREÇO UNIT. COM BDI DE {meta.bdi.rate_com_desoneracao:.2%}",
        COL_TOTAL_COMD + 1: "TOTAL COM BDI (R$)",
        COL_UNIT_COST_SEMD + 1: "CUSTO UNIT. (R$) SEM D",
        COL_UNIT_PRICE_BDI_SEMD + 1: f"PREÇO UNIT. COM BDI DE {meta.bdi.rate_sem_desoneracao:.2%}",
        COL_TOTAL_SEMD + 1: "TOTAL COM BDI (R$)",
    }
    for col, label in headers.items():
        ws.cell(row=19, column=col, value=label)


def _write_ppd_tree(ws, item: BudgetItem, row_idx: int, meta: BudgetProjectMetadata) -> int:
    if item.metadata.get("is_memory_row"):
        ws.cell(row=row_idx, column=COL_DESCRIPTION + 1, value=item.calculation_note or item.name)
        return row_idx + 1

    is_etapa = item.row_type == ROW_TYPE_ETAPA or (item.item_type.value == "group" and item.level == 0)
    is_sub = item.row_type == ROW_TYPE_SUB_ETAPA

    if is_etapa or is_sub:
        ws.cell(row=row_idx, column=COL_ROW_TYPE + 1, value=ROW_TYPE_ETAPA if is_etapa else ROW_TYPE_SUB_ETAPA)
        ws.cell(row=row_idx, column=COL_ITEM + 1, value=item.code)
        ws.cell(row=row_idx, column=COL_DESCRIPTION + 1, value=item.name)
        ws.cell(row=row_idx, column=COL_TOTAL_COMD + 1, value=item.total_price or None)
        row_idx += 1
        for child in item.children:
            row_idx = _write_ppd_tree(ws, child, row_idx, meta)
        return row_idx

    ws.cell(row=row_idx, column=COL_ROW_TYPE + 1, value=ROW_TYPE_SERVICO)
    ws.cell(row=row_idx, column=COL_ITEM + 1, value=item.code)
    ws.cell(row=row_idx, column=COL_SOURCE_CODE + 1, value=item.source_code)
    ws.cell(row=row_idx, column=COL_DESCRIPTION + 1, value=item.name)
    ws.cell(row=row_idx, column=COL_UNIT + 1, value=item.unit)
    ws.cell(row=row_idx, column=COL_QUANTITY + 1, value=item.quantity or None)
    ws.cell(row=row_idx, column=COL_UNIT_COST_COMD + 1, value=item.unit_cost or None)
    ws.cell(row=row_idx, column=COL_UNIT_PRICE_BDI_COMD + 1, value=item.unit_price or None)
    ws.cell(row=row_idx, column=COL_TOTAL_COMD + 1, value=item.total_price or None)
    ws.cell(row=row_idx, column=COL_UNIT_COST_SEMD + 1, value=item.unit_cost_semd or None)
    ws.cell(row=row_idx, column=COL_UNIT_PRICE_BDI_SEMD + 1, value=item.unit_price_semd or None)
    ws.cell(row=row_idx, column=COL_TOTAL_SEMD + 1, value=item.total_price_semd or None)
    ws.cell(row=row_idx, column=13, value="BDI1")

    row_idx += 1
    for child in item.children:
        if child.metadata.get("is_memory_row") or child.row_type == "MEMORIA":
            ws.cell(row=row_idx, column=COL_DESCRIPTION + 1, value=child.calculation_note or child.name)
            row_idx += 1
        else:
            row_idx = _write_ppd_tree(ws, child, row_idx, meta)

    if item.calculation_note and not any(
        c.metadata.get("is_memory_row") for c in item.children
    ):
        ws.cell(row=row_idx, column=COL_DESCRIPTION + 1, value=item.calculation_note)
        row_idx += 1

    return row_idx
