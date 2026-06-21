"""Testes — relatório CSV de importação em lote NBR/NR."""

from core.knowledge.norm_bulk.bulk_report import (
    attach_bulk_audit_report,
    build_audit_rows_from_bulk_result,
    build_bulk_audit_csv,
)


def test_build_audit_rows_from_result():
    result = {
        "results": [
            {
                "source": "/tmp/NBR-6118.pdf",
                "target": "/data/NBR-6118.pdf",
                "status": "copied",
                "document_id": "abc-123",
                "classification": {
                    "mapped_discipline": "ESTRUTURAL",
                    "discipline_slug": "estruturas",
                    "confidence": 0.94,
                    "source": "nbr_filename",
                    "metadata": {
                        "norm_kind": "NBR",
                        "norm_code": "6118",
                        "norm_label": "NBR 6118",
                        "edition_outdated": True,
                    },
                },
            },
            {
                "source": "/tmp/outro.pdf",
                "status": "skipped_duplicate",
                "reason": "Arquivo idêntico já está no catálogo.",
                "classification": {
                    "mapped_discipline": "GERAL",
                    "discipline_slug": "geral",
                    "confidence": 0.5,
                    "source": "filename_heuristic",
                    "metadata": {"filename": "outro.pdf"},
                },
            },
        ],
        "errors": [
            {"filename": "quebrado.pdf", "error": "PDF inválido"},
        ],
    }
    rows = build_audit_rows_from_bulk_result(result)
    assert len(rows) == 3
    by_name = {r["filename"]: r for r in rows}
    assert by_name["NBR-6118.pdf"]["discipline"] == "ESTRUTURAL"
    assert by_name["NBR-6118.pdf"]["status"] == "copied"
    assert by_name["NBR-6118.pdf"]["edition_outdated"] == "sim"
    assert by_name["quebrado.pdf"]["status"] == "error"


def test_build_bulk_audit_csv_has_bom_and_headers():
    result = attach_bulk_audit_report(
        {
            "total_files": 1,
            "ingested": 1,
            "skipped": 0,
            "errors": [],
            "results": [
                {
                    "source": "/tmp/NR-10.pdf",
                    "status": "copied",
                    "classification": {
                        "mapped_discipline": "ELÉTRICA",
                        "discipline_slug": "eletrica",
                        "confidence": 0.92,
                        "source": "nr_filename",
                        "metadata": {
                            "norm_kind": "NR",
                            "norm_code": "10",
                            "norm_label": "NR-10",
                        },
                    },
                }
            ],
        }
    )
    csv_text = result["report_csv"]
    assert csv_text.startswith("\ufeff")
    assert "Arquivo" in csv_text
    assert "NR-10.pdf" in csv_text
    assert "ELÉTRICA" in csv_text
    assert result["report_filename"].startswith("auditoria-importacao-nbr-")
