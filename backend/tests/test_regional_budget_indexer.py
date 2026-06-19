"""Testes do indexador regional SEMINF-AM."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.knowledge.regional_budget_indexer import (
    PUBLISHER,
    REGION,
    extract_regional_budget_model,
    generate_engineering_tags,
    is_amazonas_budget_workbook,
    normalize_service_code,
)

DOCS = Path(__file__).resolve().parent.parent / "knowledge" / "raw" / "documents"


def test_normalize_seminf_code():
    assert normalize_service_code(" 106913.22.9.SEMINF ") == "106913.22.9.SEMINF"
    assert normalize_service_code("2.1") == "2.1"


def test_tags_escavacao():
    tags = generate_engineering_tags("Escavação mecânica de vala em solo")
    assert "terraplanagem" in tags
    assert "solo" in tags


def test_is_amazonas_workbook_by_sheet_names():
    assert is_amazonas_budget_workbook(Path("orcamento.xlsx"), ["PLANILHA", "MCQ"])


def test_reforma_workbook_service_count():
    path = DOCS / "REFORMA_DE_PONTE_METALICA.xlsm"
    if not path.is_file():
        return
    model = extract_regional_budget_model(path)
    assert model["publisher"] == PUBLISHER
    assert model["region"] == REGION
    assert model["service_count"] >= 40
    first_svc = model["etapas"][0]["services"][0]
    assert "tags" in first_svc
    assert "name" in first_svc
