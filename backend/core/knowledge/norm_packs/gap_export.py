"""Exportação CSV do gap analysis."""

from __future__ import annotations

import csv
import io
from typing import Any

from core.knowledge.norm_packs.service import NormPackService


def build_gap_csv(analysis: dict[str, Any], *, pack_label: str = "") -> str:
    """Gera CSV UTF-8 com BOM para Excel."""
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer, lineterminator="\n")

    writer.writerow(["Pacote normativo", analysis.get("label") or pack_label])
    writer.writerow(["Cobertura %", analysis.get("summary", {}).get("coverage_pct", "")])
    writer.writerow([])

    writer.writerow(
        [
            "NBR",
            "Título",
            "Disciplina",
            "Crítica",
            "Status",
            "Chunks indexados",
            "Fonte legal",
            "Arquivo",
            "Ação recomendada",
        ]
    )

    status_action = {
        "indexed": "OK — indexada",
        "not_indexed": "PDF presente — indexar em Pacotes NBR",
        "missing": "Adquirir PDF ABNT — upload em Importações",
    }

    for item in analysis.get("items", []):
        status = item.get("status", "")
        writer.writerow(
            [
                f"NBR {item.get('nbr_code', '')}",
                item.get("title", ""),
                item.get("discipline", ""),
                "sim" if item.get("critical") else "não",
                status,
                item.get("chunk_count", 0),
                item.get("legal_source", ""),
                item.get("filename") or "",
                status_action.get(status, ""),
            ]
        )

    return buffer.getvalue()


def export_pack_gap_csv(pack_id: str) -> tuple[str, str]:
    """Retorna (filename, csv_content)."""
    svc = NormPackService()
    analysis = svc.analyze_pack(pack_id)
    safe_id = pack_id.replace("/", "-")
    filename = f"gap-nbr-{safe_id}.csv"
    content = build_gap_csv(analysis, pack_label=analysis.get("label", pack_id))
    return filename, content


def export_project_gaps_csv(gaps: dict[str, Any]) -> tuple[str, str]:
    """CSV consolidado de pendências do projeto (wizard)."""
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["Relatório de pendências normativas — Wizard de Entrega"])
    writer.writerow(["Resumo", gaps.get("summary_message", "")])
    writer.writerow(["Críticas faltando PDF", gaps.get("critical_missing_count", 0)])
    writer.writerow(["Críticas pendentes index", gaps.get("critical_not_indexed_count", 0)])
    writer.writerow([])

    writer.writerow(["NBR", "Título", "Status", "Crítica", "Pacote", "Disciplina", "Ação"])
    for item in gaps.get("pending_items", []):
        writer.writerow(
            [
                f"NBR {item.get('nbr_code', '')}",
                item.get("title", ""),
                item.get("status", ""),
                "sim" if item.get("critical") else "não",
                item.get("pack_label", ""),
                item.get("discipline", ""),
                item.get("action", ""),
            ]
        )
    return "pendencias-normativas-projeto.csv", buffer.getvalue()
