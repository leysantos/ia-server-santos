"""Personalização global de exportação (cabeçalho/rodapé) — persistência em disco."""

from __future__ import annotations

import json
from typing import Any

from config.settings import DATA_DIR
from core.system.company_profile import get_company_profile
from pricing.budget.budget_export_branding import ExportBrandingConfig

BRANDING_PATH = DATA_DIR / "system" / "export_branding.json"


def _ensure_dir() -> None:
    BRANDING_PATH.parent.mkdir(parents=True, exist_ok=True)


def _defaults_from_company() -> ExportBrandingConfig:
    profile = get_company_profile()
    footer2_parts = [p for p in (profile.email, profile.telefone) if p]
    header3_parts = [p for p in (f"CNPJ: {profile.cnpj}" if profile.cnpj else "", profile.site) if p]
    return ExportBrandingConfig(
        header_line1=profile.display_name(),
        header_line2="",
        header_line3=" · ".join(header3_parts),
        footer_line1=profile.responsavel_linha(),
        footer_line2=" · ".join(footer2_parts),
        show_logo=True,
        show_brasao=True,
    )


def get_global_export_branding() -> ExportBrandingConfig:
    _ensure_dir()
    if not BRANDING_PATH.exists():
        return _defaults_from_company()
    try:
        raw = json.loads(BRANDING_PATH.read_text(encoding="utf-8"))
        branding = ExportBrandingConfig.from_dict(raw if isinstance(raw, dict) else {})
    except (json.JSONDecodeError, OSError):
        return _defaults_from_company()
    defaults = _defaults_from_company()
    return ExportBrandingConfig(
        header_title=branding.header_title or defaults.header_title,
        header_line1=branding.header_line1 or defaults.header_line1,
        header_line2=branding.header_line2,
        header_line3=branding.header_line3 or defaults.header_line3,
        footer_line1=branding.footer_line1 or defaults.footer_line1,
        footer_line2=branding.footer_line2 or defaults.footer_line2,
        show_logo=branding.show_logo,
        show_brasao=branding.show_brasao,
    )


def save_global_export_branding(data: dict[str, Any]) -> ExportBrandingConfig:
    _ensure_dir()
    current = get_global_export_branding()
    merged = ExportBrandingConfig.from_dict({**current.to_dict(), **data})
    BRANDING_PATH.write_text(
        json.dumps(merged.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return merged


def export_branding_status() -> dict[str, Any]:
    from core.system.company_profile import load_company_brasao, load_company_logo

    branding = get_global_export_branding()
    return {
        **branding.to_dict(),
        "has_logo": load_company_logo() is not None,
        "has_brasao": load_company_brasao() is not None,
    }
