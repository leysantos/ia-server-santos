"""Sticky discipline: follow-ups curtos herdam a disciplina do histórico."""

from __future__ import annotations

from core.conversation_context import _THREAD_HEADER, _THREAD_MARKER
from core.intent_layer import analyze_intent, infer_sticky_discipline


def _composed(prior_user: str, latest: str) -> str:
    return (
        f"{_THREAD_HEADER}"
        "Os dados abaixo JÁ FORAM INFORMADOS.\n\n"
        "DADOS E PEDIDOS ANTERIORES DO USUÁRIO:\n"
        f"- {prior_user}\n\n"
        "TRECHOS DAS RESPOSTAS ANTERIORES (referência):\n"
        "- checklist preliminar entregue\n\n"
        f"{_THREAD_MARKER}{latest}"
    )


def test_infer_sticky_hidrossanitario():
    text = _composed(
        "checklist de instalações hidráulicas de água fria e esgoto sanitario",
        "preciso saber todos os itens que precisa ter no projeto",
    )
    assert infer_sticky_discipline(text) == "HIDROSSANITÁRIO"


def test_analyze_intent_sticky_followup_not_chat():
    text = _composed(
        "projeto de instalações hidráulicas água fria e esgoto",
        "liste todos os itens que precisa ter no desenho técnico",
    )
    analysis = analyze_intent(text)
    assert analysis.mode == "engineering_only"
    assert analysis.technical_discipline == "HIDROSSANITÁRIO"
    assert analysis.execution_plan[0].domain == "engineering"
    assert analysis.execution_plan[0].agent == "hidrossanitario_agent"


def test_analyze_intent_sticky_greeting_stays_chat():
    text = _composed(
        "projeto de esgoto sanitário predial NBR 8160",
        "bom dia",
    )
    analysis = analyze_intent(text)
    assert analysis.mode == "chat_only"


def test_analyze_intent_sticky_structural_followup():
    text = _composed(
        "dimensione uma viga de concreto armado 15x40cm vão 5m",
        "preciso da quantidade de barras longitudinais",
    )
    analysis = analyze_intent(text)
    assert analysis.mode == "engineering_only"
    assert analysis.technical_discipline == "ESTRUTURAL"
