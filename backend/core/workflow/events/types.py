"""Tipos de eventos do Workflow Projetos (EDA)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class WorkflowEventType(StrEnum):
    PROJECT_CREATED = "PROJECT_CREATED"
    PROJECT_UPDATED = "PROJECT_UPDATED"
    FILE_UPLOADED = "FILE_UPLOADED"
    DWG_ANALYZED = "DWG_ANALYZED"
    DXF_ANALYZED = "DXF_ANALYZED"
    IFC_ANALYZED = "IFC_ANALYZED"
    DRAWING_DETECTED = "DRAWING_DETECTED"
    SHEET_GENERATED = "SHEET_GENERATED"
    REVISION_CREATED = "REVISION_CREATED"
    PDF_PUBLISHED = "PDF_PUBLISHED"
    PACKAGE_EXPORTED = "PACKAGE_EXPORTED"
    SIGNATURE_COMPLETED = "SIGNATURE_COMPLETED"
    DELIVERY_COMPLETED = "DELIVERY_COMPLETED"


DEFAULT_FOLDER_STRUCTURE: list[dict[str, str | None]] = [
    {"nome": "Arquitetura", "path": "Arquitetura", "disciplina": "arquitetura"},
    {"nome": "Estrutural", "path": "Estrutural", "disciplina": "estrutural"},
    {"nome": "Elétrica", "path": "Eletrica", "disciplina": "eletrica"},
    {"nome": "Hidrossanitário", "path": "Hidrossanitario", "disciplina": "hidraulica"},
    {"nome": "PCI", "path": "PCI", "disciplina": "incendio"},
    {"nome": "Memoriais", "path": "Memoriais", "disciplina": "geral"},
    {"nome": "Orçamentos", "path": "Orcamentos", "disciplina": "orcamento"},
    {"nome": "Pranchas", "path": "Pranchas", "disciplina": None},
    {"nome": "PDFs", "path": "PDFs", "disciplina": None},
    {"nome": "Entregas", "path": "Entregas", "disciplina": None},
    {"nome": "Revisões", "path": "Revisoes", "disciplina": None},
    {"nome": "As Built", "path": "As_Built", "disciplina": None},
]

SUPPORTED_SCALES = (
    "1:10",
    "1:20",
    "1:25",
    "1:50",
    "1:75",
    "1:100",
    "1:125",
    "1:200",
    "1:250",
    "1:500",
)

SHEET_FORMATS = ("A4", "A3", "A2", "A1", "A0")


def event_payload(
    event_type: WorkflowEventType | str,
    **kwargs: Any,
) -> dict[str, Any]:
    return {"event_type": str(event_type), **kwargs}
