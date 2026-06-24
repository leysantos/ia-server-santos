"""Parser SICRO DNIT — composições fechadas/sintéticas, analíticas (CPU) e insumos."""

from __future__ import annotations

import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from pricing.budget.price_bank_store import (
    CompositionClosed,
    CompositionItem,
    CompositionOpen,
    InsumoRecord,
)

_COMP_CODE_RE = re.compile(r"^\d{6,8}$")
_ITEM_CODE_RE = re.compile(r"^[MEP]\d{3,5}$", re.I)
_SECTION_MARKERS = {
    "A - EQUIPAMENTOS": "equipamento",
    "B - MÃO DE OBRA": "mao_obra",
    "B - MAO DE OBRA": "mao_obra",
    "C - MATERIAL": "insumo",
    "D - ATIVIDADES AUXILIARES": "atividade",
    "E - TEMPO FIXO": "tempo_fixo",
    "F - MOMENTO DE TRANSPORTE": "transporte",
}


def _norm(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _float_cell(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    text = str(value).strip()
    if not text or text in {"-", "—", "–"}:
        return default
    try:
        return float(text.replace(",", "."))
    except (TypeError, ValueError):
        return default


def _is_comp_code(value: object) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return bool(_COMP_CODE_RE.match(text))


def _is_item_code(value: object) -> bool:
    if value is None:
        return False
    text = str(value).strip().upper()
    if text.endswith(".0"):
        text = text[:-2]
    return bool(_ITEM_CODE_RE.match(text))


def _code_str(value: object) -> str:
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def _pick_file(folder: Path, *needles: str, exclude: tuple[str, ...] = ()) -> Path | None:
    candidates = sorted(folder.glob("*.xlsx"))
    for needle in needles:
        n = _norm(needle)
        for path in candidates:
            name = _norm(path.name)
            if n not in name:
                continue
            if any(_norm(ex) in name for ex in exclude):
                continue
            if path.name.endswith(":Zone.Identifier"):
                continue
            return path
    return None


def _read_matrix(path: Path) -> list[tuple]:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb.active
        return list(ws.iter_rows(values_only=True))
    finally:
        wb.close()


def _parse_synthetic_table(
    matrix: list[tuple],
    *,
    price_col: int = 3,
    code_col: int = 0,
    desc_col: int = 1,
    unit_col: int = 2,
) -> list[tuple[str, str, str, float]]:
    rows: list[tuple[str, str, str, float]] = []
    for row in matrix[1:]:
        if not row or row[code_col] is None:
            continue
        code = _code_str(row[code_col])
        if not code or not (_is_comp_code(code) or _is_item_code(code)):
            continue
        desc = str(row[desc_col] or "").strip()
        if not desc:
            continue
        unit = str(row[unit_col] or "un").strip()
        price = _float_cell(row[price_col] if price_col < len(row) else None)
        rows.append((code.upper(), desc, unit, price))
    return rows


def _parse_closed_compositions(folder: Path, *, desonerado: bool) -> list[CompositionClosed]:
    sem = _pick_file(folder, "sintético de composições", exclude=("desoneração", "desoneracao"))
    com = _pick_file(folder, "sintético de composições", "desoneração") or _pick_file(
        folder, "sintetico de composicoes", "desoneracao"
    )
    if not sem and not com:
        return []

    sem_rows: dict[str, tuple[str, str, str, float]] = {}
    com_rows: dict[str, tuple[str, str, str, float]] = {}
    if sem:
        for code, desc, unit, price in _parse_synthetic_table(_read_matrix(sem)):
            if _is_comp_code(code):
                sem_rows[code] = (code, desc, unit, price)
    if com:
        for code, desc, unit, price in _parse_synthetic_table(_read_matrix(com)):
            if _is_comp_code(code):
                com_rows[code] = (code, desc, unit, price)

    keys = sorted(set(sem_rows) | set(com_rows))
    closed: list[CompositionClosed] = []
    for code in keys:
        sem_item = sem_rows.get(code)
        com_item = com_rows.get(code)
        base = com_item or sem_item
        if not base:
            continue
        _, desc, unit, price_com = base
        price_sem = sem_item[3] if sem_item else price_com
        closed.append(
            CompositionClosed(
                code=code,
                description=desc,
                unit=unit,
                price=price_com if desonerado else price_sem,
                price_sem_desoneracao=price_sem,
                regional={},
            )
        )
    return closed


def _parse_insumo_sheet(path: Path, *, origin: str) -> list[tuple[str, str, str, float]]:
    matrix = _read_matrix(path)
    if not matrix:
        return []
    header = [_norm(c) for c in matrix[0]]
    price_col = 3
    for idx, cell in enumerate(header):
        if "custo produtivo" in cell or "preço unitário" in cell or "preco unitario" in cell:
            price_col = idx
            break
        if "custo" in cell and "unit" in cell:
            price_col = idx
    return [
        row
        for row in _parse_synthetic_table(
            matrix,
            price_col=price_col,
        )
        if _is_item_code(row[0])
    ]


def _parse_insumos(folder: Path, *, desonerado: bool) -> list[InsumoRecord]:
    specs = (
        ("material", ("sintético de materiais",), ("desoneração", "desoneracao")),
        ("mao_obra", ("sintético de mão de obra", "sintetico de mao de obra"), ("desoneração", "desoneracao")),
        ("equipamento", ("sintético de equipamentos",), ("desoneração", "desoneracao")),
    )
    merged: dict[str, dict[str, Any]] = {}

    for origin, needles, exclude in specs:
        sem_path = _pick_file(folder, *needles, exclude=exclude)
        com_path = None
        for needle in needles:
            com_path = _pick_file(folder, needle, "desoneração") or _pick_file(
                folder, needle, "desoneracao"
            )
            if com_path:
                break
        sem_map = {c: (d, u, p) for c, d, u, p in (_parse_insumo_sheet(sem_path, origin=origin) if sem_path else [])}
        com_map = {c: (d, u, p) for c, d, u, p in (_parse_insumo_sheet(com_path, origin=origin) if com_path else [])}
        for code in sorted(set(sem_map) | set(com_map)):
            desc, unit, price_com = com_map.get(code) or sem_map.get(code) or ("", "un", 0.0)
            _, _, price_sem = sem_map.get(code) or (desc, unit, price_com)
            merged[code] = {
                "code": code,
                "description": desc,
                "unit": unit,
                "price": price_com if desonerado else price_sem,
                "price_sem_desoneracao": price_sem,
                "origin": origin,
            }

    return [
        InsumoRecord(
            code=item["code"],
            description=item["description"],
            unit=item["unit"],
            price=float(item["price"]),
            price_sem_desoneracao=float(item["price_sem_desoneracao"]),
            origin=str(item["origin"]),
        )
        for item in merged.values()
    ]


def _is_composition_header_row(row: tuple) -> bool:
    """Cabeçalho CPU: código + descrição sem quantidade na coluna de coeficiente."""
    if not row or not _is_comp_code(row[0]):
        return False
    if not str(row[1] or "").strip():
        return False
    qty = row[2] if len(row) > 2 else None
    if qty is not None and _float_cell(qty) > 0:
        return False
    row_text = _norm(" ".join(str(x) for x in row if x))
    if "valores em reais" in row_text:
        return True
    return qty is None or not str(qty).strip()


def _labeled_row_value(row: tuple, *labels: str) -> float | None:
    cells = [str(c) if c is not None else "" for c in row]
    norms = [_norm(c) for c in cells]
    for label in labels:
        ln = _norm(label)
        for idx, cell in enumerate(norms):
            if ln not in cell:
                continue
            for j in range(len(row) - 1, idx, -1):
                val = _float_cell(row[j])
                if val > 0:
                    return val
    return None


def _append_analytical_item(
    comp: CompositionOpen,
    row: tuple,
    section: str,
) -> None:
    c0 = row[0]
    if section == "tempo_fixo":
        code_raw = row[2] if len(row) > 2 and (_is_comp_code(row[2]) or _is_item_code(row[2])) else c0
        code = _code_str(code_raw).upper()
        desc = str(row[1] or "").strip()
        coef = _float_cell(row[3] if len(row) > 3 else None)
        unit = str(row[4] or "un").strip() if len(row) > 4 else "un"
        unit_price = _float_cell(row[6] if len(row) > 6 else None)
        partial = _float_cell(row[8] if len(row) > 8 else None)
    elif section == "transporte":
        code = _code_str(c0).upper()
        desc = str(row[1] or "").strip()
        coef = _float_cell(row[2] if len(row) > 2 else None)
        unit = str(row[3] or "tkm").strip() if len(row) > 3 else "tkm"
        dmt_codes = [
            _code_str(row[i])
            for i in range(4, min(7, len(row)))
            if row[i] is not None and str(row[i]).strip()
        ]
        if dmt_codes:
            desc = f"{desc} (DMT: {', '.join(dmt_codes)})"
        unit_price = _float_cell(row[8] if len(row) > 8 else None)
        partial = unit_price if unit_price > 0 else 0.0
    else:
        code = _code_str(c0).upper()
        desc = str(row[1] or "").strip()
        coef = _float_cell(row[2] if len(row) > 2 else None)
        unit = str(row[3] or "un").strip() if len(row) > 3 else "un"
        unit_price = _float_cell(row[5] if len(row) > 5 else row[4] if len(row) > 4 else None)
        partial = _float_cell(row[8] if len(row) > 8 else row[7] if len(row) > 7 else None)

    if not desc:
        return
    if partial <= 0 and coef > 0 and unit_price > 0:
        partial = round(coef * unit_price, 4)
    if coef <= 0 and partial <= 0:
        return

    comp.items.append(
        CompositionItem(
            item_type=section,
            code=code,
            description=desc,
            unit=unit,
            coefficient=coef,
            unit_price=unit_price,
            partial_cost=partial,
            unit_price_sem=unit_price,
            partial_cost_sem=partial,
        )
    )


def _parse_analytical_compositions(path: Path) -> dict[str, CompositionOpen]:
    matrix = _read_matrix(path)
    open_map: dict[str, CompositionOpen] = {}
    current: CompositionOpen | None = None
    section = "insumo"

    for row in matrix:
        if not row:
            continue
        c0 = row[0]
        c0s = str(c0 or "").strip()
        c0u = c0s.upper()

        if c0u in _SECTION_MARKERS:
            section = _SECTION_MARKERS[c0u]
            continue

        if _is_comp_code(c0):
            if _is_composition_header_row(row):
                code = _code_str(c0)
                desc = str(row[1] or "").strip()
                unit = "un"
                for cell in row[6:]:
                    if cell and str(cell).strip() and not str(cell).strip().replace(".", "").isdigit():
                        unit = str(cell).strip()
                        break
                current = CompositionOpen(
                    code=code,
                    description=desc,
                    unit=unit,
                    total_price=0.0,
                    items=[],
                )
                open_map[code] = current
            elif current is not None:
                _append_analytical_item(current, row, section)
            continue

        if current is None:
            continue

        fic_val = _labeled_row_value(row, "custo do fic")
        if fic_val is not None:
            current.items.append(
                CompositionItem(
                    item_type="fic",
                    code="",
                    description="Custo do FIC",
                    unit="",
                    coefficient=0.0,
                    unit_price=0.0,
                    partial_cost=fic_val,
                    unit_price_sem=0.0,
                    partial_cost_sem=fic_val,
                )
            )
            continue

        total_val = _labeled_row_value(row, "custo unitário direto total", "custo unitario direto total")
        if total_val is not None:
            current.total_price = total_val
            continue

        if _is_item_code(c0):
            _append_analytical_item(current, row, section)

    for comp in open_map.values():
        if comp.total_price <= 0 and comp.items:
            comp.total_price = round(sum(i.partial_cost for i in comp.items), 4)
    return open_map


def _parse_open_compositions(folder: Path) -> dict[str, CompositionOpen]:
    path = _pick_file(folder, "analítico de composições", exclude=("desoneração", "desoneracao"))
    if not path:
        path = _pick_file(folder, "analitico de composicoes", exclude=("desoneracao",))
    if not path:
        return {}
    return _parse_analytical_compositions(path)


def parse_sicro_folder(
    folder: Path,
    *,
    uf: str = "",
    desonerado: bool = True,
) -> dict[str, Any]:
    """Extrai banco SICRO a partir de pasta descompactada (ex.: am-01-2026/)."""
    folder = Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError(f"Pasta SICRO não encontrada: {folder}")

    closed = _parse_closed_compositions(folder, desonerado=desonerado)
    insumos = _parse_insumos(folder, desonerado=desonerado)
    open_map = _parse_open_compositions(folder)

    meta_path = _pick_file(folder, "sintético de composições") or _pick_file(
        folder, "sintetico de composicoes"
    )
    region = uf.upper()
    period = ""
    if meta_path:
        matrix = _read_matrix(meta_path)
        if matrix:
            head = matrix[0]
            for cell in head:
                if cell and len(str(cell)) > 2 and str(cell) not in {"SISTEMA DE CUSTOS REFERENCIAIS DE OBRAS - SICRO"}:
                    region = str(cell).strip() or region
            if len(matrix) > 1:
                for cell in matrix[1]:
                    if cell and re.search(r"\d{4}", str(cell)):
                        period = str(cell).strip()
                        break

    return {
        "closed": closed,
        "open": open_map,
        "insumos": insumos,
        "format": "sicro_dnit",
        "uf": uf.upper() or region,
        "region_label": region,
        "period_label": period,
        "dual_desoneracao": True,
        "desonerado": desonerado,
    }


def extract_sicro_archive(archive: Path, dest: Path | None = None) -> Path:
    """Descompacta .zip ou .7z SICRO para pasta temporária ou dest."""
    archive = Path(archive)
    suffix = archive.suffix.lower()
    target = Path(dest) if dest else Path(tempfile.mkdtemp(prefix="sicro_"))
    target.mkdir(parents=True, exist_ok=True)

    if suffix == ".zip":
        with zipfile.ZipFile(archive, "r") as zf:
            zf.extractall(target)
        return target

    if suffix == ".7z":
        try:
            import py7zr
        except ImportError as exc:
            raise ImportError(
                "py7zr necessário para arquivos .7z SICRO — pip install py7zr"
            ) from exc
        with py7zr.SevenZipFile(archive, mode="r") as zf:
            zf.extractall(path=target)
        return target

    if archive.is_dir():
        return archive

    raise ValueError(f"Formato SICRO não suportado: {archive.name}")


def parse_sicro_package(
    path: Path,
    *,
    uf: str = "",
    desonerado: bool = True,
    work_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Aceita pasta descompactada, .zip ou .7z DNIT.
    Remove pasta temporária ao final se criada internamente.
    """
    path = Path(path)
    cleanup: Path | None = None
    try:
        if path.is_dir():
            folder = path
        else:
            folder = extract_sicro_archive(path, dest=work_dir)
            if work_dir is None:
                cleanup = folder
        return parse_sicro_folder(folder, uf=uf, desonerado=desonerado)
    finally:
        if cleanup and cleanup.is_dir():
            shutil.rmtree(cleanup, ignore_errors=True)


def infer_sicro_reference(path: Path) -> tuple[str, str, int, int]:
    """
    Infere UF e referência BR-SICRO-{UF}-YYYY-MM a partir do nome am-01-2026 ou pasta equivalente.
    """
    name = path.stem if path.is_file() else path.name
    m = re.search(r"(?P<uf>[a-z]{2})[-_](?P<month>\d{2})[-_](?P<year>\d{4})", name, re.I)
    if not m:
        return "", f"SICRO-{name}", 0, 0
    uf = m.group("uf").upper()
    month = int(m.group("month"))
    year = int(m.group("year"))
    ref = f"BR-SICRO-{uf}-{year}-{month:02d}"
    return uf, ref, year, month
