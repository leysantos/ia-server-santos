"""Testes — Especificação Técnica do orçamento."""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pricing.budget.budget_session import BudgetSession
from pricing.models.budget_item import BudgetItem, BudgetItemType
from pricing.spec.tech_spec_agent import build_budget_context, compose_tech_spec_stream
from pricing.spec.tech_spec_docx import export_tech_spec_docx
from pricing.spec.tech_spec_editor import apply_format_edits_from_prompt, edit_tech_spec_stream
from pricing.spec.tech_spec_models import TechSpecDocument, markdown_to_html, render_document_html


def _sample_session() -> BudgetSession:
    root = BudgetItem(
        code="1",
        name="Fundações",
        row_id="r1",
        level=1,
        quantity=0,
        unit="",
        unit_cost=1000,
        unit_price=1242.6,
        total_price=12426.0,
        item_type=BudgetItemType.COMPOSITION,
        children=[
            BudgetItem(
                code="1.1",
                name="Escavação",
                row_id="r2",
                level=2,
                quantity=10,
                unit="m³",
                unit_cost=50,
                unit_price=62.13,
                total_price=621.3,
                parent_code="1",
                item_type=BudgetItemType.COMPOSITION,
            )
        ],
    )
    return BudgetSession(id="sess-test", title="Obra teste", roots=[root])


def test_build_budget_context():
    ctx = build_budget_context(_sample_session())
    assert "Fundações" in ctx
    assert "Escavação" in ctx


def test_build_budget_context_with_schedule():
    from pricing.schedule.schedule_models import ProjectSchedule, ScheduleTask

    session = _sample_session()
    session.schedule = ProjectSchedule(
        project_start="2026-01-01",
        project_end="2026-06-30",
        tasks=[
            ScheduleTask(
                task_id="t1",
                budget_row_id="r2",
                budget_code="1.1",
                name="Escavação",
                duration_days=10,
                early_start="2026-01-01",
                early_finish="2026-01-14",
            )
        ],
    )
    ctx = build_budget_context(session)
    assert "2026-01-01" in ctx
    assert "2026-01-14" in ctx


def test_apply_format_edits_page_numbers_and_logo():
    doc = TechSpecDocument(markdown="# Corpo\n\nTexto.")
    result = apply_format_edits_from_prompt(
        doc,
        'Adicione numeração de páginas e a logo (Construtora ABC)',
    )
    assert result.formatting.get("page_numbers") is True
    assert result.formatting.get("logo_text") == "Construtora ABC"
    assert len(result.logs) >= 2


def test_edit_format_only_stream():
    doc = TechSpecDocument(markdown="# ESPECIFICAÇÃO\n\nConteúdo existente.")
    events = list(
        edit_tech_spec_stream(
            doc,
            "Adicione numeração de páginas no rodapé",
            use_llm=False,
        )
    )
    types = [e[0] for e in events]
    assert "preview" in types
    assert "done" in types
    done = next(d for t, d in events if t == "done")
    assert done["tech_spec"]["formatting"]["page_numbers"] is True


def test_render_document_html():
    doc = TechSpecDocument(
        markdown="# Teste",
        formatting={
            "font_family": "Calibri",
            "font_size": 11,
            "line_spacing": 1.15,
            "margin_cm": 2.5,
            "page_numbers": True,
            "logo_text": "Empresa X",
            "document_title": "Título Capa",
        },
    )
    html = render_document_html(doc)
    assert "tech-spec-logo" in html
    assert "Empresa X" in html
    assert "Título Capa" in html
    assert "tech-spec-page-footer" in html


def test_markdown_to_html():
    html = markdown_to_html("# Título\n\nParágrafo **negrito**.")
    assert "<h1>Título</h1>" in html
    assert "<strong>negrito</strong>" in html


def test_export_docx():
    doc = TechSpecDocument(
        title="Especificação Teste",
        markdown="# OBJETO\n\nTexto da especificação.",
        html_content=markdown_to_html("# OBJETO\n\nTexto da especificação."),
    )
    blob = export_tech_spec_docx(doc)
    assert blob[:2] == b"PK"


def test_compose_heuristic_stream():
    session = _sample_session()
    events = list(compose_tech_spec_stream(session, use_llm=False))
    types = [e[0] for e in events]
    assert "log" in types
    assert "done" in types
    done = next(d for t, d in events if t == "done")
    assert done["tech_spec"]["markdown"]


def test_session_store_tech_spec():
    from pricing.budget.budget_session import SESSION_STORE

    session = _sample_session()
    SESSION_STORE._sessions[session.id] = session  # noqa: SLF001
    updated = SESSION_STORE.update_tech_spec(
        session.id,
        {"markdown": "# Teste", "html_content": "<h1>Teste</h1>"},
    )
    assert updated.tech_spec is not None
    assert "Teste" in updated.tech_spec["markdown"]
    blob = SESSION_STORE.export_tech_spec_docx(session.id)
    assert len(blob) > 100


if __name__ == "__main__":
    test_build_budget_context()
    test_build_budget_context_with_schedule()
    test_apply_format_edits_page_numbers_and_logo()
    test_edit_format_only_stream()
    test_render_document_html()
    test_markdown_to_html()
    test_export_docx()
    test_compose_heuristic_stream()
    test_session_store_tech_spec()
    print("OK: testes tech_spec passaram")
