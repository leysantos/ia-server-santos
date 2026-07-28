"""L12 — Campos metrológicos tipados para patologias e ensaios.

Normaliza medidas (fissura mm, perda de seção %, espessura residual, etc.)
a partir do JSON do Gemini e de padrões no texto descritivo.
"""

from __future__ import annotations

import re
from typing import Any

METROLOGY_KEYS = (
    "crack_width_mm",
    "crack_length_m",
    "section_loss_pct",
    "residual_thickness_mm",
    "design_thickness_mm",
    "corrosion_depth_mm",
    "displacement_mm",
    "erosion_volume_m3",
    "affected_area_m2",
    "settlement_mm",
    "opening_mm",
)

METHOD_VALUES = frozenset({"visual", "estimated", "measured", "instrumented", "desconhecido"})


def metrology_prompt_block() -> str:
    return """
════════════════════════════════════════
CAMPOS METROLÓGICOS TIPADOS (L12 — OBRIGATÓRIO)
════════════════════════════════════════
Em CADA patologia, preencha `metrology` com valores numéricos quando observáveis
ou estimáveis. Use null se não aplicável. Nunca invente precisão falsa —
se for estimativa visual, method="estimated".

Formato metrology:
{
  "crack_width_mm": null,
  "crack_length_m": null,
  "section_loss_pct": null,
  "residual_thickness_mm": null,
  "design_thickness_mm": null,
  "corrosion_depth_mm": null,
  "displacement_mm": null,
  "erosion_volume_m3": null,
  "affected_area_m2": null,
  "settlement_mm": null,
  "opening_mm": null,
  "unit_notes": "",
  "method": "visual|estimated|measured|instrumented",
  "notes": ""
}

Regras:
- Fissuras: crack_width_mm (abertura) e crack_length_m (extensão) quando possível.
- Corrosão / perda de seção em aço: section_loss_pct e residual_thickness_mm.
- Deslocamentos / recalques: displacement_mm ou settlement_mm.
- Erosão: erosion_volume_m3 e/ou affected_area_m2.
- method="instrumented" somente se houver ensaio/medição citada.
""".strip()


_FLOAT_RE = re.compile(
    r"(?P<val>\d+(?:[.,]\d+)?)\s*(?P<unit>mm|cm|m|m²|m2|m³|m3|%)?",
    re.IGNORECASE,
)


