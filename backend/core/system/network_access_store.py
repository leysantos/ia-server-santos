"""Configuração de acesso — rede interna e Cloudflare Tunnel."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from config.settings import DATA_DIR, get_settings

NETWORK_ACCESS_PATH = DATA_DIR / "system" / "network_access.json"


@dataclass
class InternalNetworkConfig:
    enabled: bool = True
    host_ip: str = ""
    api_port: int = 8000
    frontend_port: int = 3000
    api_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    allowed_cidrs: list[str] = field(
        default_factory=lambda: ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
    )
    bind_api_all_interfaces: bool = True
    notes: str = ""


@dataclass
class CloudflareAccessConfig:
    enabled: bool = False
    tunnel_name: str = ""
    tunnel_id: str = ""
    tunnel_token: str = ""
    account_id: str = ""
    zone_id: str = ""
    public_hostname: str = ""
    public_api_url: str = ""
    public_frontend_url: str = ""
    access_application_name: str = ""
    access_policy: str = ""
    warp_required: bool = False
    notes: str = ""


@dataclass
class NetworkAccessConfig:
    internal: InternalNetworkConfig = field(default_factory=InternalNetworkConfig)
    cloudflare: CloudflareAccessConfig = field(default_factory=CloudflareAccessConfig)
    cors_extra_origins: list[str] = field(default_factory=list)

    def to_dict(self, *, mask_secrets: bool = True) -> dict[str, Any]:
        cf = asdict(self.cloudflare)
        if mask_secrets and cf.get("tunnel_token"):
            token = cf["tunnel_token"]
            cf["tunnel_token"] = ""
            cf["tunnel_token_configured"] = bool(token)
            cf["tunnel_token_hint"] = f"…{token[-6:]}" if len(token) > 6 else "••••••"
        else:
            cf["tunnel_token_configured"] = bool(cf.get("tunnel_token"))
            cf.pop("tunnel_token_hint", None)
        return {
            "internal": asdict(self.internal),
            "cloudflare": cf,
            "cors_extra_origins": list(self.cors_extra_origins),
            "suggested_cors_origins": self.suggested_cors_origins(),
        }

    def suggested_cors_origins(self) -> list[str]:
        origins: list[str] = []
        if self.internal.enabled and self.internal.frontend_url:
            origins.append(self.internal.frontend_url.rstrip("/"))
        if self.cloudflare.enabled:
            for url in (self.cloudflare.public_frontend_url, self.cloudflare.public_api_url):
                if url:
                    origins.append(url.rstrip("/"))
        origins.extend(o.rstrip("/") for o in self.cors_extra_origins if o)
        base = get_settings().cors_allowed_origins
        merged: list[str] = []
        for item in [*base, *origins]:
            if item and item not in merged:
                merged.append(item)
        return merged

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> NetworkAccessConfig:
        internal_raw = raw.get("internal") if isinstance(raw.get("internal"), dict) else {}
        cf_raw = raw.get("cloudflare") if isinstance(raw.get("cloudflare"), dict) else {}
        current = cls()
        internal = InternalNetworkConfig(
            **{k: v for k, v in internal_raw.items() if k in InternalNetworkConfig.__dataclass_fields__}
        )
        cf_fields = CloudflareAccessConfig.__dataclass_fields__
        cf_data = {k: v for k, v in cf_raw.items() if k in cf_fields}
        if not cf_data.get("tunnel_token") and cf_raw.get("tunnel_token_configured"):
            cf_data["tunnel_token"] = current.cloudflare.tunnel_token
        cloudflare = CloudflareAccessConfig(**cf_data)
        extra = raw.get("cors_extra_origins")
        cors_extra = list(extra) if isinstance(extra, list) else []
        return cls(internal=internal, cloudflare=cloudflare, cors_extra_origins=cors_extra)


def _ensure_dir() -> None:
    NETWORK_ACCESS_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_network_access_config() -> NetworkAccessConfig:
    _ensure_dir()
    if not NETWORK_ACCESS_PATH.exists():
        return NetworkAccessConfig()
    try:
        raw = json.loads(NETWORK_ACCESS_PATH.read_text(encoding="utf-8"))
        return NetworkAccessConfig.from_dict(raw if isinstance(raw, dict) else {})
    except (json.JSONDecodeError, OSError):
        return NetworkAccessConfig()


def save_network_access_config(data: dict[str, Any]) -> NetworkAccessConfig:
    _ensure_dir()
    current = get_network_access_config()
    merged = current.to_dict(mask_secrets=False)

    if isinstance(data.get("internal"), dict):
        merged["internal"] = {**merged["internal"], **data["internal"]}
    if isinstance(data.get("cloudflare"), dict):
        cf_patch = dict(data["cloudflare"])
        if not cf_patch.get("tunnel_token") and merged["cloudflare"].get("tunnel_token"):
            cf_patch["tunnel_token"] = merged["cloudflare"]["tunnel_token"]
        merged["cloudflare"] = {**merged["cloudflare"], **cf_patch}
    if "cors_extra_origins" in data and isinstance(data["cors_extra_origins"], list):
        merged["cors_extra_origins"] = data["cors_extra_origins"]

    config = NetworkAccessConfig.from_dict(merged)
    to_save = config.to_dict(mask_secrets=False)
    NETWORK_ACCESS_PATH.write_text(
        json.dumps(to_save, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return config


def network_access_status() -> dict[str, Any]:
    from core.system.quick_tunnel_service import quick_tunnel_status

    config = get_network_access_config()
    settings = get_settings()
    return {
        **config.to_dict(mask_secrets=True),
        "auth_enabled": settings.auth_enabled,
        "env_cors_origins": settings.cors_allowed_origins,
        "effective_access_mode": _effective_mode(config),
        "quick_tunnel": quick_tunnel_status(),
    }


def _effective_mode(config: NetworkAccessConfig) -> str:
    from core.system.quick_tunnel_service import quick_tunnel_status

    qt = quick_tunnel_status()
    if qt.get("running"):
        if config.internal.enabled:
            return "quick-tunnel+internal"
        return "quick-tunnel"
    if config.cloudflare.enabled and config.internal.enabled:
        return "hybrid"
    if config.cloudflare.enabled:
        return "cloudflare"
    if config.internal.enabled:
        return "internal"
    return "local"
