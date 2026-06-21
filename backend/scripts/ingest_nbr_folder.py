#!/usr/bin/env python3
"""
Importação em lote de PDFs NBR/NR a partir de uma pasta no disco.

Uso:
  cd backend && python scripts/ingest_nbr_folder.py /caminho/para/nbrs \\
    --use-ai-fallback --mark-outdated --force

Recomendado para acervos grandes (900+ PDFs) — mais rápido que upload pelo browser.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.knowledge.norm_bulk.service import bulk_ingest_norm_pdfs  # noqa: E402
from app.services.knowledge_service import KnowledgeService  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa PDFs NBR/NR de uma pasta")
    parser.add_argument("folder", type=Path, help="Pasta com PDFs (recursivo)")
    parser.add_argument("--force", action="store_true", help="Substituir arquivos existentes")
    parser.add_argument(
        "--use-ai-fallback",
        action="store_true",
        help="Usar IA leve para arquivos ambíguos",
    )
    parser.add_argument(
        "--mark-outdated",
        action="store_true",
        help="Marcar metadado edition_outdated",
    )
    parser.add_argument(
        "--no-index",
        action="store_true",
        help="Não indexar FAISS ao final",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Salvar CSV de auditoria (padrão: <pasta>/auditoria-importacao-nbr-<timestamp>.csv)",
    )
    parser.add_argument("--limit", type=int, default=0, help="Limitar quantidade (0 = todos)")
    args = parser.parse_args()

    folder = args.folder.resolve()
    if not folder.is_dir():
        logger.error("Pasta não encontrada: %s", folder)
        return 1

    pdfs = sorted(folder.rglob("*.pdf"))
    if args.limit > 0:
        pdfs = pdfs[: args.limit]

    if not pdfs:
        logger.error("Nenhum PDF em %s", folder)
        return 1

    logger.info("Encontrados %d PDF(s) em %s", len(pdfs), folder)

    def on_progress(data: dict) -> None:
        if data.get("phase") == "ingest":
            logger.info(
                "[%d/%d] %s",
                data.get("current", 0),
                data.get("total", 0),
                data.get("message", ""),
            )

    result = bulk_ingest_norm_pdfs(
        pdfs,
        force=args.force,
        use_ai_fallback=args.use_ai_fallback,
        mark_edition_outdated=args.mark_outdated,
        on_progress=on_progress,
    )

    logger.info(
        "Concluído: %d importado(s), %d ignorado(s), %d erro(s)",
        result.get("ingested", 0),
        result.get("skipped", 0),
        len(result.get("errors", [])),
    )

    report_path = args.report
    if report_path is None and result.get("report_csv"):
        from datetime import datetime, timezone

        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        report_path = folder / f"auditoria-importacao-nbr-{ts}.csv"
    if report_path and result.get("report_csv"):
        report_path.write_text(result["report_csv"], encoding="utf-8")
        logger.info("Relatório CSV: %s (%d linha(s))", report_path, len(result.get("audit_rows", [])))

    if not args.no_index and result.get("ingested", 0) > 0:
        logger.info("Indexando base NBR (FAISS)…")
        svc = KnowledgeService()
        idx = svc.run_index(force=args.force, base="nbr", content_types={"nbrs"})
        logger.info("Indexação: %s", idx)

    for err in result.get("errors", [])[:10]:
        logger.warning("Erro: %s — %s", err.get("filename"), err.get("error"))

    return 0 if not result.get("errors") else 2


if __name__ == "__main__":
    raise SystemExit(main())
