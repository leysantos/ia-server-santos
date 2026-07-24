"""Parser hierárquico de PDF de orçamento (etapas, sub-etapas, composições)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from pricing.budget.price_matching_import import (
    ImportedPriceRow,
    _PDF_DESC_UNIT_ROW,
    _PDF_FULL_ROW,
    _PDF_ITEM_DESC,
    _PDF_UNIT_QTY_ONLY,
    _ITEM_RE,
    _cell_str,
    _detect_columns,
    _find_header_row,
    _item_from_excel_cell,
    _normalize_header,
    _normalize_unit,
    _parse_quantity,
    _should_skip_pdf_line,
)


class ImportRowKind(str, Enum):
    ETAPA = "ETAPA"
    SUB_ETAPA = "SUB_ETAPA"
    SERVICO = "SERVICO"


@dataclass
class ImportedBudgetLine:
    item: str
    descricao: str
    unidade: str = ""
    quantidade: float = 0.0
    codigo: str = ""
    row_type: str = ImportRowKind.SERVICO.value
    row_index: int = 0
    incomplete: bool = False

    def to_price_row(self) -> ImportedPriceRow:
        return ImportedPriceRow(
            item=self.item,
            descricao=self.descricao,
            unidade=self.unidade,
            quantidade=self.quantidade,
            row_index=self.row_index,
            codigo=self.codigo,
        )


def _item_depth(code: str) -> int:
    return code.count(".") + 1


def _parent_item_code(code: str) -> str | None:
    if "." not in code:
        return None
    return code.rsplit(".", 1)[0]


def _classify_row_type(item: str, line: str) -> str:
    """Classifica etapa/sub-etapa/serviço pela numeração e presença de und/qtd."""
    if _PDF_FULL_ROW.match(line) or _PDF_UNIT_QTY_ONLY.match(line) or _PDF_DESC_UNIT_ROW.match(line):
        return ImportRowKind.SERVICO.value
    depth = _item_depth(item)
    if depth == 1:
        return ImportRowKind.ETAPA.value
    if depth == 2:
        return ImportRowKind.SUB_ETAPA.value
    return ImportRowKind.SERVICO.value


def _parse_service_columns(line: str) -> ImportedBudgetLine | None:
    """Extrai item, descrição, unidade e quantidade de linhas de composição."""
    m = _PDF_FULL_ROW.match(line)
    if m:
        return ImportedBudgetLine(
            item=m.group(1),
            descricao=m.group(2).strip(),
            unidade=_normalize_unit(m.group(3)),
            quantidade=_parse_quantity(m.group(4)) or 0.0,
            row_type=ImportRowKind.SERVICO.value,
        )

    m = _PDF_UNIT_QTY_ONLY.match(line)
    if m:
        item, unit, qty_raw = m.group(1), m.group(2), m.group(3)
        return ImportedBudgetLine(
            item=item,
            descricao=f"[Completar descrição — item {item}]",
            unidade=_normalize_unit(unit),
            quantidade=_parse_quantity(qty_raw) or 0.0,
            row_type=ImportRowKind.SERVICO.value,
            incomplete=True,
        )

    m = _PDF_DESC_UNIT_ROW.match(line)
    if m:
        return ImportedBudgetLine(
            item=m.group(1),
            descricao=m.group(2).strip(),
            unidade=_normalize_unit(m.group(3)),
            quantidade=0.0,
            row_type=ImportRowKind.SERVICO.value,
        )

    return None


def classify_budget_line(line: str) -> ImportedBudgetLine | None:
    line = re.sub(r"\s+", " ", line.strip())
    if _should_skip_pdf_line(line):
        return None

    service = _parse_service_columns(line)
    if service:
        return service

    m = _PDF_ITEM_DESC.match(line)
    if not m:
        return None

    item, rest = m.group(1), m.group(2).strip()
    row_type = _classify_row_type(item, line)

    if row_type == ImportRowKind.SERVICO.value and len(rest) >= 4:
        return ImportedBudgetLine(
            item=item,
            descricao=rest,
            unidade="",
            quantidade=0.0,
            row_type=row_type,
            incomplete=True,
        )

    if row_type in (ImportRowKind.ETAPA.value, ImportRowKind.SUB_ETAPA.value):
        return ImportedBudgetLine(
            item=item,
            descricao=rest,
            row_type=row_type,
        )

    return None


def parse_pdf_hierarchy(path: Path) -> list[ImportedBudgetLine]:
    from core.knowledge.pdf_text_extractor import extract_pdf_pages

    pages = extract_pdf_pages(path, use_ocr=True)
    if not pages:
        raise ValueError(
            "Não foi possível extrair texto do PDF. "
            "Use PDF pesquisável ou instale Tesseract para OCR."
        )

    text = "\n".join(t for _, t in pages)
    out: list[ImportedBudgetLine] = []
    seen: set[str] = set()
    row_index = 0

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parsed = classify_budget_line(line)
        if not parsed:
            continue
        key = f"{parsed.row_type}|{parsed.item}|{parsed.descricao[:60]}|{parsed.unidade}|{parsed.quantidade}"
        if key in seen:
            continue
        seen.add(key)
        parsed.row_index = row_index
        out.append(parsed)
        row_index += 1

    if not out:
        raise ValueError("Nenhuma linha reconhecida no PDF")

    return out


def classify_excel_row(item: str, unidade: str, quantidade: float) -> tuple[str, bool]:
    """Classifica linha Excel: etapa, sub-etapa ou composição (serviço)."""
    item = item.strip()
    if not item or not _ITEM_RE.match(item):
        return "", True
    unit = (unidade or "").strip()
    qty = float(quantidade or 0)
    if unit or qty > 0:
        return ImportRowKind.SERVICO.value, False
    depth = _item_depth(item)
    if depth == 1:
        return ImportRowKind.ETAPA.value, False
    return ImportRowKind.SUB_ETAPA.value, False


def parse_excel_hierarchy(path: Path) -> list[ImportedBudgetLine]:
    """Importa planilha Excel (.xlsx) preservando etapas, sub-etapas e composições."""
    try:
        import openpyxl
    except ImportError as exc:
        raise ImportError("openpyxl necessário para importar Excel") from exc

    wb = openpyxl.load_workbook(path, read_only=True, data_only=False)
    ws = wb.active
    header_row_num, cols = _find_header_row(ws)

    if "item" not in cols:
        wb.close()
        raise ValueError("Coluna Item não encontrada na planilha")

    out: list[ImportedBudgetLine] = []
    row_index = 0
    item_col = cols["item"]
    for excel_row in ws.iter_rows(min_row=header_row_num + 1):
        cells = [c.value for c in excel_row]
        if not any(c is not None and str(c).strip() for c in cells):
            continue

        desc = _cell_str(cells, cols.get("descricao"))
        if not desc:
            continue
        desc_norm = _normalize_header(desc)
        if desc_norm in ("descricao", "descricao do servico", "servico"):
            continue

        item_cell = excel_row[item_col] if item_col < len(excel_row) else None
        item = _item_from_excel_cell(
            item_cell.value if item_cell is not None else None,
            item_cell.number_format if item_cell is not None else None,
        )
        if not item or _normalize_header(item) == "item":
            continue
        if not _ITEM_RE.match(item):
            continue

        codigo = _cell_str(cells, cols.get("codigo"))
        unit_raw = _cell_str(cells, cols.get("unidade"))
        unit = _normalize_unit(unit_raw) if unit_raw else ""
        qty_idx = cols.get("quantidade")
        qty_raw = cells[qty_idx] if qty_idx is not None and qty_idx < len(cells) else None
        qty = _parse_quantity(qty_raw)
        if qty is None:
            qty = 0.0

        tipo_raw = _cell_str(cells, cols.get("tipo")).upper()
        if tipo_raw in ("ETAPA", "SUB_ETAPA", "SUB-ETAPA", "SUBETAPA", "SERVICO", "SERVIÇO"):
            row_type = "SUB_ETAPA" if "SUB" in tipo_raw else ("ETAPA" if tipo_raw == "ETAPA" else "SERVICO")
            incomplete = False
        else:
            row_type, incomplete = classify_excel_row(item, unit, qty)
            if not row_type:
                continue

        out.append(
            ImportedBudgetLine(
                item=item,
                descricao=desc,
                unidade=unit,
                quantidade=qty,
                codigo=codigo,
                row_type=row_type,
                row_index=row_index,
                incomplete=incomplete,
            )
        )
        row_index += 1

    wb.close()
    if not out:
        raise ValueError("Nenhuma linha reconhecida na planilha Excel")
    return out


def hierarchy_stats(lines: list[ImportedBudgetLine]) -> dict[str, int]:
    return {
        "etapas": sum(1 for l in lines if l.row_type == ImportRowKind.ETAPA.value),
        "sub_etapas": sum(1 for l in lines if l.row_type == ImportRowKind.SUB_ETAPA.value),
        "servicos": sum(1 for l in lines if l.row_type == ImportRowKind.SERVICO.value),
        "total": len(lines),
    }
