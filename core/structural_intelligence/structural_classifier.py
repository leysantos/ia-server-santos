"""
Structural Classifier — detecta sistema estrutural a partir do texto.
"""

from __future__ import annotations

import re
from typing import Optional

VALID_SYSTEMS = frozenset({
    "CONCRETE_ARMED",
    "CONCRETE_PRESTRESSED",
    "PRECAST_CONCRETE",
    "STEEL_STRUCTURE",
    "TIMBER_STRUCTURE",
    "MIXED_SYSTEMS",
})

# (system, keywords, weight)
_RULES: list[tuple[str, list[str], float]] = [
    ("STEEL_STRUCTURE", ["grande vão", "grande vao", "vão livre", "vao livre", "long span"], 2.0),
    ("STEEL_STRUCTURE", ["galpão metálico", "galpao metalico", "metálico", "metalico", "aço", "aco"], 2.5),
    ("STEEL_STRUCTURE", ["industrial", "galpão", "galpao", "treliça", "trelica"], 1.5),
    ("CONCRETE_ARMED", ["residência", "residencia", "residencial", "habitacional", "concreto armado"], 2.5),
    ("CONCRETE_ARMED", ["apartamento", "sobrado", "baixa altura", "térreo", "terreo"], 1.8),
    ("CONCRETE_PRESTRESSED", ["protensão", "protensao", "prestress", "protendido"], 2.2),
    ("PRECAST_CONCRETE", ["pré-moldado", "pre-moldado", "precast", "pré-fabricado"], 2.2),
    ("TIMBER_STRUCTURE", ["madeira", "timber", "clt", "estrutura de madeira"], 2.5),
    ("TIMBER_STRUCTURE", ["cobertura leve", "leveza", "estrutura leve"], 1.8),
    ("MIXED_SYSTEMS", ["misto", "híbrid", "hibrid", "mixed"], 2.0),
]

_SUBSYSTEM_MAP: dict[str, list[tuple[str, list[str]]]] = {
    "STEEL_STRUCTURE": [
        ("PORTAL_FRAME", ["pórtico", "portico", "portal"]),
        ("TRUSS", ["treliça", "trelica", "truss"]),
        ("BEAM_COLUMN", ["viga", "pilar metálico"]),
    ],
    "CONCRETE_ARMED": [
        ("SLAB_BEAM", ["laje", "viga"]),
        ("FRAME", ["pórtico", "portico", "frame"]),
        ("FOUNDATION", ["fundação", "fundacao", "sapata", "estaca"]),
    ],
    "TIMBER_STRUCTURE": [
        ("ROOF_TRUSS", ["cobertura", "telhado", "truss"]),
        ("DECK", ["deck", "laje de madeira"]),
    ],
}

_SPAN_PATTERN = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*m(?:etros)?(?:\s*(?:de\s+)?(?:vão|vao|span|livre))?",
    re.IGNORECASE,
)
_SPAN_NEAR_PATTERN = re.compile(
    r"(?:vão|vao|span)\s*(?:de\s+)?(\d+(?:[.,]\d+)?)\s*m",
    re.IGNORECASE,
)


class StructuralClassifier:
    """Classifica sistema estrutural, complexidade e vão estimado."""

    def classify(self, text: str) -> dict:
        text = (text or "").strip()
        lowered = text.lower()
        scores: dict[str, float] = {s: 0.0 for s in VALID_SYSTEMS if s != "MIXED_SYSTEMS"}

        for system, keywords, weight in _RULES:
            for kw in keywords:
                if kw in lowered:
                    scores[system] = scores.get(system, 0.0) + weight
                    break

        span_estimate = _extract_span(text)
        if span_estimate and span_estimate >= 20:
            scores["STEEL_STRUCTURE"] = scores.get("STEEL_STRUCTURE", 0.0) + 2.0
        elif span_estimate and span_estimate >= 12:
            scores["CONCRETE_PRESTRESSED"] = scores.get("CONCRETE_PRESTRESSED", 0.0) + 1.0

        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_system, top_score = sorted_scores[0] if sorted_scores else ("CONCRETE_ARMED", 0.0)
        second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0.0

        if top_score > 0 and (top_score - second_score) < 0.8:
            top_system = "MIXED_SYSTEMS"

        if top_score == 0:
            top_system = "CONCRETE_ARMED"
            top_score = 0.5

        subsystem = _detect_subsystem(top_system, lowered)
        complexity = _estimate_complexity(top_system, span_estimate, lowered)
        total = sum(scores.values()) or 1.0
        confidence = min(1.0, max(0.4, top_score / total))

        return {
            "system": top_system,
            "subsystem": subsystem,
            "complexity": complexity,
            "span_estimate": span_estimate,
            "confidence": round(confidence, 3),
        }


def _extract_span(text: str) -> Optional[float]:
    for pattern in (_SPAN_NEAR_PATTERN, _SPAN_PATTERN):
        match = pattern.search(text)
        if match:
            raw = match.group(1).replace(",", ".")
            try:
                return float(raw)
            except ValueError:
                continue
    return None


def _detect_subsystem(system: str, lowered: str) -> Optional[str]:
    for subsystem, keywords in _SUBSYSTEM_MAP.get(system, []):
        if any(kw in lowered for kw in keywords):
            return subsystem
    return None


def _estimate_complexity(
    system: str,
    span: Optional[float],
    lowered: str,
) -> str:
    if span is not None and span >= 25:
        return "HIGH"
    if system == "STEEL_STRUCTURE" and (
        (span is not None and span >= 15)
        or "industrial" in lowered
        or "galpão" in lowered
        or "galpao" in lowered
    ):
        return "HIGH"
    if system in ("MIXED_SYSTEMS", "CONCRETE_PRESTRESSED", "PRECAST_CONCRETE"):
        return "MEDIUM"
    if system == "CONCRETE_ARMED" and span is not None and span >= 10:
        return "MEDIUM"
    return "LOW"
