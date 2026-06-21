"""Relatório CSV de auditoria — importação em lote NBR/NR."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CLASSIFICATION_SOURCE_LABELS: dict[str, str] = {
    "nbr_filename": "Nome do arquivo (NBR)",
    "nr_filename": "Nome do arquivo (NR)",
    "nbr_pdf_text": "Texto 1ª página (NBR)",
    "nr_pdf_text": "Texto 1ª página (NR)",
    "llm_fallback": "IA leve (fallback)",
    "filename_heuristic": "Heurística do nome",
    "unknown_norm": "Não identificado",
}

STATUS_LABELS: dict[str, str] = {
    "copied": "Importado",
    "skipped_duplicate": "Ignorado — duplicata idêntica",
    "skipped_exists": "Ignorado — nome já existe",
    "error": "Erro",
}


def audit_row_from_ingest(
    filename: str,
    classification: dict[str, Any],
    record: dict[str, Any],
) -> dict[str, Any]:
    meta = classification.get("metadata") or {}
    status = str(record.get("status") or "")
    return {
        "filename": filename,
        "norm_kind": meta.get("norm_kind") or "",
        "norm_code": meta.get("norm_code") or meta.get("nbr") or meta.get("nr") or "",
        "norm_label": meta.get("norm_label") or "",
        "discipline": classification.get("mapped_discipline") or "",
        "discipline_slug": classification.get("discipline_slug") or "",
        "confidence": classification.get("confidence", 0),
        "classification_source": classification.get("source") or "",
        "status": status,
        "status_label": STATUS_LABELS.get(status, status),
        "reason": record.get("reason") or "",
        "document_id": record.get("document_id") or "",
        "target": record.get("target") or "",
        "edition_outdated": "sim" if meta.get("edition_outdated") else "não",
    }


def audit_row_from_error(filename: str, error: str) -> dict[str, Any]:
    return {
        "filename": filename,
        "norm_kind": "",
        "norm_code": "",
        "norm_label": "",
        "discipline": "",
        "discipline_slug": "",
        "confidence": 0,
        "classification_source": "",
        "status": "error",
        "status_label": STATUS_LABELS["error"],
        "reason": error,
        "document_id": "",
        "target": "",
        "edition_outdated": "",
    }


def build_audit_rows_from_bulk_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Monta linhas de auditoria a partir do resultado de bulk_ingest_norm_pdfs."""
    rows: list[dict[str, Any]] = []
    seen_errors: set[str] = set()

    for record in result.get("results", []):
        source_path = Path(str(record.get("source", "")))
        filename = source_path.name or Path(str(record.get("target", ""))).name
        classification = record.get("classification") or {}
        rows.append(audit_row_from_ingest(filename, classification, record))

    for err in result.get("errors", []):
        filename = str(err.get("filename") or Path(str(err.get("source", ""))).name or "")
        if not filename or filename in seen_errors:
            continue
        seen_errors.add(filename)
        if any(r.get("filename") == filename for r in rows):
            continue
        rows.append(audit_row_from_error(filename, str(err.get("error") or "")))

    rows.sort(key=lambda r: (r.get("filename") or "").lower())
    return rows


def build_bulk_audit_csv(
    audit_rows: list[dict[str, Any]],
    *,
    summary: dict[str, Any] | None = None,
) -> str:
    """Gera CSV UTF-8 com BOM para Excel."""
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer, lineterminator="\n")

    summary = summary or {}
    writer.writerow(["Relatório de auditoria — importação em lote NBR/NR"])
    writer.writerow(["Gerado em", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")])
    writer.writerow(["Total PDFs", summary.get("total_files", len(audit_rows))])
    writer.writerow(["Importados", summary.get("ingested", "")])
    writer.writerow(["Ignorados", summary.get("skipped", "")])
    writer.writerow(["Erros", len(summary.get("errors", [])) if summary.get("errors") is not None else ""])
    writer.writerow([])

    writer.writerow(
        [
            "Arquivo",
            "Tipo norma",
            "Código",
            "Rótulo",
            "Disciplina",
            "Slug disciplina",
            "Confiança %",
            "Fonte classificação",
            "Status",
            "Motivo",
            "ID documento",
            "Caminho destino",
            "Acervo histórico",
        ]
    )

    for row in audit_rows:
        conf = row.get("confidence", 0)
        try:
            conf_pct = f"{float(conf) * 100:.0f}"
        except (TypeError, ValueError):
            conf_pct = ""
        src = str(row.get("classification_source") or "")
        writer.writerow(
            [
                row.get("filename", ""),
                row.get("norm_kind", ""),
                row.get("norm_code", ""),
                row.get("norm_label", ""),
                row.get("discipline", ""),
                row.get("discipline_slug", ""),
                conf_pct,
                CLASSIFICATION_SOURCE_LABELS.get(src, src),
                row.get("status_label") or row.get("status", ""),
                row.get("reason", ""),
                row.get("document_id", ""),
                row.get("target", ""),
                row.get("edition_outdated", ""),
            ]
        )

    return buffer.getvalue()


def attach_bulk_audit_report(result: dict[str, Any]) -> dict[str, Any]:
    """Anexa audit_rows, report_csv e report_filename ao resultado do lote."""
    audit_rows = build_audit_rows_from_bulk_result(result)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"auditoria-importacao-nbr-{ts}.csv"
    result["audit_rows"] = audit_rows
    result["report_filename"] = filename
    result["report_csv"] = build_bulk_audit_csv(audit_rows, summary=result)
    return result
