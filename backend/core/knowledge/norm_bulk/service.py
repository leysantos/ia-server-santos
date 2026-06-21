"""Ingestão em lote de PDFs NBR/NR com progresso."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Optional

from core.knowledge.ingestion import get_ingester
from core.knowledge.norm_bulk.classifier import classify_norm_pdf
from core.knowledge.norm_bulk.bulk_report import attach_bulk_audit_report

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[dict[str, Any]], None]


def bulk_ingest_norm_pdfs(
    sources: list[Path],
    *,
    force: bool = False,
    use_ai_fallback: bool = False,
    mark_edition_outdated: bool = False,
    on_progress: Optional[ProgressCallback] = None,
) -> dict[str, Any]:
    """
    Classifica e ingere PDFs de normas um a um, emitindo progresso.

    Não indexa FAISS — o caller dispara indexação uma vez ao final.
    """
    ingester = get_ingester()
    pdf_sources = [p.resolve() for p in sources if p.suffix.lower() == ".pdf"]
    total = len(pdf_sources)
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    ingested = 0
    skipped = 0
    classified: list[dict[str, Any]] = []

    def emit(phase: str, current: int, message: str, **extra: Any) -> None:
        if not on_progress:
            return
        pct = round((current / total) * 88) if total else 0
        on_progress(
            {
                "phase": phase,
                "current": current,
                "total": total,
                "percent": min(88, pct),
                "message": message,
                **extra,
            }
        )

    emit("classify", 0, f"Preparando {total} PDF(s) de normas…")

    for index, source in enumerate(pdf_sources, start=1):
        try:
            classification = classify_norm_pdf(
                source,
                use_ai_fallback=use_ai_fallback,
                mark_edition_outdated=mark_edition_outdated,
            )
            classified.append(
                {
                    "filename": source.name,
                    "norm_kind": classification.metadata.get("norm_kind"),
                    "norm_code": classification.metadata.get("norm_code"),
                    "discipline": classification.mapped_discipline,
                    "confidence": classification.confidence,
                    "source": classification.source,
                }
            )
            emit(
                "ingest",
                index,
                f"Importando {source.name} → {classification.mapped_discipline}",
                name=source.name,
            )

            record = ingester.ingest(
                source,
                discipline_hint=classification.mapped_discipline,
                content_type_hint="nbrs",
                force=force,
                name=(
                    classification.metadata.get("norm_display_name")
                    or classification.metadata.get("norm_label")
                    or source.stem
                ),
                description=(
                    classification.metadata.get("norm_title")
                    or classification.metadata.get("norm_display_name")
                    or classification.metadata.get("edition_note")
                ),
            )
            # Reaplica metadados de norma no sidecar (norm_kind, edition_outdated)
            if record.get("status") == "copied":
                target = Path(record.get("target", ""))
                if target.is_file():
                    from core.knowledge.metadata import read_metadata, write_metadata

                    sidecar = read_metadata(target) or {}
                    sidecar.update(
                        {k: v for k, v in classification.metadata.items() if v is not None}
                    )
                    if classification.metadata.get("norm_kind") == "NBR":
                        sidecar["nbr"] = classification.metadata.get("nbr")
                        sidecar["nbr_code"] = classification.metadata.get("nbr")
                    elif classification.metadata.get("norm_kind") == "NR":
                        sidecar["nr"] = classification.metadata.get("nr")
                    write_metadata(target, sidecar)

            record["classification"] = classification.to_dict()
            results.append(record)
            status = record.get("status", "")
            if status == "copied":
                ingested += 1
            elif status.startswith("skipped"):
                skipped += 1
        except Exception as exc:
            logger.exception("Falha ao importar norma %s", source.name)
            errors.append({"source": str(source), "filename": source.name, "error": str(exc)})

    summary = {
        "total_files": total,
        "ingested": ingested,
        "skipped": skipped,
        "errors": errors,
        "results": results,
        "classified_preview": classified[:50],
        "classified_count": len(classified),
    }
    emit("ingest", total, f"Concluído — {ingested} importado(s), {skipped} ignorado(s)")
    return attach_bulk_audit_report(summary)
