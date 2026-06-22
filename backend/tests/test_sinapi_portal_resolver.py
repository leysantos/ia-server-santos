"""Testes do resolver de portal SINAPI (sem rede)."""

from __future__ import annotations

from pricing.sync.sinapi_portal_resolver import (
    parse_categoria_id,
    pick_best_for_period,
    SinapiPortalFile,
)


def test_parse_categoria_id():
    assert parse_categoria_id("https://www.caixa.gov.br/site/Paginas/downloads.aspx#categoria_888") == 888
    assert parse_categoria_id("https://example.com") is None


def test_pick_best_prefers_retificacao():
    items = [
        SinapiPortalFile("SINAPI-2026-02-formato-xlsx", "http://a", "2026-03-01", 0),
        SinapiPortalFile(
            "SINAPI-2026-02-formato-xlsx_Retificacao01",
            "http://b",
            "2026-03-25",
            1,
        ),
    ]
    best = pick_best_for_period(items, year=2026, month=2)
    assert best is not None
    assert best.retificacao == 1
    assert "Retificacao01" in best.title
