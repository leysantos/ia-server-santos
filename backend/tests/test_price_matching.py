"""Testes — importação e matching de preços."""

from __future__ import annotations

from pathlib import Path

import pytest

from pricing.budget.price_matching_catalog import normalize_unit, units_compatible
from pricing.budget.price_matching_import import (
    ImportedPriceRow,
    parse_excel_rows,
    parse_pdf_rows,
    _parse_budget_pdf_line,
    _parse_table_line,
)
from pricing.budget.price_matching_service import PriceMatchingService, extract_code_from_description


def test_extract_code_sinapi():
    base, code = extract_code_from_description("TAPUME SINAPI 98459 com lona")
    assert base == "SINAPI"
    assert code == "98459"


def test_extract_code_bare():
    base, code = extract_code_from_description("Serviço código 98459")
    assert base is None
    assert code == "98459"


def test_parse_budget_pdf_line_full():
    row = _parse_budget_pdf_line("2.1 TAPUME COM LONA PLÁSTICA M2 235,06")
    assert row is not None
    assert row.item == "2.1"
    assert "TAPUME" in row.descricao
    assert row.unidade == "M²"
    assert row.quantidade == pytest.approx(235.06)


def test_parse_budget_pdf_line_engineer():
    row = _parse_budget_pdf_line("1.1 ENGENHEIRO CIVIL H 352,00")
    assert row is not None
    assert row.item == "1.1"
    assert row.unidade == "H"
    assert row.quantidade == pytest.approx(352.0)


def test_parse_budget_pdf_line_skips_unit_only():
    assert _parse_budget_pdf_line("3.1 M3 11,19") is None


def test_parse_pdf_example_file():
    from pathlib import Path

    p = Path(__file__).resolve().parents[2] / "planilhas-exemplos" / "planilha-exemplo-lancar-preco.pdf"
    if not p.is_file():
        pytest.skip("PDF de exemplo ausente")
    rows = parse_pdf_rows(p)
    assert len(rows) >= 20
    tapume = next((r for r in rows if "TAPUME" in r.descricao.upper()), None)
    assert tapume is not None
    assert tapume.quantidade == pytest.approx(235.06)


def test_units_compatible():
    assert units_compatible("M²", "m2")
    assert units_compatible("UN", "und")
    assert not units_compatible("M²", "M³")


def test_normalize_unit():
    assert normalize_unit("M²") == "m2"
    assert normalize_unit("und") == "un"


def test_description_match_score_engenheiro_civil():
    from pricing.budget.price_matching_catalog import description_match_score

    import_desc = "ENGENHEIRO CIVIL"
    catalog_desc = "ENGENHEIRO CIVIL DE OBRA SENIOR COM ENCARGOS COMPLEMENTARES"
    score = description_match_score(import_desc, catalog_desc, unit="H", catalog_unit="h")
    assert score >= 0.9


def test_description_match_score_exact():
    from pricing.budget.price_matching_catalog import description_match_score

    assert description_match_score("TAPUME COM LONA", "TAPUME COM LONA", unit="M2", catalog_unit="m²") == 1.0


def test_description_match_score_rejects_wrong_pairs():
    from pricing.budget.price_matching_catalog import description_match_score

    cases = [
        (
            "PLACA DE OBRA EM LONA DE VINIL - FORNECIMENTO E INST",
            "LUVA, PVC, SOLDAVEL, DN 25MM, INSTALADO EM PRUMADA DE AGUA",
        ),
        (
            "TAPUME COM LONA PLASTICA",
            "TRAMA DE ACO COMPOSTA POR TERÇAS PARA TELHADOS DE ATE 2 AGUAS",
        ),
        (
            "REMOCAO DE BANCADA DE GRANITO",
            "LIMPEZA DE BANCADA COM PLACA DE ROCHA (MARMORE OU GRANITO)",
        ),
        (
            "RASGO LINEAR MANUAL EM ALVENARIA PARA PASSAGEM",
            "TRANSPORTE HORIZONTAL MANUAL, DE TUBO DE PVC SERIE NORMAL",
        ),
        (
            "PORTICO EM ACM ESTRUTURADO PARA FACHADA",
            "REVESTIMENTO DECORATIVO MONOCAMADA EXECUTADO COM EQUIPAMENTO DE PROJECAO EM FACHADA",
        ),
    ]
    for imp, cat in cases:
        score = description_match_score(imp, cat, unit="M2", catalog_unit="m2")
        assert score < 0.80, f"expected <80% for: {imp[:40]} vs {cat[:40]} got {score}"


