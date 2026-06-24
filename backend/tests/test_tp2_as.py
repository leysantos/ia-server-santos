"""Testes unificação tp2 / %AS."""

from __future__ import annotations

from pricing.budget.tp2_as import (
    AS_MARKER,
    apply_tp2_to_items,
    composition_tp2_from_regional,
    merge_tp2,
)


def test_merge_tp2_from_pct_as():
    assert merge_tp2("", 0.02) == AS_MARKER
    assert merge_tp2("", 0) == ""
    assert merge_tp2(AS_MARKER, 0) == AS_MARKER


def test_composition_tp2_from_regional():
    reg = {"AM": {"pct_as_comd": 0.01, "pct_as_semd": 0}}
    assert composition_tp2_from_regional(reg, uf="AM") == AS_MARKER
    assert composition_tp2_from_regional({"SP": {"pct_as_comd": 0}}, uf="AM") == ""


def test_apply_tp2_propagates_to_items():
    items = [{"code": "1", "tp2": ""}, {"code": "2", "tp2": "AS"}]
    out = apply_tp2_to_items(items, composition_tp2=AS_MARKER, pct_as=0.05)
    assert all(i["tp2"] == AS_MARKER for i in out)
