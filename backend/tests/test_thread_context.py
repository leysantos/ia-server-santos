"""Regressão: histórico multi-turn deve sobreviver ao fechamento da sessão ORM."""

from __future__ import annotations

import os
import uuid

import pytest

os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("DB_ENABLED", "false")


@pytest.fixture
def db_ready(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("DB_ENABLED", "true")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'thread_ctx.db'}")

    from config.settings import reload_settings

    reload_settings()

    from core.database.connection import init_db, session_scope
    from core.database.repository import DatabaseRepository

    init_db()

    with session_scope() as session:
        repo = DatabaseRepository(session)
        conversation = repo.create_conversation(
            input_text="dimensione uma viga",
            mode="single",
            title="viga",
        )
        conv_id = conversation.id
        repo.create_message(conv_id, "user", "dimensione uma viga de concreto armado")
        repo.create_message(
            conv_id,
            "assistant",
            "Vou dimensionar. Qual o vão e o carregamento?",
        )

    return str(conv_id)


def test_build_thread_context_after_session_close(db_ready):
    from core.conversation_context import compose_thread_input, extract_latest_user_message
    from core.database.service import build_thread_context

    thread = build_thread_context(db_ready, limit=12)
    assert "Usuário:" in thread
    assert "Assistente:" in thread
    assert "vão" in thread.lower() or "carregamento" in thread.lower()

    composed = compose_thread_input("use 5m e 20 kN/m", db_ready)
    assert "CONTEXTO MULTI-TURN" in composed
    assert "DADOS E PEDIDOS ANTERIORES DO USUÁRIO" in composed
    assert "NOVA MENSAGEM DO USUÁRIO:" in composed
    assert "use 5m e 20 kN/m" in composed
    assert "dimensione uma viga" in composed
    assert "NÃO peça de novo" in composed
    assert extract_latest_user_message(composed) == "use 5m e 20 kN/m"


def test_compose_keeps_user_data_over_long_assistant(db_ready):
    """Respostas longas do assistente não podem expulsar dados do 1º prompt."""
    from core.database.connection import session_scope
    from core.database.repository import DatabaseRepository
    from core.conversation_context import compose_thread_input

    conv_id = uuid.UUID(db_ready)
    long_assistant = ("Cálculo detalhado. " * 400)  # ~7k chars
    with session_scope() as session:
        repo = DatabaseRepository(session)
        repo.create_message(
            conv_id,
            "user",
            "viga 15x40cm vão 5m carga 500kgf/m fck 25mpa",
        )
        repo.create_message(conv_id, "assistant", long_assistant)

    composed = compose_thread_input("quantas barras longitudinais e estribos?", str(conv_id))
    assert "15x40cm" in composed
    assert "500kgf/m" in composed
    assert "fck 25mpa" in composed
    assert "quantas barras longitudinais e estribos?" in composed
    # Assistente compactado — não deve levar o prompt a dezenas de milhares de chars
    assert len(composed) < 8000


def test_list_messages_returns_last_n(db_ready):
    from datetime import datetime, timedelta, timezone

    from core.database.connection import session_scope
    from core.database.repository import DatabaseRepository

    conv_id = uuid.UUID(db_ready)
    base = datetime.now(timezone.utc)
    with session_scope() as session:
        repo = DatabaseRepository(session)
        for i in range(20):
            msg = repo.create_message(conv_id, "user", f"msg-{i}")
            msg.created_at = base + timedelta(seconds=i)

    with session_scope() as session:
        repo = DatabaseRepository(session)
        last = repo.list_messages(conv_id, limit=5)
        assert len(last) == 5
        assert [m.content for m in last] == [f"msg-{i}" for i in range(15, 20)]
