"""Testes — Especificação Técnica do orçamento."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pricing.budget.budget_session import BudgetSession
from pricing.budget.ppd_layout import ROW_TYPE_ETAPA, ROW_TYPE_SERVICO, ROW_TYPE_SUB_ETAPA
from pricing.models.budget_item import BudgetItem, BudgetItemType
from pricing.spec.tech_spec_agent import compose_tech_spec_stream
from pricing.spec.tech_spec_docx import export_tech_spec_docx
from pricing.spec.tech_spec_format_parser import parse_format_directives
from pricing.spec.tech_spec_editor import apply_format_edits_from_prompt, edit_tech_spec_stream
from pricing.spec.tech_spec_models import TechSpecDocument, markdown_to_html, render_document_html
from pricing.spec.tech_spec_wbs import (
    append_missing_services_fallback,
    assemble_spec_markdown,
    build_budget_context,
    build_section_six_ordered,
    collect_wbs_inventory,
    fallback_spec_markdown,
    find_missing_service_codes,
    iter_spec_chunks,
    sanitize_llm_chunk,
)
from pricing.spec.tech_spec_generator import (
    default_fields_for_service,
    is_fields_complete,
    parse_service_fields,
    render_service_markdown,
    ServiceSpecFields,
)
from pricing.spec.tech_spec_etapa_json import build_etapa_json_payload, iter_etapa_chunks
from pricing.spec.tech_spec_stream_utils import has_repetition_loop
from pricing.spec.tech_spec_wbs import truncate_at_extra_service


def _sample_session() -> BudgetSession:
    """WBS real: etapa level=0, sub-etapa level=1, serviço level=2."""
    etapa1 = BudgetItem(
        code="1",
        name="Fundações",
        row_id="r1",
        level=0,
        quantity=0,
        unit="",
        unit_cost=0,
        unit_price=0,
        total_price=12426.0,
        item_type=BudgetItemType.GROUP,
        row_type=ROW_TYPE_ETAPA,
        children=[
            BudgetItem(
                code="1.1",
                name="Escavação",
                row_id="r2",
                level=1,
                quantity=0,
                unit="",
                unit_cost=0,
                unit_price=0,
                total_price=621.3,
                parent_code="1",
                item_type=BudgetItemType.GROUP,
                row_type=ROW_TYPE_SUB_ETAPA,
                children=[
                    BudgetItem(
                        code="1.1.1",
                        name="Escavação manual",
                        row_id="r3",
                        level=2,
                        quantity=10,
                        unit="m³",
                        unit_cost=50,
                        unit_price=62.13,
                        total_price=621.3,
                        parent_code="1.1",
                        item_type=BudgetItemType.COMPOSITION,
                        row_type=ROW_TYPE_SERVICO,
                    )
                ],
            )
        ],
    )
    etapa2 = BudgetItem(
        code="2",
        name="Estrutura",
        row_id="r4",
        level=0,
        quantity=0,
        unit="",
        unit_cost=0,
        unit_price=0,
        total_price=5000.0,
        item_type=BudgetItemType.GROUP,
        row_type=ROW_TYPE_ETAPA,
        children=[
            BudgetItem(
                code="2.1",
                name="Concreto",
                row_id="r5",
                level=1,
                quantity=5,
                unit="m³",
                unit_cost=400,
                unit_price=500,
                total_price=2500.0,
                parent_code="2",
                item_type=BudgetItemType.COMPOSITION,
                row_type=ROW_TYPE_SERVICO,
            )
        ],
    )
    return BudgetSession(id="sess-test", title="Obra teste", roots=[etapa1, etapa2])


def test_parse_service_fields():
    raw = (
        "**Descrição:** Escavação manual em solo de 1ª categoria.\n"
        "**Materiais:** Ferramentas manuais.\n"
        "**Método executivo:** Escavação com pás.\n"
        "**Critério de medição:** m³ executados.\n"
        "**Base de Preços:** SINAPI 12345\n"
        "**Normas aplicáveis:** NR-18\n"
    )
    fields = parse_service_fields(raw)
    assert fields is not None
    assert "Escavação" in fields.descricao
    assert fields.materiais
    assert "NR-18" in fields.normas


def test_render_service_markdown_structure():
    session = _sample_session()
    chunk = next(iter(iter_spec_chunks(session.roots)))
    svc = chunk.services[0]
    block = render_service_markdown(svc, default_fields_for_service(svc))
    assert f"#### SUB-ETAPA {svc.code}" in block
    assert "**Código WBS:**" in block
    assert "**Descrição:**" in block
    assert "**Normas aplicáveis:**" in block


def test_assemble_spec_markdown_partial():
    session = _sample_session()
    chunks = list(iter_spec_chunks(session.roots))
    blocks = {}
    for chunk in chunks[:1]:
        svc = chunk.services[0]
        blocks[svc.code] = render_service_markdown(svc, default_fields_for_service(svc))
    from pricing.spec.tech_spec_wbs import assemble_spec_markdown_partial

    md = assemble_spec_markdown_partial(session, blocks)
    assert "## 6. ESPECIFICAÇÕES POR ETAPA" in md
    assert "### ETAPA 1" in md
    assert "1.1.1" in md
    assert "## 7. MATERIAIS" not in md


def test_etapa_json_payload():
    session = _sample_session()
    etapas = list(iter_etapa_chunks(session))
    assert len(etapas) == 2
    p1 = etapas[0].payload
    assert p1["etapa"]["codigo"] == "1"
    assert "1.1.1" in p1["servicos_obrigatorios"]
    assert p1["total_servicos"] >= 1


def test_assemble_spec_from_etapas():
    from pricing.spec.tech_spec_wbs import assemble_spec_from_etapas

    session = _sample_session()
    md = assemble_spec_from_etapas(session, {})
    assert "### ETAPA 1" in md
    assert "1.1.1" in md
    assert "## 7. MATERIAIS" in md


def test_truncate_at_extra_service():
    text = (
        "#### SUB-ETAPA 3.2 — A\n\n**Código WBS:** 3.2\n\n"
        "#### SUB-ETAPA 3.3 — B\n\n**Código WBS:** 3.3"
    )
    out = truncate_at_extra_service(text, "3.2")
    assert "3.3" not in out
    assert "3.2" in out


def test_has_repetition_loop_ignores_service_template():
    """Blocos parecidos por serviço não devem disparar anti-loop."""
    block = (
        "**Descrição:** Serviço de pavimentação asfáltica em via urbana com camada de rolamento CBUQ.\n"
        "**Materiais:** CBUQ, emulsão, primer.\n"
        "**Método:** Aplicação mecanizada com vibroacabadora.\n"
        "**Medição:** metro quadrado executado e aceito.\n\n"
    )
    blocks = [
        block.replace("pavimentação", f"pavimentação trecho {i}") for i in range(12)
    ]
    text = "\n\n".join(blocks)
    assert len(text) >= 2_500
    assert has_repetition_loop(text) is False

    stuck = text + "### ETAPA 3 — INFRAESTRUTURA\n\n" * 4
    assert has_repetition_loop(stuck) is True


def test_iter_spec_chunks_one_per_service():
    services = [
        BudgetItem(
            code=f"2.{i}",
            name=f"Serv {i}",
            row_id=f"s{i}",
            level=1,
            quantity=1,
            unit="un",
            unit_cost=1,
            unit_price=1,
            total_price=1,
            parent_code="2",
            item_type=BudgetItemType.COMPOSITION,
            row_type=ROW_TYPE_SERVICO,
        )
        for i in range(1, 8)
    ]
    etapa = BudgetItem(
        code="2",
        name="Grande",
        row_id="e2",
        level=0,
        quantity=0,
        unit="",
        unit_cost=0,
        unit_price=0,
        total_price=0,
        item_type=BudgetItemType.GROUP,
        row_type=ROW_TYPE_ETAPA,
        children=services,
    )
    chunks = list(iter_spec_chunks([etapa]))
    assert len(chunks) == 7
    assert [c.service_codes[0] for c in chunks] == [f"2.{i}" for i in range(1, 8)]


def test_build_section_six_preserves_order():
    session = _sample_session()
    blocks = {
        "1.1.1": "#### SUB-ETAPA 1.1.1 — Escavação manual\n\n**Código WBS:** 1.1.1",
        "2.1": "#### SUB-ETAPA 2.1 — Concreto\n\n**Código WBS:** 2.1",
    }
    section = build_section_six_ordered(session.roots, blocks)
    assert section.index("1.1.1") < section.index("2.1")
    assert "### ETAPA 1" in section
    assert "### ETAPA 2" in section


def test_sanitize_llm_chunk():
    raw = "---\n```markdown\n#### SUB-ETAPA 3.2 — Teste\n\n**Código WBS:** 3.2\n```"
    cleaned = sanitize_llm_chunk(raw)
    assert "```" not in cleaned
    assert "---" not in cleaned
    assert "3.2" in cleaned


def test_assemble_spec_includes_all_services():
    session = _sample_session()
    md = assemble_spec_markdown(session, {})
    assert "1.1.1" in md
    assert "2.1" in md
    assert "## 7. MATERIAIS" in md
    assert find_missing_service_codes(session.roots, md) == []


def test_find_missing_service_codes():
    session = _sample_session()
    md = "### ETAPA 1\n\n[1.1.1] Escavação manual"
    missing = find_missing_service_codes(session.roots, md)
    assert "1.1.1" not in missing
    assert "2.1" in missing


def test_service_mentioned_by_name_or_heading():
    session = _sample_session()
    md = (
        "## 6. ESPECIFICAÇÕES POR ETAPA\n\n"
        "#### SUB-ETAPA 1.1 — Escavação\n\n"
        "Detalhamento do serviço de escavação manual em solo.\n"
    )
    assert find_missing_service_codes(session.roots, md) == ["2.1"]


def test_append_missing_inserts_before_section_seven():
    session = _sample_session()
    md = "# Doc\n\n## 6. ESPECIFICAÇÕES POR ETAPA\n\nTexto.\n\n## 7. MATERIAIS\n\nFim."
    result = append_missing_services_fallback(session, md, ["2.1"])
    assert "Serviços complementares" not in result
    assert "Serviços pendentes" in result
    assert result.index("Serviços pendentes") < result.index("## 7. MATERIAIS")


def test_collect_wbs_inventory():
    inv = collect_wbs_inventory(_sample_session().roots)
    assert inv.etapas == ["1", "2"]
    assert inv.subetapas == ["1.1"]
    assert inv.servicos == ["1.1.1", "2.1"]


def test_build_budget_context():
    ctx = build_budget_context(_sample_session())
    assert "## ETAPA 1 — Fundações" in ctx
    assert "### SUB-ETAPA 1.1 — Escavação" in ctx
    assert "[1.1.1] Escavação manual" in ctx
    assert "## ETAPA 2 — Estrutura" in ctx
    assert "[2.1] Concreto" in ctx
    assert "Etapas obrigatórias: 1, 2" in ctx
    assert "Sub-etapas obrigatórias: 1.1" in ctx


def test_build_budget_context_with_schedule():
    from pricing.schedule.schedule_models import ProjectSchedule, ScheduleTask

    session = _sample_session()
    session.schedule = ProjectSchedule(
        project_start="2026-01-01",
        project_end="2026-06-30",
        tasks=[
            ScheduleTask(
                task_id="t1",
                budget_row_id="r3",
                budget_code="1.1.1",
                name="Escavação manual",
                duration_days=10,
                early_start="2026-01-01",
                early_finish="2026-01-14",
            )
        ],
    )
    ctx = build_budget_context(session)
    assert "2026-01-01" in ctx
    assert "2026-01-14" in ctx


def test_fallback_spec_covers_all_etapas():
    md = fallback_spec_markdown(_sample_session())
    assert "### ETAPA 1 — Fundações" in md
    assert "#### SUB-ETAPA 1.1.1 — Escavação manual" in md
    assert "### ETAPA 2 — Estrutura" in md
    assert "2.1" in md


def test_parse_format_directives_full_prompt():
    base = {"page_numbers": False, "font_family": "Arial", "font_size": 12, "line_spacing": 1.5}
    prompt = (
        "Detalhe cada serviço por etapa. Fonte Times New Roman 12pt, entrelinha 1,5, "
        "texto justificado, número da página no canto inferior direito, margens 3cm"
    )
    fmt, logs = parse_format_directives(prompt, base)
    assert fmt["page_numbers"] is True
    assert fmt["page_number_position"] == "right"
    assert fmt["font_family"] == "Times New Roman"
    assert fmt["font_size"] == 12
    assert fmt["line_spacing"] == 1.5
    assert fmt["text_align"] == "justify"
    assert fmt["margin_top_cm"] == 3.0
    assert len(logs) >= 5


def test_parse_format_directives_page_center_and_no_numbers():
    fmt, _ = parse_format_directives(
        "Página centralizada no rodapé, fonte Arial 11pt",
        {"page_numbers": True},
    )
    assert fmt["page_number_position"] == "center"
    assert fmt["font_family"] == "Arial"
    assert fmt["font_size"] == 11

    fmt2, logs2 = parse_format_directives("Sem numeração de páginas", {"page_numbers": True})
    assert fmt2["page_numbers"] is False
    assert any("desativada" in log.lower() for log in logs2)


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


def test_export_pdf():
    try:
        from pricing.spec.tech_spec_pdf import export_tech_spec_pdf
    except ImportError:
        return
    doc = TechSpecDocument(
        title="Especificação Teste",
        markdown="# OBJETO\n\nTexto da especificação.",
        html_content=markdown_to_html("# OBJETO\n\nTexto da especificação."),
        formatting={"document_title": "Especificação Técnica — Teste"},
    )
    blob = export_tech_spec_pdf(doc)
    assert blob[:4] == b"%PDF"


def test_export_pdf_list_items_and_bold_labels():
    try:
        from pricing.spec.tech_spec_pdf import export_tech_spec_pdf
    except ImportError:
        return
    from pricing.spec.tech_spec_layout import parse_html_blocks

    md = (
        "## 3. DADOS DA OBRA\n\n"
        "- **Obra / Projeto:** Teste\n"
        "- **Local:** SP\n\n"
        "**Código WBS:** 1.1\n"
    )
    html = markdown_to_html(md)
    blocks = parse_html_blocks(html)
    list_blocks = [b for b in blocks if b.get("type") == "list_item"]
    assert len(list_blocks) == 2
    assert "**Obra / Projeto:**" in list_blocks[0]["text"]

    doc = TechSpecDocument(
        title="Especificação Teste",
        markdown=md,
        html_content=html,
        formatting={"document_title": "Especificação Técnica — Teste", "margin_left_cm": 3},
    )
    blob = export_tech_spec_pdf(doc)
    assert blob[:4] == b"%PDF"
    assert len(blob) > 500


def test_document_blocks_for_export_skips_preview_chrome():
    from pricing.spec.tech_spec_layout import document_blocks_for_export
    from pricing.spec.tech_spec_models import render_document_html

    md = "# CORPO\n\n- item um\n"
    doc = TechSpecDocument(markdown=md, html_content=markdown_to_html(md))
    full = render_document_html(doc)
    blocks = document_blocks_for_export(full, md)
    types = [b["type"] for b in blocks]
    assert types.count("heading") == 1
    assert types[0] == "heading"
    assert blocks[0]["text"] == "CORPO"
    assert "list_item" in types

    session = _sample_session()
    events = list(compose_tech_spec_stream(session, use_llm=False))
    types = [e[0] for e in events]
    assert "log" in types
    assert "done" in types
    done = next(d for t, d in events if t == "done")
    md = done["tech_spec"]["markdown"]
    assert "### ETAPA 1" in md
    assert "### ETAPA 2" in md


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


def test_is_fields_complete():
    full = ServiceSpecFields(
        descricao="A" * 50,
        materiais="m",
        metodo_executivo="m",
        criterio_medicao="m",
        base_precos="b",
        normas="n",
    )
    assert is_fields_complete(full) is True
    assert is_fields_complete(None) is False
    assert is_fields_complete(ServiceSpecFields("curta", "m", "m", "m", "b", "n")) is False


def test_compose_retries_incomplete_service():
    session = _sample_session()
    calls = {"n": 0}
    incomplete = "**Descrição:** Curta.\n**Materiais:** x\n"
    complete = (
        "**Descrição:** " + ("Escavação manual em solo de primeira categoria. " * 3) + "\n"
        "**Materiais:** Ferramentas.\n"
        "**Método executivo:** Sequência operacional detalhada.\n"
        "**Critério de medição:** m³.\n"
        "**Base de Preços:** SINAPI.\n"
        "**Normas aplicáveis:** NR-18.\n"
    )

    class RetryClient:
        def generate_stream(self, prompt, model=None, fallback_models=None, format_json=False, options=None):
            calls["n"] += 1
            text = incomplete if calls["n"] == 1 else complete
            yield text, "fake-model"

    events = list(compose_tech_spec_stream(session, use_llm=True, llm_client=RetryClient()))
    logs = [d["message"] for t, d in events if t == "log"]
    assert any("retentativa 2" in m for m in logs)
    assert calls["n"] >= 2
    done = next(d for t, d in events if t == "done")
    assert "#### SUB-ETAPA 1.1.1" in done["tech_spec"]["markdown"]


def test_compose_with_mock_llm():
    session = _sample_session()

    class FakeClient:
        def generate_stream(self, prompt, model=None, fallback_models=None, format_json=False, options=None):
            _ = (prompt, model, fallback_models, format_json, options)
            text = (
                "**Descrição:** Serviço executado conforme projeto.\n"
                "**Materiais:** Conforme composição.\n"
                "**Método executivo:** Sequência operacional padrão.\n"
                "**Critério de medição:** Unidade contratada.\n"
                "**Base de Preços:** SINAPI.\n"
                "**Normas aplicáveis:** NR-18.\n"
            )
            yield text, "fake-model"

    events = list(compose_tech_spec_stream(session, use_llm=True, llm_client=FakeClient()))
    done = next(d for t, d in events if t == "done")
    md = done["tech_spec"]["markdown"]
    assert "### ETAPA 1" in md
    assert "#### SUB-ETAPA 1.1.1" in md
    assert "### ETAPA 2" in md
    assert done["llm_model"] == "fake-model"


if __name__ == "__main__":
    test_parse_service_fields()
    test_render_service_markdown_structure()
    test_assemble_spec_markdown_partial()
    test_is_fields_complete()
    test_compose_retries_incomplete_service()
    test_compose_with_mock_llm()
    test_etapa_json_payload()
    test_assemble_spec_from_etapas()
    test_truncate_at_extra_service()
    test_has_repetition_loop_ignores_service_template()
    test_iter_spec_chunks_one_per_service()
    test_build_section_six_preserves_order()
    test_sanitize_llm_chunk()
    test_assemble_spec_includes_all_services()
    test_find_missing_service_codes()
    test_service_mentioned_by_name_or_heading()
    test_append_missing_inserts_before_section_seven()
    test_collect_wbs_inventory()
    test_build_budget_context()
    test_build_budget_context_with_schedule()
    test_fallback_spec_covers_all_etapas()
    test_parse_format_directives_full_prompt()
    test_parse_format_directives_page_center_and_no_numbers()
    test_apply_format_edits_page_numbers_and_logo()
    test_edit_format_only_stream()
    test_render_document_html()
    test_markdown_to_html()
    test_export_docx()
    test_export_pdf()
    test_compose_heuristic_stream()
    test_session_store_tech_spec()
    print("OK: testes tech_spec passaram")
