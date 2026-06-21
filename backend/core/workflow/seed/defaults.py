"""Templates padrão de prancha A4–A0."""

from __future__ import annotations

from sqlalchemy.orm import Session

from core.database.workflow_models import WorkflowTemplate
from core.workflow.nomenclature.standards import SHEET_FORMATS

DEFAULT_SHEET_TEMPLATES: list[dict] = [
    {
        "nome": f"{fmt} Paisagem",
        "formato": fmt,
        "orientacao": "paisagem",
        "disciplina": None,
        "placeholders": {
            "empresa": "{{empresa}}",
            "autor": "{{autor}}",
            "crea": "{{crea}}",
            "escala": "{{escala}}",
            "titulo": "{{titulo}}",
            "codigo": "{{codigo}}",
            "revisao": "{{revisao}}",
            "data": "{{data}}",
        },
        "layout": {"carimbo": "inferior", "area_desenho_pct": 0.82},
    }
    for fmt in SHEET_FORMATS
] + [
    {
        "nome": f"{fmt} Retrato",
        "formato": fmt,
        "orientacao": "retrato",
        "disciplina": None,
        "placeholders": {
            "empresa": "{{empresa}}",
            "autor": "{{autor}}",
            "crea": "{{crea}}",
            "escala": "{{escala}}",
            "titulo": "{{titulo}}",
            "codigo": "{{codigo}}",
            "revisao": "{{revisao}}",
            "data": "{{data}}",
        },
        "layout": {"carimbo": "inferior", "area_desenho_pct": 0.78},
    }
    for fmt in ("A4", "A3")
]


def ensure_default_sheet_templates(db: Session) -> int:
    """Insere templates globais (sem empresa) se ainda não existirem."""
    existing = (
        db.query(WorkflowTemplate)
        .filter(WorkflowTemplate.company_id.is_(None))
        .count()
    )
    if existing >= len(DEFAULT_SHEET_TEMPLATES):
        return 0

    names = {t.nome for t in db.query(WorkflowTemplate).filter(WorkflowTemplate.company_id.is_(None)).all()}
    created = 0
    for spec in DEFAULT_SHEET_TEMPLATES:
        if spec["nome"] in names:
            continue
        db.add(
            WorkflowTemplate(
                company_id=None,
                nome=spec["nome"],
                formato=spec["formato"],
                orientacao=spec["orientacao"],
                disciplina=spec.get("disciplina"),
                placeholders=spec.get("placeholders"),
                layout=spec.get("layout"),
                ativo=True,
            )
        )
        created += 1
    if created:
        db.flush()
    return created
