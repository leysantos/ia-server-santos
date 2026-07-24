"""Testes — fallback de lookup de composição entre referências."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pricing.budget.composition_lookup import (
    find_references_with_closed_code,
    resolve_composition_detail,
)
from pricing.budget.price_bank_index import PRICE_BANK_ROOT


@pytest.mark.parametrize("code", ["97063", "99806"])
def test_find_references_includes_sinapi_not_sicro_to(code: str):
    refs = find_references_with_closed_code(code)
    assert any(r.startswith("BR-2026") for r in refs)
    assert "BR-SICRO-TO-2026-01" not in refs


def test_resolve_composition_fallback_sinapi_code_with_sicro_reference():
    comp = resolve_composition_detail(
        "97063",
        uf="TO",
        reference="BR-SICRO-TO-2026-01",
    )
    if not (PRICE_BANK_ROOT / "BR-2026-05").is_dir():
        pytest.skip("Banco SINAPI 2026-05 ausente")
    assert comp is not None
    assert str(comp.get("resolved_reference") or "").startswith("BR-2026")
    assert comp.get("reference_fallback") is True
    assert comp.get("code")


def test_resolve_composition_still_404_for_unknown_code():
    comp = resolve_composition_detail(
        "00000000",
        uf="SP",
        reference="BR-2026-05",
    )
    assert comp is None
