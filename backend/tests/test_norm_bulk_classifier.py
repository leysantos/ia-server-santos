"""Testes — classificação em lote NBR/NR."""

from pathlib import Path

import pytest

from core.knowledge.norm_bulk.classifier import classify_norm_pdf
from core.knowledge.norm_bulk.nr_catalog import infer_nr_discipline, parse_nr_code


def test_parse_nr_code_from_filename():
    assert parse_nr_code("NR-10.pdf") == "10"
    assert parse_nr_code("nr_35_seguranca.pdf") == "35"
    assert parse_nr_code("Norma Regulamentadora 12.pdf") == "12"


def test_infer_nr_discipline():
    assert infer_nr_discipline("10") == "ELÉTRICA"
    assert infer_nr_discipline("35") == "SEGURANCA"


def test_classify_nbr_from_filename(tmp_path: Path):
    pdf = tmp_path / "NBR 6118 - 2014 - Projeto de Estruturas de Concreto.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    result = classify_norm_pdf(pdf)
    assert result.content_type == "nbrs"
    assert result.metadata.get("norm_kind") == "NBR"
    assert result.metadata.get("nbr") == "6118"
    assert "Projeto de Estruturas" in (result.metadata.get("norm_display_name") or "")
    assert result.mapped_discipline == "ESTRUTURAL"
    assert result.confidence >= 0.9


def test_classify_nr_from_filename(tmp_path: Path):
    pdf = tmp_path / "NR-10-Eletrica.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    result = classify_norm_pdf(pdf)
    assert result.metadata.get("norm_kind") == "NR"
    assert result.metadata.get("nr") == "10"
    assert result.mapped_discipline == "ELÉTRICA"


def test_classify_in_sicro_from_filename(tmp_path: Path):
    pdf = tmp_path / "IN-002-2020 SICRO - Composicoes de Custos.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    result = classify_norm_pdf(pdf)
    assert result.metadata.get("norm_kind") == "IN_SICRO"
    assert result.mapped_discipline == "ORÇAMENTO"
    assert result.content_type == "nbrs"
    assert result.confidence >= 0.9


def test_mark_edition_outdated_flag(tmp_path: Path):
    pdf = tmp_path / "NBR-9050.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    result = classify_norm_pdf(pdf, mark_edition_outdated=True)
    assert result.metadata.get("edition_outdated") is True
    assert "histórico" in (result.metadata.get("edition_note") or "")