def test_imported_code_rejected_when_description_diverges(monkeypatch):
    from pricing.budget.price_matching_catalog import CatalogEntry
    from pricing.budget.price_matching_service import PriceMatchingService

    wrong = CatalogEntry(
        base="SINAPI",
        source="sinapi",
        reference="BR-2026-05",
        code="98928",
        description="LUVA, PVC, SOLDAVEL, DN 25MM, INSTALADO EM PRUMADA DE AGUA",
        unit="M",
        price=4.42,
        default_uf="AM",
    )

    def fake_lookup(code, base_hint, **kwargs):
        return wrong if code == "98928" else None

    monkeypatch.setattr(
        "pricing.budget.price_matching_service._lookup_by_code",
        fake_lookup,
    )
    monkeypatch.setattr(
        "pricing.budget.price_matching_service._text_candidates",
        lambda *a, **k: [],
    )

    svc = PriceMatchingService(uf="AM", use_llm=False)
    result = svc.match_row(
        "PLACA DE OBRA EM LONA DE VINIL - FORNECIMENTO E INSTALACAO",
        "M2",
        1.2,
        imported_code="98928",
    )
    assert result.entry is None
    assert (result.score or 0) < 0.80


def test_suggest_tier_assigns_price_below_auto_threshold(monkeypatch):
    from pricing.budget.price_matching_catalog import CatalogEntry
    from pricing.budget.price_matching_service import MatchResult, PriceMatchingService

    entry = CatalogEntry(
        base="SINAPI",
        source="sinapi",
        reference="BR-2026-05",
        code="104761",
        description="FURO MECANIZADO EM CONCRETO, COM MARTELO DEMOLIDOR",
        unit="UN",
        price=12.53,
        default_uf="AM",
    )

    def fake_candidates(*args, **kwargs):
        return [(0.58, entry)]

    monkeypatch.setattr("pricing.budget.price_matching_service._text_candidates", fake_candidates)
    monkeypatch.setattr(
        "pricing.budget.price_matching_service._lookup_by_code",
        lambda *a, **k: None,
    )

    svc = PriceMatchingService(uf="AM", use_llm=False)
    result = svc.match_row("LIMPEZA DE FURO EM PILAR DE CONCRETO ARMADO", "UN", 1.0)
    priced = svc.apply_pricing(result, 2.0)
    assert priced["codigo_base"] == "104761"
    assert priced["valor_unitario"] == pytest.approx(12.53)
    assert priced["status"] in ("review", "matched")
    assert (priced["score_confianca"] or 0) >= 0.52


def test_parse_excel_hierarchy_example():
    p = Path(__file__).resolve().parents[2] / "planilhas-exemplos" / "planilha-exemplo-lancar-preco.xlsx"
    if not p.is_file():
        pytest.skip("Planilha de exemplo ausente")
    from pricing.budget.price_matching_hierarchy import hierarchy_stats, parse_excel_hierarchy

    lines = parse_excel_hierarchy(p)
    stats = hierarchy_stats(lines)
    assert len(lines) == 283
    assert stats["servicos"] == 244
    assert stats["etapas"] == 14
    eng = next(l for l in lines if l.item == "1.1")
    assert eng.descricao == "ENGENHEIRO CIVIL"
    assert eng.unidade == "H"
    assert eng.quantidade == pytest.approx(352.0)
    sub = next(l for l in lines if l.item == "4.1")
    assert sub.row_type == "SUB_ETAPA"
    assert sub.descricao == "VIGA BALDRAME"


def test_item_from_excel_date_cell():
    from datetime import datetime

    from pricing.budget.price_matching_import import _item_from_excel_cell

    assert _item_from_excel_cell(datetime(2010, 7, 2), "m\\.d\\.yy;@") == "7.2.10"
    assert _item_from_excel_cell(datetime(2011, 1, 1), "yy\\.m\\.d;@") == "11.1.1"


def test_parse_excel_rows(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    path = tmp_path / "orcamento.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Item", "Descrição", "Und", "Qtd"])
    ws.append(["2.1", "TAPUME COM LONA PLÁSTICA", "M²", 235.06])
    wb.save(path)
    rows = parse_excel_rows(path)
    assert len(rows) == 1
    assert rows[0].descricao == "TAPUME COM LONA PLÁSTICA"
    assert rows[0].quantidade == pytest.approx(235.06)


def test_price_matching_service_without_catalog(monkeypatch):
    monkeypatch.setattr(
        "pricing.budget.price_matching_service.load_catalog",
        lambda **_: ([], {}),
    )
    monkeypatch.setattr(
        "pricing.budget.price_matching_service._text_candidates",
        lambda *a, **k: [],
    )
    svc = PriceMatchingService(uf="AM", use_llm=False)
    result = svc.match_row("SERVICO GENERICO", "M2", 10)
    assert result.entry is None
    assert result.score == 0.0


