"""Análise CAD via ezdxf (Módulo E)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def analyze_dxf(path: Path) -> dict[str, Any]:
    path = Path(path).resolve()
    result: dict[str, Any] = {
        "format": "dxf",
        "layers": [],
        "blocos": [],
        "textos": [],
        "cotas": [],
        "polylines": 0,
        "elementos_detectados": [],
    }

    try:
        import ezdxf
    except ImportError:
        result["error"] = "ezdxf não instalado"
        return result

    try:
        doc = ezdxf.readfile(str(path))
    except Exception as exc:
        result["error"] = str(exc)
        return result

    msp = doc.modelspace()
    layer_names = sorted({layer.dxf.name for layer in doc.layers})
    result["layers"] = layer_names[:100]

    block_names = sorted({b.name for b in doc.blocks if not b.name.startswith("*")})
    result["blocos"] = block_names[:100]

    text_count = 0
    dim_count = 0
    pline_count = 0

    for entity in msp:
        dxftype = entity.dxftype()
        if dxftype == "TEXT" or dxftype == "MTEXT":
            text_count += 1
            if text_count <= 50:
                try:
                    txt = entity.dxf.text if dxftype == "TEXT" else entity.text
                    result["textos"].append(str(txt)[:200])
                except Exception:
                    pass
        elif dxftype == "DIMENSION":
            dim_count += 1
        elif dxftype in ("LWPOLYLINE", "POLYLINE"):
            pline_count += 1

    result["cotas"] = [{"count": dim_count}]
    result["polylines"] = pline_count
    result["elementos_detectados"] = [
        {"tipo": "layer", "quantidade": len(layer_names)},
        {"tipo": "bloco", "quantidade": len(block_names)},
        {"tipo": "texto", "quantidade": text_count},
        {"tipo": "cota", "quantidade": dim_count},
        {"tipo": "polyline", "quantidade": pline_count},
    ]
    return result
