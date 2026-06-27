"""Serviço de exportação nativa (Excel/PDF) — substitui sync com template SEMINF."""

from __future__ import annotations

from typing import Any

from core.system.company_profile import get_company_profile, load_company_brasao, load_company_logo
from core.system.export_branding_store import (
    export_branding_status,
    get_global_export_branding,
    save_global_export_branding,
)
from pricing.budget.budget_export_branding import ExportBrandingConfig
from pricing.budget.budget_pdf_export import export_budget_pdf
from pricing.budget.budget_session import BudgetSession, SESSION_STORE
from pricing.budget.budget_xlsx_builder import export_budget_document_xlsx, export_budget_workbook_xlsx


def get_session_or_raise(session_id: str) -> BudgetSession:
    session = SESSION_STORE.get(session_id)
    if not session:
        raise KeyError(f"Sessão não encontrada: {session_id}")
    return session


def get_export_branding(_session_id: str | None = None) -> ExportBrandingConfig:
    """Personalização global — aplicada a todos os orçamentos exportados."""
    return get_global_export_branding()


def update_export_branding(_session_id: str | None, data: dict[str, Any]) -> ExportBrandingConfig:
    return save_global_export_branding(data)


def update_global_export_branding(data: dict[str, Any]) -> ExportBrandingConfig:
    return save_global_export_branding(data)


def get_export_branding_status() -> dict[str, Any]:
    return export_branding_status()


def _resolve_logo_bytes(branding: ExportBrandingConfig) -> bytes | None:
    if not branding.show_logo:
        return None
    return load_company_logo()


def _resolve_brasao_bytes(branding: ExportBrandingConfig) -> bytes | None:
    if not branding.show_brasao:
        return None
    return load_company_brasao()


def export_session_xlsx(session_id: str, doc_type: str) -> bytes:
    session = get_session_or_raise(session_id)
    for root in session.roots:
        root.recompute_total()
    branding = get_global_export_branding()
    logo = _resolve_logo_bytes(branding)
    profile = get_company_profile()
    return export_budget_document_xlsx(
        doc_type,
        session.roots,
        session.project,
        branding=branding,
        schedule=session.schedule,
        tech_spec=session.tech_spec,
        logo_bytes=logo,
        company_profile=profile,
    )


def export_session_workbook_xlsx(session_id: str) -> bytes:
    """Workbook legado com 5 abas."""
    session = get_session_or_raise(session_id)
    for root in session.roots:
        root.recompute_total()
    branding = get_global_export_branding()
    logo = _resolve_logo_bytes(branding)
    return export_budget_workbook_xlsx(
        session.roots,
        session.project,
        branding=branding,
        schedule=session.schedule,
        tech_spec=session.tech_spec,
        logo_bytes=logo,
    )


def export_session_pdf(session_id: str, doc_type: str) -> bytes:
    session = get_session_or_raise(session_id)
    for root in session.roots:
        root.recompute_total()
    branding = get_global_export_branding()
    logo = _resolve_logo_bytes(branding)
    brasao = _resolve_brasao_bytes(branding)
    profile = get_company_profile()
    return export_budget_pdf(
        doc_type,
        session.roots,
        session.project,
        branding=branding,
        schedule=session.schedule,
        tech_spec=session.tech_spec,
        logo_bytes=logo,
        brasao_bytes=brasao,
        company_profile=profile,
    )
