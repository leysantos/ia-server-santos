"""Testes B22 — pacote compliance licitação."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pricing.budget.budget_compliance_pack import build_compliance_pack, compliance_pack_json
from pricing.budget.budget_session import SESSION_STORE
from pricing.budget.budget_structure import add_etapa
from pricing.budget.ppd_template import create_empty_ppd_metadata


def test_compliance_pack_structure():
    SESSION_STORE._sessions.clear()
    meta = create_empty_ppd_metadata()
    roots = []
    add_etapa(roots, "ETAPA 1", meta)
    session = SESSION_STORE.create(roots=roots, title="Licitação", intent={}, project=meta)
    pack = build_compliance_pack(session)
    assert pack["session_id"] == session.id
    assert "checklist_lei_14133" in pack
    assert len(pack["checklist_lei_14133"]) >= 5
    assert any(c["id"] == "L3" for c in pack["checklist_lei_14133"])
    raw = compliance_pack_json(session)
    assert b"checklist_lei_14133" in raw
