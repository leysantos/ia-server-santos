"""Validação BDI aplicado vs perfil edital / limites TCU (B26)."""

from __future__ import annotations

from typing import Any

from pricing.budget.bdi_edital_profiles import (
    BdiTcuComponents,
    get_bdi_edital_profile,
    seminf_profile_for_obra,
)
from pricing.models.budget_metadata import BdiConfig

_COMPONENT_LABELS: dict[str, str] = {
    "administracao_central": "AC — Administração central",
    "garantias_seguros": "G — Garantias e seguros",
    "riscos": "R — Riscos",
    "despesas_financeiras": "DF — Despesas financeiras",
    "lucro": "L — Lucro",
    "tributos": "T — Tributos",
}


def _issue(
    code: str,
    message: str,
    *,
    severity: str = "warning",
    field: str | None = None,
) -> dict[str, Any]:
    return {"code": code, "message": message, "severity": severity, "field": field}


def _compare_components(
    applied: BdiTcuComponents,
    reference: BdiTcuComponents,
    *,
    mode: str,
    tolerance: float = 0.0005,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for key in _COMPONENT_LABELS:
        actual = float(getattr(applied, key))
        expected = float(getattr(reference, key))
        if abs(actual - expected) > tolerance:
            label = _COMPONENT_LABELS[key]
            issues.append(
                _issue(
                    f"bdi_component_{key}_{mode}",
                    f"{label} ({mode}): aplicado {(actual * 100):.2f}% ≠ edital {(expected * 100):.2f}%",
                    severity="warning",
                    field=key,
                )
            )
    return issues


def _has_documented_components(comp: BdiTcuComponents | None) -> bool:
    if comp is None:
        return False
    return any(float(v) > 0 for v in comp.to_dict().values())


def validate_bdi_config(bdi: BdiConfig) -> dict[str, Any]:
    """Compara taxas e componentes da sessão com o perfil edital de referência."""
    profile_id = (bdi.profile_id or "seminf_table").strip()
    profile = get_bdi_edital_profile(profile_id)
    if profile_id == "seminf_table":
        profile = seminf_profile_for_obra(bdi.obra_type)

    issues: list[dict[str, Any]] = []
    if not profile:
        issues.append(_issue("bdi_profile_missing", f"Perfil BDI desconhecido: {profile_id}", severity="error"))
        return _pack_result(profile_id, bdi, issues)

    ref_comd, ref_semd = profile.rates()
    applied_comd = float(bdi.rate_com_desoneracao or 0)
    applied_semd = float(bdi.rate_sem_desoneracao or 0)

    if profile.max_rate_comd is not None and applied_comd > profile.max_rate_comd + 1e-6:
        issues.append(
            _issue(
                "bdi_rate_comd_exceeds_max",
                f"BDI ComD {(applied_comd * 100):.2f}% excede teto edital {(profile.max_rate_comd * 100):.2f}%",
                severity="error",
                field="rate_com_desoneracao",
            )
        )
    if profile.max_rate_semd is not None and applied_semd > profile.max_rate_semd + 1e-6:
        issues.append(
            _issue(
                "bdi_rate_semd_exceeds_max",
                f"BDI SemD {(applied_semd * 100):.2f}% excede teto edital {(profile.max_rate_semd * 100):.2f}%",
                severity="error",
                field="rate_sem_desoneracao",
            )
        )

    if profile.source == "edital" and profile_id != "custom_edital":
        if abs(applied_comd - ref_comd) > 0.0005:
            issues.append(
                _issue(
                    "bdi_rate_comd_drift",
                    f"BDI ComD aplicado {(applied_comd * 100):.2f}% difere do perfil {(ref_comd * 100):.2f}%",
                    severity="warning",
                    field="rate_com_desoneracao",
                )
            )
        if abs(applied_semd - ref_semd) > 0.0005:
            issues.append(
                _issue(
                    "bdi_rate_semd_drift",
                    f"BDI SemD aplicado {(applied_semd * 100):.2f}% difere do perfil {(ref_semd * 100):.2f}%",
                    severity="warning",
                    field="rate_sem_desoneracao",
                )
            )
        if bdi.components_comd:
            issues.extend(
                _compare_components(bdi.components_comd, profile.components_comd, mode="ComD")
            )
        if bdi.components_semd:
            issues.extend(
                _compare_components(bdi.components_semd, profile.components_semd, mode="SemD")
            )

    if profile_id == "custom_edital" and not (
        _has_documented_components(bdi.components_comd) or _has_documented_components(bdi.components_semd)
    ):
        issues.append(
            _issue(
                "bdi_custom_components_missing",
                "Perfil personalizado sem componentes TCU documentados",
                severity="warning",
            )
        )

    if not bdi.profile_id:
        issues.append(
            _issue(
                "bdi_profile_unset",
                "BDI sem profile_id — documente o perfil edital na sessão",
                severity="warning",
            )
        )

    return _pack_result(profile_id, bdi, issues, profile_label=profile.label, reference_rates=(ref_comd, ref_semd))


def _pack_result(
    profile_id: str,
    bdi: BdiConfig,
    issues: list[dict[str, Any]],
    *,
    profile_label: str | None = None,
    reference_rates: tuple[float, float] | None = None,
) -> dict[str, Any]:
    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]
    if errors:
        status = "error"
    elif warnings:
        status = "warning"
    else:
        status = "ok"

    ref_comd, ref_semd = reference_rates or (None, None)
    return {
        "status": status,
        "profile_id": profile_id,
        "profile_label": profile_label,
        "applied_rates": {
            "com_desoneracao": bdi.rate_com_desoneracao,
            "sem_desoneracao": bdi.rate_sem_desoneracao,
        },
        "reference_rates": {
            "com_desoneracao": ref_comd,
            "sem_desoneracao": ref_semd,
        },
        "issue_count": len(issues),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "issues": issues,
        "valid_for_edital": status == "ok",
    }


def bdi_checklist_status(bdi: BdiConfig) -> str:
    """Status curto para checklist compliance L3."""
    result = validate_bdi_config(bdi)
    if result["status"] == "ok":
        return "ok"
    if result["status"] == "error":
        return "revisar"
    return "atencao"
