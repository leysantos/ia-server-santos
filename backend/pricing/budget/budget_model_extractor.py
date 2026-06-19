"""Extrai texto estruturado de planilhas PPD para modelos de orçamento (RAG)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BUDGET_MODEL_SUFFIX = ".budget_model.json"


def budget_model_sidecar_path(document_path: Path) -> Path:
    return document_path.with_name(document_path.name + BUDGET_MODEL_SUFFIX)


def _extract_ppd_legacy(path: Path) -> dict[str, Any]:
    """Fallback legado via parse_ppd_workbook (sem enriquecimento regional)."""
    from pricing.budget.ppd_parser import parse_ppd_workbook

    metadata, roots, info = parse_ppd_workbook(path)
    lines: list[str] = []
    etapas: list[dict[str, Any]] = []
    lines.append(f"MODELO DE ORÇAMENTO PPD: {metadata.projeto or path.stem}")
    lines.append(f"Tipo de obra: {metadata.obra_type or 'RF'}")
    lines.append(f"Objeto: {metadata.objeto or ''}")
    lines.append("ESTRUTURA WBS:")

    for root in roots:
        etapa_name = root.name
        etapa_code = root.code
        lines.append(f"\nETAPA {etapa_code} — {etapa_name}")
        svc_list: list[dict[str, str]] = []
        for child in root.children:
            code = child.source_code or child.code
            svc_line = f"  S {child.code} {child.name}"
            if code:
                svc_line += f" [SINAPI {code}]"
            if child.unit:
                svc_line += f" ({child.unit})"
            lines.append(svc_line)
            svc_list.append(
                {
                    "code": child.code,
                    "name": child.name,
                    "sinapi_code": child.source_code or "",
                    "unit": child.unit or "",
                }
            )
        etapas.append({"code": etapa_code, "name": etapa_name, "services": svc_list})

    return {
        "format": "ppd",
        "obra_type": metadata.obra_type,
        "projeto": metadata.projeto,
        "etapas": etapas,
        "service_count": sum(len(e["services"]) for e in etapas),
        "summary_text": "\n".join(lines),
        "import_info": info,
    }


def extract_budget_model_summary(path: Path) -> dict[str, Any]:
    """Gera resumo WBS de um PPD (.xlsm/.xlsx) para indexação e contexto IA."""
    suffix = path.suffix.lower()

    if suffix in (".xlsm", ".xlsx", ".xls"):
        regional_err: str | None = None
        try:
            from core.knowledge.regional_budget_indexer import (
                extract_regional_budget_model,
                is_amazonas_budget_workbook,
            )

            if is_amazonas_budget_workbook(path):
                regional = extract_regional_budget_model(path)
                if regional.get("service_count", 0) > 0:
                    return regional
                regional_err = regional.get("error")
        except Exception as exc:
            regional_err = str(exc)

        try:
            result = _extract_ppd_legacy(path)
            if regional_err and result.get("service_count", 0) == 0:
                result["regional_parse_warning"] = regional_err
            return result
        except Exception as exc:
            return {
                "format": "ppd",
                "publisher": "SEMINF-AM",
                "region": "Manaus/Amazonas",
                "error": str(exc),
                "summary_text": f"Modelo de orçamento PPD: {path.name} (parse parcial: {exc})",
                "etapas": [],
            }

    if suffix == ".pdf":
        try:
            from memory.pdf_indexer import PDFIndexer

            pages = PDFIndexer.extract_text(path)
            text = "\n".join(t for _, t in pages)[:12000]
            return {
                "format": "pdf",
                "summary_text": f"MODELO DE ORÇAMENTO (PDF):\n{text[:8000]}",
                "etapas": [],
            }
        except Exception as exc:
            return {"format": "pdf", "error": str(exc), "summary_text": "", "etapas": []}

    raw = path.read_text(encoding="utf-8", errors="ignore")[:8000]
    return {
        "format": suffix.lstrip(".") or "txt",
        "summary_text": f"MODELO DE ORÇAMENTO:\n{raw}",
        "etapas": [],
    }


def write_budget_model_sidecar(document_path: Path, model: dict[str, Any]) -> Path:
    sidecar = budget_model_sidecar_path(document_path)
    sidecar.write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")
    return sidecar
