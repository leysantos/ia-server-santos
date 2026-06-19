"""Restauração de sessão em memória após perda do store."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.budget_db_service import session_from_payload
from pricing.budget.budget_session import SESSION_STORE
from pricing.budget.ppd_template import create_empty_ppd_metadata
from pricing.budget.budget_structure import add_etapa


def test_session_restore_from_payload():
    SESSION_STORE._sessions.clear()
    meta = create_empty_ppd_metadata()
    roots = []
    add_etapa(roots, "ADMINISTRAÇÃO", meta)
    session = SESSION_STORE.create(
        roots=roots,
        title="Obra teste",
        intent={},
        project=meta,
    )
    payload = session.to_dict()
    sid = session.id
    SESSION_STORE._sessions.clear()
    assert SESSION_STORE.get(sid) is None

    restored = session_from_payload(payload)
    assert SESSION_STORE.get(sid) is not None
    assert restored.id == sid
    assert len(restored.roots) == 1
    assert restored.roots[0].name == "ADMINISTRAÇÃO"
