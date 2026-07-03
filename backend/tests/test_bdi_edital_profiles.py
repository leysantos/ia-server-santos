"""Testes BDI edital / decomposição TCU."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pricing.budget.bdi_edital_profiles import (
    BdiTcuComponents,
    get_bdi_edital_profile,
    list_bdi_edital_profiles,
)
from pricing.models.budget_metadata import BdiConfig


def test_tcu_formula():
    comp = BdiTcuComponents(
        administracao_central=0.05,
        garantias_seguros=0.005,
        riscos=0.01,
        despesas_financeiras=0.018,
        lucro=0.06,
        tributos=0.0565,
    )
    rate = comp.compute_rate()
    assert 0.20 < rate < 0.23


def test_edital_profile_list():
    profiles = list_bdi_edital_profiles()
    ids = {p["id"] for p in profiles}
    assert "seminf_table" in ids
    assert "tcu_obra_civil" in ids
    assert "custom_edital" in ids


def test_bdi_config_from_profile():
    profile = get_bdi_edital_profile("tcu_obra_civil")
    assert profile is not None
    cfg = BdiConfig.from_profile(profile, obra_type="RF")
    assert cfg.source == "edital"
    assert cfg.rate_com_desoneracao > 0
    assert cfg.rate_sem_desoneracao > 0


def test_seminf_profile_still_works():
    cfg = BdiConfig.from_obra_type("RF")
    assert cfg.source == "seminf"
    assert cfg.rate_com_desoneracao == 0.2426