def test_effective_base_order_from_selections():
    from pricing.budget.price_matching_catalog import effective_base_order

    order = effective_base_order(
        [
            {"source": "sinapi", "enabled": True, "reference": "BR-2024-01", "uf": "AM"},
            {"source": "sicro", "enabled": True, "reference": "BR-SICRO-AM-2024-01", "uf": "AM"},
        ]
    )
    assert order == ["SINAPI", "SICRO"]
    assert effective_base_order(None) == ["SEMINF", "SINAPI", "SICRO", "ORSE"]


def test_sync_hierarchy_codes_from_rows():
    from pricing.budget.price_matching_budget import sync_hierarchy_codes_from_rows

    job = {
        "hierarchy": [
            {"item": "1.1", "codigo": "", "descricao": "Serviço A", "row_type": "SERVICO"},
            {"item": "1", "codigo": "", "descricao": "Etapa", "row_type": "ETAPA"},
        ],
        "rows": [
            {"item": "1.1", "codigo_base": "98459"},
        ],
    }
    synced = sync_hierarchy_codes_from_rows(job)
    assert synced["hierarchy"][0]["codigo"] == "98459"
    assert synced["hierarchy"][1]["codigo"] == ""


def test_sync_priced_rows_applies_unit_cost_to_service_row_type_s():
    from pricing.budget.budget_session import SESSION_STORE
    from pricing.budget.ppd_layout import ROW_TYPE_SERVICO
    from pricing.budget.price_matching_budget import (
        build_budget_from_hierarchy,
        sync_priced_rows_to_session,
    )
    from pricing.budget.price_matching_hierarchy import ImportRowKind, ImportedBudgetLine

    lines = [
        ImportedBudgetLine(
            item="1",
            descricao="Etapa",
            unidade="",
            quantidade=0,
            row_type=ImportRowKind.ETAPA.value,
            row_index=0,
        ),
        ImportedBudgetLine(
            item="1.1",
            descricao="Serviço teste",
            unidade="M2",
            quantidade=10,
            row_type=ImportRowKind.SERVICO.value,
            row_index=1,
        ),
    ]
    job = {"obra": "Teste sync", "bdi": 0.25, "increase_index": 1.0, "id": "job-sync-test"}
    session_dict = build_budget_from_hierarchy(lines, job)
    session_id = session_dict["session_id"]

    job_with_rows = {
        **job,
        "session_id": session_id,
        "rows": [
            {
                "item": "1.1",
                "codigo_base": "98459",
                "descricao_base": "Tapume com lona",
                "base": "SINAPI",
                "valor_unitario": 150.0,
                "valor_unitario_base": 150.0,
                "score_confianca": 0.95,
                "match_level": "exact",
                "status": "matched",
            }
        ],
    }
    synced = sync_priced_rows_to_session(session_id, job_with_rows)
    assert synced["intent"]["price_matching_applied"] == 1

    session = SESSION_STORE.get(session_id)
    assert session is not None

    service = None

    def walk(items):
        nonlocal service
        for item in items:
            if item.row_type == ROW_TYPE_SERVICO and item.metadata.get("pdf_item") == "1.1":
                service = item
            walk(item.children)

    walk(session.roots)
    assert service is not None
    assert service.unit_cost == pytest.approx(150.0)
    assert service.unit_price == pytest.approx(150.0 * 1.25)
    assert service.source_code == "98459"
    assert service.metadata.get("confidence") == pytest.approx(0.95)


def test_bdi_apply_to_service_with_memory_child():
    from pricing.budget.bdi_calculator import BdiCalculator
    from pricing.budget.budget_structure import _make_memory_row
    from pricing.models.budget_item import BudgetItem
    from pricing.models.budget_metadata import BdiConfig

    svc = BudgetItem(
        code="2.1",
        name="Tapume",
        level=2,
        quantity=10,
        unit="M2",
        unit_cost=100.0,
        unit_cost_semd=95.0,
        unit_price=0,
        total_price=0,
        row_type="S",
    )
    svc.children = [_make_memory_row(svc, "quantidade = 10 M2")]
    bdi = BdiConfig(rate_com_desoneracao=0.25, rate_sem_desoneracao=0.20)
    BdiCalculator(bdi).apply_to_item(svc)
    assert svc.unit_price == pytest.approx(125.0)
    assert svc.unit_price_semd == pytest.approx(114.0)
    svc.recompute_total()


