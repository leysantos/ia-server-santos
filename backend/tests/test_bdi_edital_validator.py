"""Testes B26 — validador BDI vs edital."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pricing.budget.bdi_edital_profiles import BdiTcuComponents, get_bdi_edital_profile
from pricing.budget.bdi_edital_validator import bdi_checklist_status, validate_bdi_config
from pricing.budget.budget_compliance_pack import build_compliance_pack
from pricing.budget.budget_session import SESSION_STORE
from pricing.budget.budget_structure import add_etapa
from pricing.budget.ppd_template import create_empty_ppd_metadata
from pricing.models.budget_metadata import BdiConfig


def test_validate_seminf_profile_ok():
    cfg = BdiConfig.from_obra_type("RF")
    result = validate_bdi_config(cfg)
    assert result["status"] == "ok"
    assert result["valid_for_edital"] is True
    assert result["issue_count"] == 0


def test_validate_rate_exceeds_edital_max():
    profile = get_bdi_edital_profile("tcu_obra_civil")
    assert profile is not None
    cfg = BdiConfig.from_profile(profile, obra_type="RF")
    cfg.rate_com_desoneracao = 0.35
    result = validate_bdi_config(cfg)
    assert result["status"] == "error"
    assert any(i["code"] == "bdi_rate_comd_exceeds_max" for i in result["issues"])


def test_compliance_l3_uses_validator():
    SESSION_STORE._sessions.clear()
    meta = create_empty_ppd_metadata()
    meta.bdi = BdiConfig.from_profile(get_bdi_edital_profile("tcu_obra_civil"), obra_type="RF")
    meta.bdi.rate_com_desoneracao = 0.35
    roots = []
    add_etapa(roots, "ETAPA", meta)
    session = SESSION_STORE.create(roots=roots, title="BDI", intent={}, project=meta)
    pack = build_compliance_pack(session)
    l3 = next(c for c in pack["checklist_lei_14133"] if c["id"] == "L3")
    assert l3["status"] == "revisar"
    assert pack["bdi_validation_status"] == "revisar"


def test_bdi_checklist_status_ok_for_seminf():
    cfg = BdiConfig.from_obra_type("ED")
    assert bdi_checklist_status(cfg) == "ok"


def test_custom_edital_warns_without_components():
    cfg = BdiConfig.from_dict(
        {
            "profile_id": "custom_edital",
            "source": "custom",
            "obra_type": "RF",
            "rate_com_desoneracao": 0.25,
            "rate_sem_desoneracao": 0.23,
        }
    )
    result = validate_bdi_config(cfg)
    assert result["status"] == "warning"
    assert any(i["code"] == "bdi_custom_components_missing" for i in result["issues"])
