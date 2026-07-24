"""Importação de planilhas e PDFs para o módulo Lançar Preços."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_QTY_RE = re.compile(r"^[\d.,]+$")
_ITEM_RE = re.compile(r"^\d+(?:\.\d+)*$")
_ITEM_CODE_RE = re.compile(r"^\d+(?:\.\d+)*$")

# Unidades comuns em planilhas de orçamento (SEINFRA / SEMINF / SINAPI)
_UNIT_PATTERN = (
    r"(?:"
    r"m²|m2|m³|m3|"
    r"und|unid|un\.?|"
    r"h|kg|vb|cj|gl|t|m|%|"
    r"mes|mês|"
    r"ls|pc|pç|pct"
    r")"
)

_PDF_FULL_ROW = re.compile(
    rf"^(\d+(?:\.\d+)*)\s+(.+?)\s+({_UNIT_PATTERN})\s+([\d.,]+)\s*$",
    re.IGNORECASE,
)
_PDF_DESC_UNIT_ROW = re.compile(
    rf"^(\d+(?:\.\d+)*)\s+(.+?)\s+({_UNIT_PATTERN})\s*$",
    re.IGNORECASE,
)
_PDF_UNIT_QTY_ONLY = re.compile(
    rf"^(\d+(?:\.\d+)*)\s+({_UNIT_PATTERN})\s+([\d.,]+)\s*$",
    re.IGNORECASE,
)
_PDF_ITEM_DESC = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$")

_SKIP_LINE_PATTERNS = (
    re.compile(r"^planilha de servi", re.I),
    re.compile(r"^item\s+desc", re.I),
    re.compile(r"^reforma\s+", re.I),
    re.compile(r"^pagina\s+\d", re.I),
)


@dataclass
class ImportedPriceRow:
    item: str
    descricao: str
    unidade: str
    quantidade: float
    row_index: int = 0
    codigo: str = ""


def _normalize_header(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = (
        text.replace("ç", "c")
        .replace("ã", "a")
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("º", "o")
        .replace("ª", "a")
    )
    return re.sub(r"\s+", " ", text)


def _parse_quantity(raw: Any) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip()
    if not text:
        return None
    if text.count(",") == 1 and text.count(".") >= 1:
        text = text.replace(".", "").replace(",", ".")
    elif text.count(",") == 1:
        text = text.replace(",", ".")
    else:
        text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def _normalize_unit(unit: str) -> str:
    u = unit.strip().replace(".", "")
    low = u.lower()
    mapping = {
        "m2": "M²",
        "m²": "M²",
        "m3": "M³",
        "m³": "M³",
        "un": "UN",
        "und": "UN",
        "unid": "UN",
        "h": "H",
        "kg": "KG",
        "vb": "VB",
        "cj": "CJ",
        "gl": "GL",
        "t": "T",
        "m": "M",
        "mes": "Mês",
        "mês": "Mês",
        "ls": "LS",
        "pc": "PC",
        "pç": "PC",
        "pct": "PC",
    }
    return mapping.get(low, u.upper())


def _should_skip_pdf_line(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) < 3:
        return True
    for pat in _SKIP_LINE_PATTERNS:
        if pat.search(stripped):
            return True
    norm = _normalize_header(stripped)
    if norm in ("descricao", "descricao do servico", "servico", "item descricao und"):
        return True
    return False


def _parse_budget_pdf_line(line: str) -> ImportedPriceRow | None:
    """Parser para planilhas PDF de orçamento (formato ITEM DESCRIÇÃO UND QTD)."""
    line = re.sub(r"\s+", " ", line.strip())
    if _should_skip_pdf_line(line):
        return None

    m = _PDF_FULL_ROW.match(line)
    if m:
        return ImportedPriceRow(
            item=m.group(1),
            descricao=m.group(2).strip(),
            unidade=_normalize_unit(m.group(3)),
            quantidade=_parse_quantity(m.group(4)) or 0.0,
        )

    m = _PDF_DESC_UNIT_ROW.match(line)
    if m:
        desc = m.group(2).strip()
        if len(desc) < 4:
            return None
        return ImportedPriceRow(
            item=m.group(1),
            descricao=desc,
            unidade=_normalize_unit(m.group(3)),
            quantidade=0.0,
        )

    # Linha quebrada pelo OCR: "3.1 M3 11,19" (sem descrição) — ignorar
    if _PDF_UNIT_QTY_ONLY.match(line):
        return None

    m = _PDF_ITEM_DESC.match(line)
    if not m:
        return None

    item, desc = m.group(1), m.group(2).strip()
    if len(desc) < 4:
        return None
    # Ignora cabeçalhos de grupo curtos sem unidade (ex.: "4.1 VIGA BALDRAME")
    if re.match(r"^[A-ZÁÉÍÓÚÃÕÇ0-9\s./-]{3,40}$", desc) and " " in desc and len(desc.split()) <= 4:
        words = desc.split()
        if all(w.isupper() or w.isdigit() for w in words if len(w) > 1):
            return None

    return ImportedPriceRow(item=item, descricao=desc, unidade="", quantidade=0.0)


def _detect_columns(headers: list[Any]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, header in enumerate(headers):
        h = _normalize_header(header)
        h_compact = h.replace(" ", "")
        if not h:
            continue
        if h in ("item", "it", "cod item", "codigo item") or h.startswith("item "):
            mapping.setdefault("item", idx)
        elif h in ("codigo", "cod", "codigo composicao", "cod composicao", "cod. composicao") or (
            "codigo" in h and "item" not in h
        ):
            mapping.setdefault("codigo", idx)
        elif h in ("tipo", "nivel", "nível", "row type", "row_type"):
            mapping.setdefault("tipo", idx)
        elif "descricao" in h or h in ("servico", "servicos", "especificacao"):
            mapping.setdefault("descricao", idx)
        elif h in ("und", "un", "unid", "unidade", "un.") or h.startswith("unidade"):
            mapping.setdefault("unidade", idx)
        elif (
            h in ("qtd", "quant", "quantidade", "qtde")
            or "quantidade" in h
            or h_compact == "quantidade"
            or h.startswith("quanti")
        ):
            mapping.setdefault("quantidade", idx)
    return mapping


def _item_from_excel_cell(value: Any, number_format: str | None = None) -> str:
    """Normaliza código de item; recupera numeração quando Excel converteu para data."""
    from datetime import date, datetime

    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        dt = value if isinstance(value, datetime) else datetime(value.year, value.month, value.day)
        fmt = (number_format or "").replace("\\", "").lower()
        if fmt.startswith("yy") or re.search(r"yy\.[^;]*m", fmt):
            return f"{dt.year % 100}.{dt.month}.{dt.day}"
        return f"{dt.month}.{dt.day}.{dt.year % 100}"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    if not text:
        return ""
    if text.endswith(".0") and _ITEM_RE.match(text[:-2]):
        return text[:-2]
    return text


def _normalize_item_code(raw: Any) -> str:
    return _item_from_excel_cell(raw)


def _cell_str(cells: list[Any], idx: int | None) -> str:
    if idx is None or idx >= len(cells):
        return ""
    val = cells[idx]
    if val is None:
        return ""
    return str(val).strip()


def _find_header_row(ws) -> tuple[int, dict[str, int]]:
    """Localiza linha de cabeçalho (ITEM + DESCRIÇÃO) nas primeiras 15 linhas."""
    for row_num, raw in enumerate(ws.iter_rows(min_row=1, max_row=15, values_only=True), start=1):
        headers = list(raw or [])
        cols = _detect_columns(headers)
        if "descricao" in cols and "item" in cols:
            return row_num, cols
        if "descricao" in cols:
            return row_num, cols
    raise ValueError(
        "Planilha sem colunas reconhecíveis. Use cabeçalho com Item, Descrição, Und e Quantidade."
    )


def parse_excel_rows(path: Path) -> list[ImportedPriceRow]:
    from pricing.budget.price_matching_hierarchy import parse_excel_hierarchy

    lines = parse_excel_hierarchy(path)
    return [ln.to_price_row() for ln in lines if ln.row_type == "SERVICO"]


def parse_excel_hierarchy(path: Path):
    """Reexport — implementação em price_matching_hierarchy."""
    from pricing.budget.price_matching_hierarchy import parse_excel_hierarchy as _parse

    return _parse(path)


def _parse_table_line(line: str) -> ImportedPriceRow | None:
    parsed = _parse_budget_pdf_line(line)
    if parsed:
        return parsed

    line = re.sub(r"\s{2,}", "\t", line.strip())
    parts = [p.strip() for p in line.split("\t") if p.strip()]
    if len(parts) < 2:
        parts = [p.strip() for p in re.split(r"\s{2,}|\|", line) if p.strip()]
    if len(parts) < 2:
        return None

    item = ""
    desc = ""
    unit = ""
    qty = 0.0

    if len(parts) >= 4 and (_ITEM_RE.match(parts[0]) or parts[0].endswith(".")):
        item, desc, unit, qty_raw = parts[0], parts[1], parts[2], parts[3]
        qty = _parse_quantity(qty_raw) or 0.0
    elif len(parts) >= 3:
        if _ITEM_RE.match(parts[0]):
            item, desc, unit = parts[0], parts[1], parts[2]
            if len(parts) >= 4:
                qty = _parse_quantity(parts[3]) or 0.0
        else:
            desc, unit, qty_raw = parts[0], parts[1], parts[2]
            qty = _parse_quantity(qty_raw) or 0.0
    else:
        desc = parts[0]
        if len(parts) > 1 and _QTY_RE.match(parts[-1].replace(",", ".")):
            qty = _parse_quantity(parts[-1]) or 0.0

    desc = desc.strip()
    if not desc or len(desc) < 3:
        return None
    if _normalize_header(desc) in ("descricao", "descricao do servico", "servico"):
        return None
    return ImportedPriceRow(item=item, descricao=desc, unidade=unit.strip(), quantidade=qty)


def parse_pdf_rows(path: Path) -> list[ImportedPriceRow]:
    from core.knowledge.pdf_text_extractor import extract_pdf_pages

    pages = extract_pdf_pages(path, use_ocr=True)
    if not pages:
        raise ValueError(
            "Não foi possível extrair texto do PDF. "
            "Verifique se o arquivo é pesquisável ou se o Tesseract está instalado para OCR."
        )

    text = "\n".join(t for _, t in pages)
    out: list[ImportedPriceRow] = []
    seen: set[str] = set()
    row_index = 0

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parsed = _parse_budget_pdf_line(line) or _parse_table_line(line)
        if not parsed:
            continue
        key = f"{parsed.item}|{parsed.descricao[:80]}|{parsed.unidade}|{parsed.quantidade}"
        if key in seen:
            continue
        seen.add(key)
        parsed.row_index = row_index
        out.append(parsed)
        row_index += 1

    return out


def import_price_file(path: Path) -> tuple[list[ImportedPriceRow], str]:
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        if suffix == ".xls":
            raise ValueError("Formato .xls legado: salve como .xlsx antes de importar")
        return parse_excel_rows(path), "xlsx"
    raise ValueError(
        f"Formato não suportado: {suffix}. Use planilha Excel (.xlsx) com colunas Item, Descrição, Und e Quantidade."
    )
