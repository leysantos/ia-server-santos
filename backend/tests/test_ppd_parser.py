"""Testes parser/exportador PPD — planilha municipal de referência."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.conftest import PPD_EXAMPLE_PATH, requires_ppd_example

PPD_PATH = PPD_EXAMPLE_PATH


@requires_ppd_example
def test_ppd_parse_example_workbook():
    from pricing.budget.ppd_parser import parse_ppd_workbook

    metadata, items, info = parse_ppd_workbook(PPD_PATH)

    assert metadata.projeto
    assert "PONTE" in metadata.projeto.upper() or "DUTRA" in metadata.objeto.upper()
    assert len(items) >= 1
    assert info.get("sheets")
    assert metadata.bdi.rate_com_desoneracao > 0


@requires_ppd_example
def test_ppd_parse_has_etapas_and_services():
    from pricing.budget.ppd_parser import parse_ppd_workbook

    _, items, _ = parse_ppd_workbook(PPD_PATH)
    etapas = [i for i in items if i.row_type == "ETAPA"]
    assert len(etapas) >= 2

    all_children = []
    for e in etapas:
        all_children.extend(e.children)
    services = [c for c in all_children if c.row_type == "S"]
    assert len(services) >= 5
    assert any(s.source_code for s in services)
    assert any(s.total_price > 0 for s in services)


@requires_ppd_example
def test_ppd_extract_price_base():
    from pricing.budget.ppd_parser import extract_price_base_rows

    rows = extract_price_base_rows(PPD_PATH)
    assert len(rows) > 100
    assert rows[0]["code"]
    assert rows[0]["price"] > 0


@requires_ppd_example
def test_ppd_extract_price_base_includes_seminf_and_container():
    from pricing.budget.ppd_parser import extract_price_base_rows

    rows = extract_price_base_rows(PPD_PATH)
    codes = {r["code"] for r in rows}
    assert "107071.1.9.SEMINF" in codes
    assert any("container" in r["description"].lower() for r in rows)


@requires_ppd_example
def test_ppd_seminf_services_use_dp_seminf_source_base():
    from pricing.budget.ppd_parser import parse_ppd_workbook

    _, items, _ = parse_ppd_workbook(PPD_PATH)

    def walk(nodes):
        for node in nodes:
            if node.row_type == "S":
                yield node
            yield from walk(node.children)

    seminf_services = [
        s for s in walk(items) if (s.source_code or "").upper().endswith(".SEMINF")
    ]
    assert len(seminf_services) >= 1
    for svc in seminf_services:
        assert svc.source_base.replace("-", "").upper() in ("DPSEMINF", "SEMINF", "PPDSEMINF")


@requires_ppd_example
def test_ppd_export_roundtrip():
    from pricing.budget.ppd_exporter import export_ppd_xlsx
    from pricing.budget.ppd_parser import parse_ppd_workbook

    metadata, items, _ = parse_ppd_workbook(PPD_PATH)
    xlsx = export_ppd_xlsx(items, metadata)
    assert xlsx[:2] == b"PK"
    assert len(xlsx) > 5000


@requires_ppd_example
def test_import_ppd_api():
    from app.routes.pricing import import_ppd_from_path
    from pricing.budget.budget_session import SESSION_STORE
    from pricing.bootstrap import reset_providers, ensure_providers_registered

    reset_providers()
    SESSION_STORE._sessions.clear()
    ensure_providers_registered()

    result = import_ppd_from_path(PPD_PATH, load_base=True)
    assert result["session_id"]
    assert result["grand_total"] > 0
    assert len(result["rows"]) > 10
    assert result["import_info"]["base_loaded"] > 100
