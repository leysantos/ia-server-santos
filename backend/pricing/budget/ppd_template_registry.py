from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pricing.budget.ppd_layout import PPD_TEMPLATE_ID

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PLANILHAS = _REPO_ROOT / "planilhas-exemplos"

_TEMPLATE_SEMINF_2026 = _PLANILHAS / "ppd_seminf_abril_2026.xlsm"
_TEMPLATE_V81 = _PLANILHAS / "00_MOD_MC_OR_R00-Nivel-1-2-Abril2026-10-06-2026v8.1.xlsm"
_TEMPLATE_FALLBACK = _PLANILHAS / "19_PPD_MC_OR_R01-Nivel-1-2-Marco2026-14-05-2026.xlsm"

PPD_SEMINF_2026_ID = "PPD_SEMINF_ABRIL_2026"


@dataclass(frozen=True)
class PpdTemplate:
    id: str
    label: str
    path: Path
    version: str
    base_template: Path | None = None


REGISTERED_TEMPLATES: dict[str, PpdTemplate] = {
    PPD_SEMINF_2026_ID: PpdTemplate(
        id=PPD_SEMINF_2026_ID,
        label="SEMINF Abril/2026 (MCQ + OR + Cronograma + Esp. Técnica)",
        path=_TEMPLATE_SEMINF_2026,
        version="2026.04",
        base_template=_TEMPLATE_V81,
    ),
    PPD_TEMPLATE_ID: PpdTemplate(
        id=PPD_TEMPLATE_ID,
        label="SEMINF MC/OR v8.1 (modelo oficial legado)",
        path=_TEMPLATE_V81,
        version="8.1",
    ),
    f"{PPD_TEMPLATE_ID}_FALLBACK": PpdTemplate(
        id=f"{PPD_TEMPLATE_ID}_FALLBACK",
        label="SEMINF MC/OR exemplo preenchido",
        path=_TEMPLATE_FALLBACK,
        version="R01",
    ),
}


def resolve_template(template_id: str | None = None) -> PpdTemplate:
    """Template PPD — preferência ppd_seminf_abril_2026, fallback v8.1 / R01."""
    if template_id:
        preferred = REGISTERED_TEMPLATES.get(template_id)
        if preferred and preferred.path.exists():
            return preferred

    if _TEMPLATE_SEMINF_2026.exists():
        return REGISTERED_TEMPLATES[PPD_SEMINF_2026_ID]

    primary = REGISTERED_TEMPLATES[PPD_TEMPLATE_ID]
    if primary.path.exists():
        return primary

    fallback = REGISTERED_TEMPLATES[f"{PPD_TEMPLATE_ID}_FALLBACK"]
    if fallback.path.exists():
        return fallback

    raise FileNotFoundError(
        f"Nenhum template PPD encontrado em {_PLANILHAS} "
        f"(esperado ppd_seminf_abril_2026, v8.1 ou exemplo R01)"
    )


def list_templates() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for tmpl in REGISTERED_TEMPLATES.values():
        out.append(
            {
                "id": tmpl.id,
                "label": tmpl.label,
                "version": tmpl.version,
                "available": str(tmpl.path.exists()).lower(),
                "path": str(tmpl.path),
                "default": str(
                    tmpl.id == PPD_SEMINF_2026_ID and _TEMPLATE_SEMINF_2026.exists()
                ).lower(),
            }
        )
    return out
