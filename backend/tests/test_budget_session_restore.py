"""Restauração de sessão em memória após perda do store."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.budget_db_service import session_from_payload
from pricing.budget.budget_session import SESSION_STORE
from pricing.budget.ppd_template import create_empty_ppd_metadata
from pricing.budget.budget_structure import add_etapa


def test_session_restore_from_payload(monkeypatch):
    """Restore via payload (salvar orçamento) — sem depender do snapshot B18."""
    monkeypatch.setattr(SESSION_STORE, "_persist_snapshot", lambda _session: None)
    monkeypatch.setattr(
        "app.services.budget_session_snapshot_service.restore_session_snapshot",
        lambda _sid: None,
    )
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


def test_session_snapshot_survives_memory_clear(monkeypatch, tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import core.database.workflow_models  # noqa: F401
    from app.services.budget_session_snapshot_service import save_session_snapshot
    from core.database.migrate_budget_session_snapshot import migrate_budget_session_snapshot
    from core.database.models import Base

    engine = create_engine(
        f"sqlite:///{tmp_path / 'snapshot.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    migrate_budget_session_snapshot(engine)
    test_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr("core.database.connection.SessionLocal", test_session_local)
    monkeypatch.setattr("core.database.connection.is_db_enabled", lambda: True)

    SESSION_STORE._sessions.clear()
    meta = create_empty_ppd_metadata()
    roots = []
    add_etapa(roots, "ESTRUTURA", meta)
    session = SESSION_STORE.create(
        roots=roots,
        title="Snapshot test",
        intent={},
        project=meta,
    )
    sid = session.id
    saved = save_session_snapshot(session)
    assert saved is True

    SESSION_STORE._sessions.clear()
    restored = SESSION_STORE.get(sid)
    assert restored is not None
    assert restored.id == sid
    assert restored.roots[0].name == "ESTRUTURA"
