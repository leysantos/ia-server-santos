"""Testes — purge de importações genéricas CBMAM."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.knowledge.document_admin import is_generic_legislation_import


def test_is_generic_legislation_import_detects_numeric_pdf():
    assert is_generic_legislation_import(
        {"name": "Instrução Técnica", "filename": "87.pdf"}
    )


def test_is_generic_legislation_import_skips_named_assunto():
    assert not is_generic_legislation_import(
        {
            "name": "Instrução Técnica Nº 2/2019 - Conceitos básicos de segurança contra incêndio.",
            "filename": "IT_2_Conceitos.pdf",
        }
    )
