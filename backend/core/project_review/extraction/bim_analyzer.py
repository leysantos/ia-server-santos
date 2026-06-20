"""Análise BIM via IFCOpenShell (Módulo D)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_IFC_ELEMENT_TYPES = (
    "IfcBeam",
    "IfcColumn",
    "IfcSlab",
    "IfcWall",
    "IfcFooting",
    "IfcStair",
    "IfcRamp",
    "IfcDoor",
    "IfcWindow",
    "IfcPile",
    "IfcBuildingElementProxy",
)


def analyze_ifc(path: Path) -> dict[str, Any]:
    path = Path(path).resolve()
    result: dict[str, Any] = {
        "format": "ifc",
        "inventario_bim": [],
        "quantitativos": {},
        "elementos_detectados": [],
        "metadata": {},
    }

    try:
        import ifcopenshell
    except ImportError:
        result["error"] = "ifcopenshell não instalado"
        return result

    try:
        model = ifcopenshell.open(str(path))
    except Exception as exc:
        result["error"] = str(exc)
        return result

    counts: dict[str, int] = {}
    inventory: list[dict[str, Any]] = []

    for ifc_type in _IFC_ELEMENT_TYPES:
        elements = model.by_type(ifc_type)
        if not elements:
            continue
        counts[ifc_type] = len(elements)
        for el in elements[:200]:
            name = getattr(el, "Name", None) or getattr(el, "GlobalId", "")
            inventory.append({"tipo": ifc_type, "nome": str(name)})

    result["quantitativos"] = counts
    result["inventario_bim"] = inventory
    result["elementos_detectados"] = [
        {"tipo": k.replace("Ifc", "").lower(), "quantidade": v} for k, v in counts.items()
    ]

    try:
        project = model.by_type("IfcProject")
        if project:
            result["metadata"]["project_name"] = getattr(project[0], "Name", None)
    except Exception:
        pass

    return result
