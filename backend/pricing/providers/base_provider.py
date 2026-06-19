from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from pricing.models.price_item import PriceItem
from pricing.models.price_request import PriceRequest
from pricing.models.price_source import PriceSource


class BasePriceProvider(ABC):
    """Interface plugável — cada base de preços implementa load/search/get_by_code."""

    name: str = "base"
    label: str = "Base genérica"

    def __init__(self) -> None:
        self._data: list[dict] = []
        self._source: Optional[PriceSource] = None

    @property
    def source_info(self) -> Optional[PriceSource]:
        return self._source

    @property
    def is_loaded(self) -> bool:
        return bool(self._data)

    @abstractmethod
    def load(self, source_path: str) -> None:
        """Carrega itens da base a partir de arquivo (CSV, Excel, JSON…)."""

    def search(self, request: PriceRequest) -> list[PriceItem]:
        raise NotImplementedError

    def get_by_code(self, code: str) -> Optional[PriceItem]:
        row = next((x for x in self._data if str(x.get("code", "")) == str(code)), None)
        if not row:
            return None
        return self._row_to_item(row)

    def get_by_code_flexible(self, code: str) -> Optional[PriceItem]:
        """Aceita código SEMINF (106913.22.9.SEMINF) ou prefixo numérico."""
        raw = str(code or "").strip()
        if not raw:
            return None
        item = self.get_by_code(raw)
        if item:
            return item
        base = raw.split(".")[0]
        if base != raw:
            item = self.get_by_code(base)
            if item:
                return item
        row = next(
            (
                x
                for x in self._data
                if str(x.get("code", "")).startswith(f"{base}.") or str(x.get("code", "")) == base
            ),
            None,
        )
        if row:
            return self._row_to_item(row)
        return None

    def _row_to_item(self, row: dict) -> PriceItem:
        return PriceItem(
            code=str(row.get("code", "")),
            description=str(row.get("description", "")),
            unit=str(row.get("unit", "un")),
            price=float(row.get("price", 0) or 0),
            source=self.name,
            region=row.get("region"),
            metadata=dict(row.get("metadata") or {}),
        )
