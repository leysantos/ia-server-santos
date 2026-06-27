"""Configuração de marca (logo, cabeçalho, rodapé) para exportação Excel/PDF."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.workflow.storage.client import get_workflow_storage
from pricing.models.budget_metadata import BudgetProjectMetadata

LOGO_FILENAME = "export_logo"
EXPORT_DOC_TYPES = (
    "orc_sintetico",
    "orc_analitico",
    "mcq",
    "cronograma",
    "esp_tecnica",
    "curva_abc",
    "curva_s",
    "histograma",
)


def logo_storage_key(session_id: str) -> str:
    return f"budgets/{session_id}/{LOGO_FILENAME}"


@dataclass
class ExportBrandingConfig:
    """Personalização visual dos documentos exportados."""

    header_title: str = "PLANILHA ORÇAMENTÁRIA"
    header_line1: str = ""
    header_line2: str = ""
    header_line3: str = ""
    footer_line1: str = ""
    footer_line2: str = ""
    show_logo: bool = True
    show_brasao: bool = True
    logo_storage_key: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "header_title": self.header_title,
            "header_line1": self.header_line1,
            "header_line2": self.header_line2,
            "header_line3": self.header_line3,
            "footer_line1": self.footer_line1,
            "footer_line2": self.footer_line2,
            "show_logo": self.show_logo,
            "show_brasao": self.show_brasao,
            "logo_storage_key": self.logo_storage_key,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ExportBrandingConfig:
        if not data:
            return cls()
        return cls(
            header_title=str(data.get("header_title") or "PLANILHA ORÇAMENTÁRIA"),
            header_line1=str(data.get("header_line1") or ""),
            header_line2=str(data.get("header_line2") or ""),
            header_line3=str(data.get("header_line3") or ""),
            footer_line1=str(data.get("footer_line1") or ""),
            footer_line2=str(data.get("footer_line2") or ""),
            show_logo=bool(data.get("show_logo", True)),
            show_brasao=bool(data.get("show_brasao", True)),
            logo_storage_key=data.get("logo_storage_key"),
        )

    @classmethod
    def from_project(cls, meta: BudgetProjectMetadata, session_id: str | None = None) -> ExportBrandingConfig:
        """Preenche defaults a partir dos metadados do orçamento."""
        key = logo_storage_key(session_id) if session_id else None
        return cls(
            header_line1=meta.empresa or meta.orgao or "",
            header_line2=meta.projeto or meta.objeto or "",
            header_line3=" · ".join(
                p for p in (meta.local, meta.orcamento) if p
            ),
            footer_line1=meta.responsavel_tecnico or "",
            footer_line2=" · ".join(
                p for p in (meta.processo, meta.data_ref) if p
            ),
            logo_storage_key=key,
        )


def get_branding_from_intent(intent: dict[str, Any] | None, session_id: str) -> ExportBrandingConfig:
    raw = (intent or {}).get("export_branding")
    branding = ExportBrandingConfig.from_dict(raw if isinstance(raw, dict) else None)
    if not branding.logo_storage_key:
        branding.logo_storage_key = logo_storage_key(session_id)
    return branding


def merge_branding_with_project(
    branding: ExportBrandingConfig,
    meta: BudgetProjectMetadata,
) -> ExportBrandingConfig:
    """Preenche linhas vazias com dados do projeto."""
    defaults = ExportBrandingConfig.from_project(meta)
    return ExportBrandingConfig(
        header_title=branding.header_title or defaults.header_title,
        header_line1=branding.header_line1 or defaults.header_line1,
        header_line2=branding.header_line2 or defaults.header_line2,
        header_line3=branding.header_line3 or defaults.header_line3,
        footer_line1=branding.footer_line1 or defaults.footer_line1,
        footer_line2=branding.footer_line2 or defaults.footer_line2,
        show_logo=branding.show_logo,
        show_brasao=branding.show_brasao,
        logo_storage_key=branding.logo_storage_key,
    )


def load_logo_bytes(storage_key: str | None) -> bytes | None:
    if not storage_key:
        return None
    storage = get_workflow_storage()
    if not storage.exists(storage_key):
        return None
    return storage.get_bytes(storage_key)


def save_logo_bytes(session_id: str, content: bytes, content_type: str = "image/png") -> str:
    storage = get_workflow_storage()
    key = logo_storage_key(session_id)
    storage.put_bytes(key, content, content_type=content_type)
    return key
