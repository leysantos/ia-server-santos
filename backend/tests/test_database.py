"""Testes da camada PostgreSQL (SQLite in-memory para CI local)."""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database.models import Base
from core.database.repository import DatabaseRepository
from core.database.service import (
    get_history,
    save_agent_run,
    save_conversation,
    save_orchestrator_log,
)


def _setup_sqlite_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_repository_crud():
    db = _setup_sqlite_session()
    repo = DatabaseRepository(db)

    conv = repo.create_conversation("teste multi", mode="multi")
    log = repo.create_orchestrator_log(
        input_text="teste multi",
        disciplines=["ESTRUTURAL", "ORÇAMENTO"],
        final_report="relatório",
        synthesis={"technical_summary": "resumo"},
        use_rag=False,
        agent_count=2,
        conversation_id=conv.id,
    )
    run = repo.create_agent_run(
        input_text="teste multi",
        discipline="ESTRUTURAL",
        agent_name="estruturas_agent",
        result_text="resultado",
        had_context=False,
        extra={"normas_base": ["NBR 6118"]},
        response_payload={"discipline": "ESTRUTURAL"},
        conversation_id=conv.id,
        orchestrator_log_id=log.id,
    )
    db.commit()

    history = repo.get_history(limit=10)
    assert len(history) == 1
    assert history[0].id == conv.id
    assert run.discipline == "ESTRUTURAL"
    assert log.agent_count == 2


def test_service_with_sqlite(monkeypatch=None):
    db = _setup_sqlite_session()

    import core.database.service as service_module

    original = service_module.is_db_enabled
    service_module.is_db_enabled = lambda: True

    conv = service_module.save_conversation("input teste", mode="multi", db=db)
    assert conv is not None
    conv_id = conv["id"]

    run = service_module.save_agent_run(
        route_result={"input": "input teste", "discipline": "ESTRUTURAL"},
        response={
            "agent": "estruturas_agent",
            "discipline": "ESTRUTURAL",
            "result": "ok",
            "extra": {},
        },
        conversation_id=conv_id,
        db=db,
    )
    assert run is not None

    log = service_module.save_orchestrator_log(
        input_text="input teste",
        disciplines=["ESTRUTURAL"],
        final_report="report",
        synthesis={"technical_summary": "s"},
        conversation_id=conv_id,
        db=db,
    )
    assert log is not None

    history = service_module.get_history(limit=10, db=db)
    assert len(history) == 1
    assert history[0]["id"] == conv_id

    service_module.is_db_enabled = original


def test_dispatcher_persist_flag():
    from core.dispatcher import dispatch

    result = dispatch(
        {"discipline": "ESTRUTURAL", "input": "viga"},
        persist=False,
    )
    assert result["discipline"] == "ESTRUTURAL"


def test_orchestrator_persist_flag():
    from core.orchestrator import process_multi_domain_request

    output = process_multi_domain_request(
        "projeto de prédio residencial com estrutura e hidráulica",
        use_rag=False,
        persist=False,
    )
    assert "conversation_id" not in output
    assert len(output["disciplines"]) >= 2


if __name__ == "__main__":
    test_repository_crud()
    test_service_with_sqlite()
    test_dispatcher_persist_flag()
    test_orchestrator_persist_flag()
    print("OK: testes database passaram")
