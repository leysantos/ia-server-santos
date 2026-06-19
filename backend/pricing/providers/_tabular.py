from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from pricing.models.price_source import PriceSource
from pricing.providers.base_provider import BasePriceProvider
from pricing.core.price_matcher import PriceMatcher
from pricing.models.price_request import PriceRequest
from pricing.models.price_item import PriceItem

_CODE_KEYS = ("codigo", "code", "código", "cod", "item")
_DESC_KEYS = ("descricao", "descrição", "description", "desc", "servico", "serviço")
_UNIT_KEYS = ("unidade", "unit", "und", "un")
_PRICE_KEYS = ("preco", "preço", "price", "valor", "custo", "total")


def _norm_header(value: object) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _pick_column(headers: list[str], candidates: tuple[str, ...]) -> int | None:
    for idx, header in enumerate(headers):
        h = _norm_header(header)
        if h in candidates or any(c in h for c in candidates):
            return idx
    return None


def parse_tabular_file(path: Path) -> list[dict]:
    """Parse CSV ou Excel genérico com detecção de colunas."""
    suffix = path.suffix.lower()
    if suffix in (".csv", ".txt"):
        return _parse_csv(path)
    if suffix in (".xlsx", ".xls"):
        return _parse_excel(path)
    if suffix == ".json":
        return _parse_json(path)
    raise ValueError(f"Formato não suportado: {suffix}")


def _parse_csv(path: Path) -> list[dict]:
    rows: list[dict] = []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        headers = next(reader, None)
        if not headers:
            return rows
        return _rows_from_matrix(headers, list(reader))


def _parse_excel(path: Path) -> list[dict]:
    try:
        import openpyxl
    except ImportError as exc:
        raise ImportError("openpyxl necessário para Excel: pip install openpyxl") from exc

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    matrix = list(ws.iter_rows(values_only=True))
    wb.close()
    if not matrix:
        return []
    headers = [str(c or "") for c in matrix[0]]
    return _rows_from_matrix(headers, matrix[1:])


def _parse_json(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [_normalize_row(item) for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and "items" in data:
        return [_normalize_row(item) for item in data["items"] if isinstance(item, dict)]
    return []


def _rows_from_matrix(headers: list, data_rows: list) -> list[dict]:
    headers_norm = [_norm_header(h) for h in headers]
    code_i = _pick_column(headers_norm, _CODE_KEYS)
    desc_i = _pick_column(headers_norm, _DESC_KEYS)
    unit_i = _pick_column(headers_norm, _UNIT_KEYS)
    price_i = _pick_column(headers_norm, _PRICE_KEYS)

    if desc_i is None and code_i is None:
        return []

    items: list[dict] = []
    for row in data_rows:
        if not row:
            continue
        cells = list(row)
        code = cells[code_i] if code_i is not None and code_i < len(cells) else ""
        desc = cells[desc_i] if desc_i is not None and desc_i < len(cells) else ""
        if not str(desc or code).strip():
            continue
        unit = cells[unit_i] if unit_i is not None and unit_i < len(cells) else "un"
        price_raw = cells[price_i] if price_i is not None and price_i < len(cells) else 0
        try:
            price = float(str(price_raw).replace(",", ".").strip() or 0)
        except ValueError:
            price = 0.0
        items.append(
            {
                "code": str(code or "").strip(),
                "description": str(desc or "").strip(),
                "unit": str(unit or "un").strip(),
                "price": price,
            }
        )
    return items


def _normalize_row(row: dict) -> dict:
    mapping = {
        "code": _first_key(row, _CODE_KEYS),
        "description": _first_key(row, _DESC_KEYS),
        "unit": _first_key(row, _UNIT_KEYS) or "un",
        "price": _first_key(row, _PRICE_KEYS) or 0,
    }
    try:
        mapping["price"] = float(mapping["price"])
    except (TypeError, ValueError):
        mapping["price"] = 0.0
    return mapping


def _first_key(row: dict, keys: tuple[str, ...]) -> object:
    for key, val in row.items():
        if _norm_header(key) in keys:
            return val
    return ""


class TabularPriceProvider(BasePriceProvider):
    """Base para providers que carregam CSV/Excel/JSON tabular."""

    def load(self, source_path: str) -> None:
        path = Path(source_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Base de preços não encontrada: {path}")
        self._data = parse_tabular_file(path)
        self._source = PriceSource(
            name=self.name,
            label=self.label,
            item_count=len(self._data),
            path=str(path),
        )

    def search(self, request: PriceRequest) -> list[PriceItem]:
        if not self._data:
            return []
        matcher = PriceMatcher()
        query = request.query.strip()
        if query:
            qn = matcher.normalize(query)
            code_hits = [
                self._row_to_item(row)
                for row in self._data
                if qn and qn in matcher.normalize(str(row.get("code", "")))
            ]
            if code_hits:
                return code_hits[: request.limit]

        candidates = [
            self._row_to_item(row)
            for row in self._data
            if matcher.lexical_hit(request.query, row.get("description", ""))
        ]
        if not candidates:
            all_items = [self._row_to_item(row) for row in self._data]
            candidates = matcher.fuzzy_match(
                request.query,
                all_items,
                limit=request.limit,
                min_score=0.30,
                unit=request.unit,
            )
        else:
            candidates = sorted(
                candidates,
                key=lambda item: -matcher.match_score(
                    request.query, item.description, request.unit, item.unit
                ),
            )
        return candidates[: request.limit]