def _to_float(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip().replace(",", ".")
    s = re.sub(r"[^\d.\-]", "", s)
    if not s or s in (".", "-", "-."):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _empty_metrology() -> dict[str, Any]:
    return {
        **{k: None for k in METROLOGY_KEYS},
        "unit_notes": "",
        "method": "desconhecido",
        "notes": "",
    }


def _extract_from_text(text: str) -> dict[str, float]:
    """Heurísticas leves para recuperar medidas mencionadas no texto."""
    t = (text or "").lower()
    found: dict[str, float] = {}
    patterns: list[tuple[str, re.Pattern[str]]] = [
        (
            "crack_width_mm",
            re.compile(
                r"(?:abertura|fissura|trinca)[^\d]{0,40}?(\d+(?:[.,]\d+)?)\s*mm",
                re.I,
            ),
        ),
        (
            "crack_width_mm",
            re.compile(r"(\d+(?:[.,]\d+)?)\s*mm\s*(?:de\s+)?(?:abertura|fissura)", re.I),
        ),
        (
            "section_loss_pct",
            re.compile(
                r"(?:perda\s+de\s+se[cç][aã]o|se[cç][aã]o\s+residual)[^\d]{0,30}?(\d+(?:[.,]\d+)?)\s*%",
                re.I,
            ),
        ),
        (
            "section_loss_pct",
            re.compile(r"(\d+(?:[.,]\d+)?)\s*%[^\n]{0,40}(?:perda|se[cç][aã]o)", re.I),
        ),
        (
            "residual_thickness_mm",
            re.compile(
                r"(?:espessura\s+residual|espessura\s+medida)[^\d]{0,30}?(\d+(?:[.,]\d+)?)\s*mm",
                re.I,
            ),
        ),
        (
            "corrosion_depth_mm",
            re.compile(r"(?:profundidade\s+de\s+corros[aã]o)[^\d]{0,30}?(\d+(?:[.,]\d+)?)\s*mm", re.I),
        ),
        (
            "displacement_mm",
            re.compile(r"(?:deslocamento|flecha)[^\d]{0,30}?(\d+(?:[.,]\d+)?)\s*mm", re.I),
        ),
        (
            "settlement_mm",
            re.compile(r"(?:recalque|assentamento)[^\d]{0,30}?(\d+(?:[.,]\d+)?)\s*mm", re.I),
        ),
        (
            "affected_area_m2",
            re.compile(r"(?:[aá]rea\s+afetada)[^\d]{0,30}?(\d+(?:[.,]\d+)?)\s*m[²2]", re.I),
        ),
        (
            "erosion_volume_m3",
            re.compile(r"(?:volume\s+eros|volume\s+de\s+eros)[^\d]{0,30}?(\d+(?:[.,]\d+)?)\s*m[³3]", re.I),
        ),
        (
            "crack_length_m",
            re.compile(r"(?:extens[aã]o|comprimento)[^\d]{0,40}?(\d+(?:[.,]\d+)?)\s*m(?![m²³23])", re.I),
        ),
    ]
    for key, pat in patterns:
        if key in found:
            continue
        m = pat.search(t)
        if m:
            val = _to_float(m.group(1))
            if val is not None:
                found[key] = val
    return found


def normalize_metrology(
    raw: Any,
    *,
    text_fallback: str = "",
    has_linked_assay: bool = False,
) -> dict[str, Any]:
    base = _empty_metrology()
    if isinstance(raw, dict):
        for k in METROLOGY_KEYS:
            if k in raw:
                base[k] = _to_float(raw.get(k))
        # aliases comuns
        aliases = {
            "abertura_mm": "crack_width_mm",
            "fissura_mm": "crack_width_mm",
            "width_mm": "crack_width_mm",
            "perda_secao_pct": "section_loss_pct",
            "section_loss": "section_loss_pct",
            "espessura_residual_mm": "residual_thickness_mm",
            "thickness_mm": "residual_thickness_mm",
            "area_m2": "affected_area_m2",
            "volume_m3": "erosion_volume_m3",
        }
        for src, dst in aliases.items():
            if base.get(dst) is None and src in raw:
                base[dst] = _to_float(raw.get(src))
        method = str(raw.get("method") or "").strip().lower()
        if method in METHOD_VALUES:
            base["method"] = method
        base["unit_notes"] = str(raw.get("unit_notes") or raw.get("units") or "")[:200]
        base["notes"] = str(raw.get("notes") or "")[:400]
        # Faixas opcionais do Gemini
        for k in METROLOGY_KEYS:
            lo = _to_float(raw.get(f"{k}_min") or raw.get(f"{k}_low"))
            hi = _to_float(raw.get(f"{k}_max") or raw.get(f"{k}_high"))
            if lo is not None or hi is not None:
                base[f"{k}_min"] = lo
                base[f"{k}_max"] = hi

    extracted = _extract_from_text(text_fallback)
    for k, v in extracted.items():
        if base.get(k) is None:
            base[k] = v
            if base["method"] == "desconhecido":
                base["method"] = "estimated"

    # Inferir method se há valores
    has_value = any(base.get(k) is not None for k in METROLOGY_KEYS)
    if has_value and base["method"] == "desconhecido":
        base["method"] = "estimated"

    # Honestidade: measured/instrumented só com ensaio vinculado
    if base["method"] in ("measured", "instrumented") and not has_linked_assay:
        base["method"] = "estimated"
        note_extra = "Método rebaixado para estimated (sem ensaio documentado no laudo)."
        if note_extra not in (base.get("notes") or ""):
            base["notes"] = ((base.get("notes") or "") + " " + note_extra).strip()[:400]

    # Extrair faixas do texto ("entre 35% e 65%", "35% a 65%")
    t = (text_fallback or "").lower()
    range_pct = re.search(
        r"(?:entre\s+)?(\d+(?:[.,]\d+)?)\s*%?\s*(?:e|a|–|-)\s*(\d+(?:[.,]\d+)?)\s*%",
        t,
    )
    if range_pct and base.get("section_loss_pct") is not None:
        lo = _to_float(range_pct.group(1))
        hi = _to_float(range_pct.group(2))
        if lo is not None and hi is not None:
            base["section_loss_pct_min"] = min(lo, hi)
            base["section_loss_pct_max"] = max(lo, hi)

    return base


def _format_measure(m: dict[str, Any], key: str, label: str, unit: str) -> str | None:
    v = m.get(key)
    lo = m.get(f"{key}_min")
    hi = m.get(f"{key}_max")
    method = str(m.get("method") or "")
    if lo is not None and hi is not None:
        text = f"{label}: {lo:g}–{hi:g} {unit}"
    elif v is None:
        return None
    else:
        text = f"{label}: {v:g} {unit}"
    if method in ("estimated", "visual", "desconhecido"):
        text = f"≈ {text} (estim.)"
    return text


def apply_metrology(content: dict[str, Any]) -> dict[str, Any]:
    """Anexa/normaliza `metrology` em cada patologia."""
    out = dict(content or {})
    # Códigos de patologia com ensaio vinculado (sugerido ou executado L16)
    linked: set[str] = set()
    for t in out.get("instrumented_tests") or []:
        if not isinstance(t, dict):
            continue
        for ref in t.get("pathology_refs") or []:
            linked.add(str(ref).strip().upper())
    try:
        from core.inspection_report.assay_results import pathology_refs_with_executed_results

        linked |= pathology_refs_with_executed_results(out)
    except Exception:
        pass

    pathologies = []
    for p in out.get("pathologies") or []:
        if not isinstance(p, dict):
            continue
        item = dict(p)
        code = str(item.get("code") or item.get("codigo") or "").strip().upper()
        text = " ".join(
            str(item.get(k) or "")
            for k in ("description", "name", "recommendation", "location", "notes")
        )
        item["metrology"] = normalize_metrology(
            item.get("metrology"),
            text_fallback=text,
            has_linked_assay=bool(code and code in linked),
        )
        pathologies.append(item)
    out["pathologies"] = pathologies
    return out


def metrology_table(pathologies: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[list[str]] = []
    for p in pathologies:
        if not isinstance(p, dict):
            continue
        m = p.get("metrology") if isinstance(p.get("metrology"), dict) else {}
        vals = []
        labels = [
            ("crack_width_mm", "abert. fissura", "mm"),
            ("crack_length_m", "ext. fissura", "m"),
            ("section_loss_pct", "perda seção", "%"),
            ("residual_thickness_mm", "esp. residual", "mm"),
            ("design_thickness_mm", "esp. projeto", "mm"),
            ("corrosion_depth_mm", "prof. corrosão", "mm"),
            ("displacement_mm", "deslocamento", "mm"),
            ("settlement_mm", "recalque", "mm"),
            ("opening_mm", "abertura", "mm"),
            ("affected_area_m2", "área afetada", "m²"),
            ("erosion_volume_m3", "vol. erosão", "m³"),
        ]
        for key, label, unit in labels:
            formatted = _format_measure(m, key, label, unit)
            if formatted:
                vals.append(formatted)
        if not vals:
            continue
        rows.append(
            [
                str(p.get("code") or p.get("codigo") or "—"),
                str(p.get("name") or p.get("nome") or "—")[:80],
                str(p.get("element_id") or p.get("element") or "—"),
                "; ".join(vals),
                str(m.get("method") or "—"),
                (m.get("notes") or "—")[:100],
            ]
        )
    return {
        "caption": (
            "Campos metrológicos tipados — valores «estimated/visual» são estimativas "
            "de campo (confirmar com ensaio)"
        ),
        "headers": ["Código", "Patologia", "Elemento", "Medidas", "Método", "Notas"],
        "rows": rows
        or [["—", "—", "—", "Sem medidas tipadas nesta vistoria", "—", "—"]],
    }


def pathology_has_metrology(p: dict[str, Any]) -> bool:
    m = p.get("metrology") if isinstance(p.get("metrology"), dict) else {}
    return any(m.get(k) is not None for k in METROLOGY_KEYS)
