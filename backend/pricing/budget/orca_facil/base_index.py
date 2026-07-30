"""OF2 — índice da base de preços embutida na planilha modelo."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _norm(text: str) -> str:
    raw = (text or "").lower().strip()
    raw = unicodedata.normalize("NFKD", raw)
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw)


def _tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9.]+", _norm(text)) if len(t) >= 2}


@dataclass
class BaseRow:
    code: str
    description: str
    unit: str
    price_comd: float
    price_semd: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_price_data(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "description": self.description,
            "unit": self.unit,
            "price": self.price_comd,
            "source": "seminf",
            "metadata": {
                **self.metadata,
                "price_sem_desoneracao": self.price_semd,
                "source": "ORCA_FACIL_MODEL_BASE",
            },
        }


@dataclass
class ModelPriceBaseIndex:
    """Catálogo em memória: get_by_code + search_base (top-k)."""

    sheet_name: str | None = None
    rows: list[BaseRow] = field(default_factory=list)
    _by_code: dict[str, BaseRow] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._by_code = {}
        for row in self.rows:
            key = str(row.code).strip()
            if key:
                self._by_code[key] = row
                # aliases numéricos (92212.0 → 92212)
                if key.endswith(".0") and key[:-2].isdigit():
                    self._by_code[key[:-2]] = row

    @property
    def size(self) -> int:
        return len(self.rows)

    def get_by_code(self, code: str) -> BaseRow | None:
        raw = str(code or "").strip()
        if not raw:
            return None
        hit = self._by_code.get(raw)
        if hit:
            return hit
        if raw.endswith(".0") and raw[:-2].isdigit():
            return self._by_code.get(raw[:-2])
        try:
            as_int = str(int(float(raw)))
            return self._by_code.get(as_int)
        except (TypeError, ValueError):
            return None

    def search_base(self, query: str, *, top_k: int = 8) -> list[tuple[BaseRow, float]]:
        q = _norm(query)
        if not q:
            return []
        q_tokens = _tokens(q)
        scored: list[tuple[BaseRow, float]] = []
        for row in self.rows:
            hay = _norm(f"{row.code} {row.description} {row.unit}")
            score = 0.0
            if q in hay:
                score += 10.0
            if row.code.strip() == query.strip():
                score += 50.0
            overlap = len(q_tokens & _tokens(hay))
            if overlap:
                score += overlap * 1.5
                # boost se tokens longos batem
                for t in q_tokens:
                    if len(t) >= 4 and t in hay:
                        score += 0.5
            if score > 0:
                scored.append((row, score))
        scored.sort(key=lambda x: (-x[1], x[0].code))
        return scored[: max(1, top_k)]

    def sample_for_prompt(self, *, limit: int = 40) -> list[dict[str, str]]:
        """Amostra compacta para few-shot / grounding (não enviar base inteira)."""
        out: list[dict[str, str]] = []
        step = max(1, len(self.rows) // max(limit, 1))
        for i in range(0, len(self.rows), step):
            row = self.rows[i]
            out.append(
                {
                    "code": row.code,
                    "unit": row.unit,
                    "description": (row.description or "")[:120],
                }
            )
            if len(out) >= limit:
                break
        return out

    def to_summary(self) -> dict[str, Any]:
        return {
            "sheet_name": self.sheet_name,
            "size": self.size,
            "sample_codes": [r.code for r in self.rows[:5]],
        }


def build_base_index_from_model(path: str | Path) -> ModelPriceBaseIndex:
    from pricing.budget.ppd_parser import extract_price_base_rows, pick_base_sheet_name
    import openpyxl

    path = Path(path)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = pick_base_sheet_name(wb.sheetnames)
    finally:
        wb.close()

    raw_rows = extract_price_base_rows(path, sheet_name=sheet)
    rows: list[BaseRow] = []
    for item in raw_rows:
        meta = dict(item.get("metadata") or {})
        rows.append(
            BaseRow(
                code=str(item.get("code") or "").strip(),
                description=str(item.get("description") or "").strip(),
                unit=str(item.get("unit") or "un").strip(),
                price_comd=float(item.get("price") or 0),
                price_semd=float(meta.get("price_sem_desoneracao") or item.get("price") or 0),
                metadata=meta,
            )
        )
    return ModelPriceBaseIndex(sheet_name=sheet, rows=rows)
