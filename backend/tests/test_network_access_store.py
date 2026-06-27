"""Testes do store de configuração de rede."""

from core.system.network_access_store import (
    get_network_access_config,
    network_access_status,
    save_network_access_config,
)


def test_network_access_persists(network_path, monkeypatch):
    monkeypatch.setattr(
        "core.system.network_access_store.NETWORK_ACCESS_PATH",
        network_path,
    )
    save_network_access_config(
        {
            "internal": {"host_ip": "192.168.1.10", "api_base_url": "http://192.168.1.10:8000"},
            "cloudflare": {"enabled": True, "public_hostname": "ia.exemplo.com"},
        }
    )
    loaded = get_network_access_config()
    assert loaded.internal.host_ip == "192.168.1.10"
    assert loaded.cloudflare.public_hostname == "ia.exemplo.com"


def test_network_access_masks_tunnel_token(network_path, monkeypatch):
    monkeypatch.setattr(
        "core.system.network_access_store.NETWORK_ACCESS_PATH",
        network_path,
    )
    save_network_access_config({"cloudflare": {"tunnel_token": "secret-token-abc123"}})
    status = network_access_status()
    assert status["cloudflare"]["tunnel_token"] == ""
    assert status["cloudflare"]["tunnel_token_configured"] is True


import pytest


@pytest.fixture
def network_path(tmp_path):
    return tmp_path / "network_access.json"
