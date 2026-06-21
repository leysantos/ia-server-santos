"""Testes — extração de título para catálogo NBR/NR."""

from core.knowledge.norm_bulk.title_extract import (
    extract_title_from_filename,
    is_bare_norm_name,
)


def test_extract_nbr_title_from_filename():
    title = extract_title_from_filename(
        "NBR 6118 - 2014 - Projeto de Estruturas de Concreto.pdf",
        norm_kind="NBR",
        norm_code="6118",
    )
    assert title == "NBR 6118 - Projeto de Estruturas de Concreto"


def test_extract_it_title_from_filename():
    title = extract_title_from_filename(
        "2019_-_Saídas_de_emergência..pdf",
        norm_kind="NBR",
        norm_code=None,
    )
    assert title is not None
    assert "Saídas" in title or "emergência" in title


def test_is_bare_norm_name():
    assert is_bare_norm_name("NBR 6118", "6118")
    assert not is_bare_norm_name("NBR 6118 - Projeto de Estruturas de Concreto", "6118")
