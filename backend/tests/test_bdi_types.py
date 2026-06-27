"""Testes BDI por tipo de obra."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.conftest import PPD_EXAMPLE_PATH, requires_ppd_example

PPD_PATH = PPD_EXAMPLE_PATH


def test_bdi_table_rates():
    from pricing.budget.bdi_types import OBRA_BDI_TABLE, get_obra_bdi

    rf = get_obra_bdi("RF")
    assert rf.rate_com_desoneracao == 0.2426
    assert rf.rate_sem_desoneracao == 0.2097

    ed = get_obra_bdi("ED")
    assert ed.rate_com_desoneracao == 0.2572

    ie = get_obra_bdi("EI")  # alias → IE
    assert ie.code == "IE"
    assert ie.rate_com_desoneracao == 0.2889

    see = get_obra_bdi("SEE")
    assert see.rate_com_desoneracao == 0.0
    assert see.rate_sem_desoneracao == 0.1772

    assert len(OBRA_BDI_TABLE) == 7


def test_detect_obra_type():
    from pricing.budget.bdi_types import detect_obra_type

    assert detect_obra_type(orcamento="PONTES", objeto="REFORMA DA PONTE") == "RF"
    assert detect_obra_type(text="instalação elétrica residencial") == "IE"
    assert detect_obra_type(text="obra portuária cais") == "OPMF"
    assert detect_obra_type(text="rede de água e esgoto") == "AG"
    assert detect_obra_type(text="edificação comercial") == "ED"


@requires_ppd_example
def test_ppd_import_detects_rf():
    from pricing.budget.ppd_parser import parse_ppd_workbook

    metadata, _, _ = parse_ppd_workbook(PPD_PATH)
    assert metadata.obra_type == "RF"
    assert metadata.bdi.rate_com_desoneracao == 0.2426


def test_bdi_change_recalculates_session():
    from pricing.bootstrap import ensure_providers_registered, load_default_bases, reset_providers
    from pricing.budget.budget_engine_v2 import BudgetEngineV2
    from pricing.budget.budget_session import SESSION_STORE

    reset_providers()
    SESSION_STORE._sessions.clear()
    ensure_providers_registered()
    load_default_bases(Path(__file__).resolve().parent.parent / "pricing" / "data")

    engine = BudgetEngineV2()
    session = engine.generate_session(
        {"scope": "alvenaria", "dimensions": {"length": 10, "height": 2}, "obra_type": "RF"},
        source_priority=["sinapi"],
    )
    total_rf = session.grand_total

    updated = engine.set_obra_type(session.id, "ED")
    assert updated.project.obra_type == "ED"
    assert updated.project.bdi.rate_com_desoneracao == 0.2572
    assert updated.grand_total != total_rf
