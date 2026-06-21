"""Testes — export CSV e gaps do wizard."""

from __future__ import annotations

from core.knowledge.norm_packs.gap_export import build_gap_csv, export_project_gaps_csv
from core.knowledge.norm_packs.project_gaps import (
    compute_project_norm_gaps,
    resolve_pack_ids_for_disciplines,
)


def test_resolve_pack_ids_includes_documentacao_and_discipline():
    ids = resolve_pack_ids_for_disciplines(["eletrica", "drenagem"])
    assert "documentacao_projetos" in ids
    assert "disc_eletrica" in ids
    assert "disc_drenagem" in ids


def test_build_gap_csv_contains_headers_and_nbr():
    analysis = {
        "label": "Elétrica",
        "summary": {"coverage_pct": 50.0},
        "items": [
            {
                "nbr_code": "5410",
                "title": "Instalações elétricas",
                "discipline": "ELÉTRICA",
                "critical": True,
                "status": "missing",
                "chunk_count": 0,
                "legal_source": "missing",
                "filename": None,
            }
        ],
    }
    csv_text = build_gap_csv(analysis)
    assert "NBR" in csv_text
    assert "5410" in csv_text
    assert "Adquirir PDF ABNT" in csv_text


def test_export_project_gaps_csv():
    gaps = {
        "summary_message": "2 críticas faltando",
        "critical_missing_count": 2,
        "critical_not_indexed_count": 0,
        "pending_items": [
            {
                "nbr_code": "8196",
                "title": "Folha de desenho",
                "status": "missing",
                "critical": True,
                "pack_label": "Documentação",
                "discipline": "DOCUMENTACAO",
                "action": "Comprar",
            }
        ],
    }
    filename, content = export_project_gaps_csv(gaps)
    assert filename.endswith(".csv")
    assert "8196" in content


def test_compute_project_norm_gaps_structure():
    result = compute_project_norm_gaps(["eletrica"])
    assert "documentacao_projetos" in result["pack_ids"]
    assert "disc_eletrica" in result["pack_ids"]
    assert "summary_message" in result
    assert "pending_items" in result
