"""Testes Learning Loop v1."""

import sys
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database.models import Base
from core.database.repository import DatabaseRepository
from core.learning.feedback_service import (
    get_feedback_by_agent,
    get_low_quality_responses,
    record_agent_execution,
    save_feedback,
)
from core.dispatcher import dispatch


def _setup_sqlite_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_save_feedback_and_retrieve():
    db = _setup_sqlite_session()
    conv_id = str(uuid.uuid4())

    import core.learning.feedback_service as learning_module

    original = learning_module.is_db_enabled
    learning_module.is_db_enabled = lambda: True

    def _session_scope():
        from contextlib import contextmanager

        @contextmanager
        def scope():
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

        return scope()

    learning_module.session_scope = _session_scope

    record_agent_execution(
        agent_name="estruturas_agent",
        discipline="ESTRUTURAL",
        input_text="dimensionar viga",
        response_text="Análise estrutural",
        conversation_id=conv_id,
    )

    updated = save_feedback(
        conversation_id=conv_id,
        agent_name="estruturas_agent",
        rating=2,
        feedback_text="Resposta incompleta",
        corrected_answer="Deveria citar NBR 6118 tabela 6.3",
    )

    assert updated is not None
    assert updated["rating"] == 2
    assert updated["feedback_text"] == "Resposta incompleta"

    rows = get_feedback_by_agent("estruturas_agent")
    assert len(rows) >= 1
    assert rows[0]["agent_name"] == "estruturas_agent"

    low = get_low_quality_responses(threshold=3)
    assert any(r["rating"] == 2 for r in low)

    learning_module.is_db_enabled = original


def test_get_low_quality_responses():
    db = _setup_sqlite_session()
    repo = DatabaseRepository(db)
    repo.create_agent_feedback(
        agent_name="chat_agent",
        discipline="CHAT",
        input_text="oi",
        response_text="olá",
        rating=5,
    )
    repo.create_agent_feedback(
        agent_name="estruturas_agent",
        discipline="ESTRUTURAL",
        input_text="viga",
        response_text="erro",
        rating=1,
    )
    db.commit()

    import core.learning.feedback_service as learning_module

    original = learning_module.is_db_enabled
    learning_module.is_db_enabled = lambda: True

    def _session_scope():
        from contextlib import contextmanager

        @contextmanager
        def scope():
            yield db

        return scope()

    learning_module.session_scope = _session_scope

    low = get_low_quality_responses(threshold=3)
    assert len(low) == 1
    assert low[0]["rating"] == 1

    learning_module.is_db_enabled = original


def test_dispatcher_records_feedback_without_breaking():
    with patch.object(
        __import__("models.ollama_client", fromlist=["OllamaClient"]).OllamaClient,
        "generate",
        return_value=("Resposta OK", "qwen3:8b"),
    ), patch("core.learning.feedback_service.record_agent_execution") as mock_record:
        response = dispatch(
            {
                "input": "dimensionar viga",
                "discipline": "CHAT",
                "agent": "chat_agent",
                "_use_rag": False,
            },
            persist=False,
        )

    assert response.get("result") or response.get("response")
    mock_record.assert_called_once()
    call_kwargs = mock_record.call_args.kwargs
    assert call_kwargs["agent_name"] == "chat_agent"
    assert call_kwargs["discipline"] == "CHAT"


if __name__ == "__main__":
    test_save_feedback_and_retrieve()
    test_get_low_quality_responses()
    test_dispatcher_records_feedback_without_breaking()
    print("OK: testes Learning Loop v1 passaram")
