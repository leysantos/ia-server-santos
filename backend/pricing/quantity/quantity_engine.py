from __future__ import annotations

import math
from typing import Any


class QuantityEngine:
    """
    Cálculo técnico de quantitativos — determinístico, sem LLM.
    Enriquece intent com quantities derivadas de dimensões.
    """

    WASTE_FACTOR = 1.05

    def enrich(self, intent: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(intent)
        dims = dict(enriched.get("dimensions") or {})
        computed = self._compute_base_quantities(dims)
        enriched["computed_quantities"] = computed

        etapas = enriched.get("etapas")
        if etapas:
            enriched["etapas"] = [
                {
                    **etapa,
                    "services": [
                        self._enrich_item(svc, computed)
                        for svc in (etapa.get("services") or [])
                    ],
                }
                for etapa in etapas
            ]
            enriched["items"] = [
                svc
                for etapa in enriched["etapas"]
                for svc in (etapa.get("services") or [])
            ]
        else:
            items = enriched.get("items")
            if items:
                enriched["items"] = [
                    self._enrich_item(row, computed) for row in items
                ]
            else:
                enriched["_default_quantity"] = computed.get("area") or computed.get("volume") or 1.0

        enriched["quantity_memory"] = self._build_memory(dims, computed)
        return enriched

    def _compute_base_quantities(self, dims: dict[str, Any]) -> dict[str, float]:
        length = float(dims.get("length") or 0)
        height = float(dims.get("height") or 0)
        width = float(dims.get("width") or 0)
        thickness = float(dims.get("thickness") or dims.get("espessura") or 0)
        area = float(dims.get("area") or 0)
        volume = float(dims.get("volume") or 0)
        count = float(dims.get("count") or dims.get("quantidade") or 0)

        if not area and length and height:
            area = length * height
        if not area and length and width:
            area = length * width
        if not volume and area and thickness:
            volume = area * thickness
        if not volume and length and width and height:
            volume = length * width * height

        perimeter = 2 * (length + width) if length and width else (2 * length if length else 0)

        result: dict[str, float] = {}
        if area:
            result["area"] = round(area * self.WASTE_FACTOR, 2)
        if volume:
            result["volume"] = round(volume * self.WASTE_FACTOR, 2)
        if length:
            result["length"] = round(length, 2)
        if perimeter:
            result["perimeter"] = round(perimeter, 2)
        if count:
            result["count"] = count
        return result

    def _enrich_item(self, row: dict[str, Any], computed: dict[str, float]) -> dict[str, Any]:
        if row.get("quantity"):
            return row
        unit = str(row.get("unit") or "").lower()
        qty = self._quantity_for_unit(unit, computed)
        if qty:
            return {**row, "quantity": qty}
        return row

    def _quantity_for_unit(self, unit: str, computed: dict[str, float]) -> float | None:
        mapping = {
            "m²": "area",
            "m2": "area",
            "m³": "volume",
            "m3": "volume",
            "m": "length",
            "un": "count",
            "und": "count",
            "h": "count",
        }
        key = mapping.get(unit.replace(" ", ""))
        if key and key in computed:
            return computed[key]
        if "area" in computed and unit in ("m²", "m2", ""):
            return computed["area"]
        return None

    def _build_memory(self, dims: dict[str, Any], computed: dict[str, float]) -> list[dict[str, Any]]:
        memory: list[dict[str, Any]] = []
        length = float(dims.get("length") or 0)
        height = float(dims.get("height") or 0)
        width = float(dims.get("width") or 0)

        if length and height and "area" in computed:
            memory.append(
                {
                    "step": "area",
                    "formula": f"{length} m × {height} m × {self.WASTE_FACTOR} (perda)",
                    "result": computed["area"],
                    "unit": "m²",
                }
            )
        if length and width and height and "volume" in computed:
            raw = length * width * height
            memory.append(
                {
                    "step": "volume",
                    "formula": f"{length}×{width}×{height} × {self.WASTE_FACTOR}",
                    "result": computed["volume"],
                    "unit": "m³",
                }
            )
        if not memory and computed:
            for key, val in computed.items():
                memory.append({"step": key, "formula": f"dimensões → {key}", "result": val})
        return memory