def test_apply_pricing_assigns_price_when_unit_mismatch():
    from pricing.budget.price_matching_catalog import CatalogEntry
    from pricing.budget.price_matching_service import MatchResult, PriceMatchingService

    entry = CatalogEntry(
        base="SINAPI",
        source="sinapi",
        reference="BR-2026-01",
        code="12345",
        description="Serviço teste",
        unit="UN",
        price=100.0,
        default_uf="AM",
    )
    match = MatchResult(
        entry=entry,
        score=0.45,
        level="text",
        candidates=[entry.to_dict()],
        unit_compatible=False,
    )
    svc = PriceMatchingService(use_llm=False)
    priced = svc.apply_pricing(match, 10.0, increase_index=1.0)
    assert priced["codigo_base"] is None
    assert priced["valor_unitario"] is None
    assert priced["status"] == "review"


def test_build_export_lines_hierarchy():
    from pricing.budget.price_matching_export import build_export_lines

    job = {
        "bdi": 0.266,
        "increase_index": 1.0,
        "hierarchy": [
            {"item": "1", "descricao": "Etapa A", "row_type": "ETAPA", "unidade": "", "quantidade": 0},
            {"item": "1.1", "descricao": "Sub A", "row_type": "SUB_ETAPA", "unidade": "", "quantidade": 0},
            {"item": "1.1.1", "descricao": "Serviço", "row_type": "SERVICO", "unidade": "M2", "quantidade": 10},
        ],
        "rows": [
            {
                "item": "1.1.1",
                "codigo_base": "98459",
                "base": "SINAPI",
                "valor_unitario_base": 50.0,
                "valor_unitario": 50.0,
                "score_confianca": 0.9,
            }
        ],
    }
    lines = build_export_lines(job)
    assert len(lines) == 3
    assert lines[0]["is_header"] is True
    assert lines[2]["codigo_base"] == "98459"
    assert lines[2]["valor_unitario_base"] == pytest.approx(50.0)


def test_export_xlsx_has_bdi_formulas(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    from pricing.budget.price_matching_export import export_price_matching_xlsx

    job = {
        "cliente": "Cliente X",
        "obra": "Obra Y",
        "bdi": 0.266,
        "increase_index": 1.2,
        "price_bases": [
            {"source": "sinapi", "label": "SINAPI", "enabled": True, "uf": "AM", "reference": "BR-2026-01"},
        ],
        "hierarchy": [
            {"item": "1", "descricao": "Etapa", "row_type": "ETAPA", "unidade": "", "quantidade": 0},
            {"item": "1.1", "descricao": "Serviço", "row_type": "SERVICO", "unidade": "M2", "quantidade": 2},
        ],
        "rows": [
            {
                "item": "1.1",
                "codigo_base": "111",
                "base": "SINAPI",
                "valor_unitario_base": 100.0,
                "score_confianca": 0.95,
            }
        ],
    }
    path = tmp_path / "out.xlsx"
    export_price_matching_xlsx(job, path)
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    assert ws["B4"].value == pytest.approx(26.6)
    assert ws["B5"].value == pytest.approx(1.2)
    assert "SINAPI" in str(ws["B6"].value)
    assert "BR-2026-01" in str(ws["B6"].value)
    service_row = 10
    assert str(ws.cell(row=service_row, column=7).value).startswith("=L")
    assert "/100" in str(ws.cell(row=service_row, column=8).value)
    assert ws.cell(row=service_row + 2, column=4).value == "Total s/ BDI"
    assert ws.cell(row=service_row + 3, column=4).value == "Valor BDI"
    assert ws.cell(row=service_row + 4, column=4).value == "Total c/ BDI"


def test_price_bases_header_lines():
    from pricing.budget.price_matching_export import _price_bases_header_lines

    job = {
        "price_bases": [
            {"source": "sinapi", "label": "SINAPI", "enabled": True, "uf": "AM", "reference": "BR-2026-05"},
            {"source": "sicro", "label": "SICRO", "enabled": False, "reference": "BR-SICRO-AM-2026-01"},
        ]
    }
    lines = _price_bases_header_lines(job)
    assert len(lines) == 1
    assert "SINAPI" in lines[0]
    assert "BR-2026-05" in lines[0]


def test_merge_job_price_bases_from_session():
    from pricing.budget.price_matching_budget import merge_job_price_bases

    job = {"id": "j1", "price_bases": []}
    session = {
        "project": {
            "price_bases": [
                {"source": "sicro", "label": "SICRO", "enabled": True, "uf": "TO", "reference": "BR-SICRO-TO-2026-01"}
            ]
        }
    }
    merged = merge_job_price_bases(job, session)
    assert len(merged["price_bases"]) == 1
    assert merged["price_bases"][0]["reference"] == "BR-SICRO-TO-2026-01"

