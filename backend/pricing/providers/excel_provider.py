from __future__ import annotations

from pathlib import Path

from pricing.models.price_source import PriceSource
from pricing.providers._tabular import TabularPriceProvider, parse_tabular_file


class ExcelPriceProvider(TabularPriceProvider):
    """
    Provider genérico para planilhas Excel/CSV:
    SINAPI export, ORSE, prefeitura, base de empreiteiro.
    """

    name = "excel"
    label = "Excel/CSV genérico"

    def load(self, source_path: str, source_name: str | None = None) -> None:
        path = Path(source_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Base de preços não encontrada: {path}")
        self._data = parse_tabular_file(path)
        detected = (source_name or path.stem).lower()
        if "sinapi" in detected:
            self.name = "sinapi"
            self.label = "SINAPI (Excel)"
        elif "orse" in detected:
            self.name = "orse"
            self.label = "ORSE (Excel)"
        elif "tcpo" in detected:
            self.name = "tcpo"
            self.label = "TCPO (Excel)"
        elif "cicro" in detected or "sicro" in detected:
            self.name = "cicro"
            self.label = "CICRO (Excel)"
        self._source = PriceSource(
            name=self.name,
            label=self.label,
            item_count=len(self._data),
            path=str(path),
        )
