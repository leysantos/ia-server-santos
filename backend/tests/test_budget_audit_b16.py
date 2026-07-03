"""Testes B16 — auditoria completa de operações de orçamento."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pricing.budget.budget_session import SESSION_STORE
from pricing.budget.budget_structure import add_etapa, add_service_to_group
from pricing.budget.ppd_template import create_empty_ppd_metadata
from pricing.models.price_item import PriceItem


def _fresh_session():
    SESSION_STORE._sessions.clear()
    meta = create_empty_ppd_metadata()
    roots = []
    add_etapa(roots, "FUNDAÇÕES", meta)
    return SESSION_STORE.create(roots=roots, title="Audit test", intent={}, project=meta)


def test_add_service_audit_entry():
    session = _fresh_session()
    etapa = session.roots[0].code
    price = PriceItem(code="88262", description="Escavação", unit="m³", price=12.5, source="sinapi")
    SESSION_STORE.add_service(
        session.id,
        etapa,
        {
            "code": price.code,
            "description": price.description,
            "unit": price.unit,
            "price": price.price,
            "source": price.source,
        },
        quantity=10.0,
    )
    actions = [e["action"] for e in session.audit_log]
    assert "add_service" in actions
    entry = next(e for e in session.audit_log if e["action"] == "add_service")
    assert entry["etapa_code"] == etapa
    assert entry["quantity"] == 10.0
    assert entry["service"]["source_code"] == "88262"


def test_replace_service_audit_entry():
    session = _fresh_session()
    etapa = session.roots[0]
    price = PriceItem(code="88262", description="Escavação", unit="m³", price=12.5, source="sinapi")
    svc = add_service_to_group(etapa, price, session.project, quantity=5.0)
    SESSION_STORE.replace_service(
        session.id,
        svc.row_id,
        {
            "code": "88309",
            "description": "Aterro",
            "unit": "m³",
            "price": 8.0,
            "source": "sinapi",
        },
    )
    entry = next(e for e in session.audit_log if e["action"] == "replace_service")
    assert entry["old_service"]["source_code"] == "88262"
    assert entry["new_service"]["source_code"] == "88309"


def test_apply_group_quantity_audit_entry():
    session = _fresh_session()
    group_code = session.roots[0].code
    SESSION_STORE.apply_group_quantity(session.id, group_code, 100.0)
    entry = next(e for e in session.audit_log if e["action"] == "apply_group_quantity")
    assert entry["group_code"] == group_code
    assert entry["quantity"] == 100.0


def test_schedule_sync_audit_entry():
    session = _fresh_session()
    SESSION_STORE.sync_schedule(session.id)
    entry = next(e for e in session.audit_log if e["action"] == "schedule_sync")
    assert entry["task_count"] >= 1
