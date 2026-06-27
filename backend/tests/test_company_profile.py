"""Testes do cadastro da empresa (configuração do sistema)."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.system.company_profile import (
    PROFILE_PATH,
    CompanyProfile,
    get_company_profile,
    save_company_profile,
    update_company_profile,
)


@pytest.fixture(autouse=True)
def _isolate_profile(tmp_path, monkeypatch):
    path = tmp_path / "company_profile.json"
    monkeypatch.setattr("core.system.company_profile.PROFILE_PATH", path)
    yield


def test_company_profile_save_and_load():
    profile = CompanyProfile(
        razao_social="Santos Engenharia LTDA",
        nome_fantasia="Santos Eng",
        cidade="Manaus",
        uf="AM",
        responsavel_tecnico="Francirley Santos",
        rt_crea="31.410-AM",
    )
    save_company_profile(profile)
    loaded = get_company_profile()
    assert loaded.razao_social == "Santos Engenharia LTDA"
    assert loaded.rt_crea == "31.410-AM"


def test_company_profile_endereco_linha():
    p = CompanyProfile(
        endereco="Av. Teste",
        numero="100",
        bairro="Centro",
        cidade="Manaus",
        uf="AM",
        cep="69000-000",
    )
    line = p.endereco_linha()
    assert "Av. Teste" in line
    assert "Manaus/AM" in line
