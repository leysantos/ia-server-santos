"""Serviço de histograma — exportação Excel/PDF alinhada ao modelo Caixa."""

from __future__ import annotations

from typing import Any

from core.system.company_profile import CompanyProfile, get_company_profile
from pricing.budget.budget_export_branding import ExportBrandingConfig
from pricing.budget.histogram.excel_builder import build_histogram_report_workbook_bytes
from pricing.budget.histogram.section_mapper import HistogramReport, build_histogram_report
from pricing.models.budget_item import BudgetItem
from pricing.models.budget_metadata import BudgetProjectMetadata
from pricing.schedule.schedule_models import ProjectSchedule


def _resolve_schedule(schedule: Any | None) -> ProjectSchedule | None:
    if schedule is None:
        return None
    if isinstance(schedule, ProjectSchedule):
        return schedule
    try:
        return ProjectSchedule.from_dict(schedule)
    except Exception:
        return None


def export_histogram_mo_xlsx(
    roots: list[BudgetItem],
    metadata: BudgetProjectMetadata | None = None,
    schedule: Any | None = None,
    *,
    branding: ExportBrandingConfig | None = None,
    company_profile: CompanyProfile | None = None,
    logo_bytes: bytes | None = None,
    report: HistogramReport | None = None,
) -> bytes:
    """Exporta workbook Excel com abas MO + equipamentos (tabela + gráfico empilhado)."""
    meta = metadata or BudgetProjectMetadata()
    brand = branding or ExportBrandingConfig()
    profile = company_profile or get_company_profile()
    sched = _resolve_schedule(schedule)

    hist_report = report or build_histogram_report(roots, meta, sched)
    return build_histogram_report_workbook_bytes(
        hist_report,
        profile=profile,
        brand=brand,
        logo_bytes=logo_bytes,
    )
