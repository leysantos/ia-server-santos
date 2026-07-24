"""Helpers para distinguir códigos WBS (itemização) de códigos de composição na base de preços."""

from __future__ import annotations

import re

_ITEMIZATION_RE = re.compile(r"^\d+(?:\.\d+)+$")


def is_itemization_code(code: str) -> bool:
    """True para códigos hierárquicos do orçamento (ex.: 4.1.7), não códigos SINAPI/SICRO."""
    return bool(_ITEMIZATION_RE.match((code or "").strip()))


def normalize_composition_code(raw: str) -> str:
    """Retorna código de composição válido ou string vazia se for itemização/WBS."""
    code = (raw or "").strip()
    if not code or is_itemization_code(code):
        return ""
    return code
