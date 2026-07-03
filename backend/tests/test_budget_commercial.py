"""Testes B21 — CPQ margem comercial."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pricing.budget.budget_commercial_export import commercial_totals, export_proposta_comercial_xlsx
from pricing.budget.budget_session import SESSION_STORE
from pricing.budget.budget_structure import add_etapa, add_service_to_group
from pricing.budget.ppd_template import create_empty_ppd_metadata
from pricing.models.price_item import PriceItem


def test_commercial_totals_with_margin():
    meta = create_empty_ppd_metadata()
    meta.commercial_margin_pct = 10.0
    roots = []
    etapa = add_etapa(roots, "SERVIÇOS", meta)
    price = PriceItem(code="1", description="Serv", unit="un", price=100.0, source="sinapi")
    add_service_to_group(etapa, price, meta, quantity=10.0)
    totals = commercial_totals(roots, meta)
    assert totals["cost_total"] > 0
    assert totals["margin_pct"] == 10.0
    assert totals["margin_value"] > 0
    assert totals["proposal_total"] == round(totals["cost_total"] + totals["margin_value"], 2)


def test_export_proposta_comercial_xlsx():
    SESSION_STORE._sessions.clear()
    meta = create_empty_ppd_metadata()
    meta.commercial_margin_pct = 5.0
    meta.commercial_client = "Cliente XYZ"
    roots = []
    add_etapa(roots, "OBRA", meta)
    session = SESSION_STORE.create(roots=roots, title="CPQ", intent={}, project=meta)
    for root in session.roots:
        root.recompute_total()
    blob = export_proposta_comercial_xlsx(session.roots, session.project)
    assert blob[:2] == b"PK"
    assert len(blob) > 500
