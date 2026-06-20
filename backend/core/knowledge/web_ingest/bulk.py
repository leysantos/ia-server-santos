"""Orquestra download em lote + ingestão no catálogo/FAISS."""

from __future__ import annotations

import logging
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import requests

from core.knowledge.ingestion import ingest_batch_sync
from core.knowledge.web_ingest.downloader import download_file, fetch_page
from core.knowledge.web_ingest.pagination import listing_page_urls, merge_unique_links
from core.knowledge.web_ingest.parser import extract_download_links
from core.knowledge.web_ingest.security import UnsafeURLError, validate_public_http_url

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[dict[str, Any]], None]


def _emit_progress(
    on_progress: ProgressCallback | None,
    *,
    phase: str,
    current: int,
    total: int,
    message: str,
    name: str = "",
) -> None:
    if not on_progress:
        return
    percent = round((current / total) * 100) if total > 0 else 0
    on_progress(
        {
            "phase": phase,
            "current": current,
            "total": total,
            "percent": min(100, max(0, percent)),
            "message": message,
            "name": name or None,
        }
    )


def bulk_ingest_from_page(
    page_url: str,
    *,
    discipline: str | None = None,
    content_type: str | None = None,
    description_prefix: str = "",
    max_files: int = 50,
    force: bool = False,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """
    Acessa uma página, detecta links de download e ingere todos na biblioteca.
    Ideal para portais com tabela de anexos (ex.: anexos PSCIP/CBMAM).
    """
    validate_public_http_url(page_url)
    _emit_progress(
        on_progress,
        phase="parse",
        current=0,
        total=1,
        message="Analisando página e detectando links…",
    )
    html, session = fetch_page(page_url)
    page_urls = listing_page_urls(html, page_url)
    link_batches: list[list[dict[str, str | dict[str, str]]]] = []

    for page_idx, purl in enumerate(page_urls, start=1):
        if page_idx == 1:
            page_html = html
        else:
            _emit_progress(
                on_progress,
                phase="parse",
                current=page_idx - 1,
                total=len(page_urls),
                message=f"Lendo página {page_idx}/{len(page_urls)} da listagem…",
            )
            page_html, session = fetch_page(purl, session=session)
        link_batches.append(extract_download_links(page_html, purl, max_links=max_files))

    links = merge_unique_links(link_batches, max_links=max_files)
    _emit_progress(
        on_progress,
        phase="parse",
        current=len(page_urls),
        total=len(page_urls),
        message=(
            f"{len(links)} link(s) em {len(page_urls)} página(s)"
            if len(page_urls) > 1
            else f"{len(links)} link(s) encontrado(s) na página"
        ),
    )

    if not links:
        return {
            "page_url": page_url,
            "pages_fetched": len(page_urls),
            "discovered": 0,
            "downloaded": 0,
            "ingested": 0,
            "skipped": 0,
            "errors": [{"stage": "parse", "error": "Nenhum link de download indexável encontrado"}],
            "files": [],
        }

    tmp_root = Path(tempfile.mkdtemp(prefix="web_ingest_batch_"))
    downloaded: list[Path] = []
    names: list[str] = []
    descriptions: list[str] = []
    errors: list[dict[str, str]] = []
    file_log: list[dict[str, Any]] = []
    work_total = len(links) * 2
    work_done = 0

    try:
        for idx, item in enumerate(links, start=1):
            display_name = str(item.get("name") or item.get("hint_filename") or "documento")
            _emit_progress(
                on_progress,
                phase="download",
                current=work_done,
                total=work_total,
                message=f"Baixando ({idx}/{len(links)})",
                name=display_name,
            )
            try:
                post_data = item.get("post_data")
                path = download_file(
                    item["url"],
                    dest_dir=tmp_root,
                    hint_filename=item.get("hint_filename"),
                    hint_suffix=item.get("hint_suffix"),
                    session=session if post_data else None,
                    post_data=post_data if isinstance(post_data, dict) else None,
                )
                downloaded.append(path)
                names.append(item["name"])
                descriptions.append(str(item.get("description") or item["name"]))
                file_log.append({"url": item["url"], "name": item["name"], "status": "downloaded"})
            except (UnsafeURLError, ValueError, requests.RequestException) as exc:
                err = str(exc)
                errors.append({"url": item["url"], "error": err, "stage": "download"})
                file_log.append({"url": item["url"], "name": item["name"], "status": "download_error", "error": err})
            except Exception as exc:
                logger.exception("Download falhou %s", item["url"])
                err = str(exc)
                errors.append({"url": item["url"], "error": err, "stage": "download"})
                file_log.append({"url": item["url"], "name": item["name"], "status": "download_error", "error": err})
            finally:
                work_done += 1
                _emit_progress(
                    on_progress,
                    phase="download",
                    current=work_done,
                    total=work_total,
                    message=f"Baixado ({len(downloaded)}/{len(links)})",
                    name=display_name,
                )

        if not downloaded:
            return {
                "page_url": page_url,
                "pages_fetched": len(page_urls),
                "discovered": len(links),
                "downloaded": 0,
                "ingested": 0,
                "skipped": 0,
                "errors": errors,
                "files": file_log,
            }

        # Ingestão individual para preservar nome/descrição por arquivo
        total_ingested = 0
        total_skipped = 0
        ingest_errors: list[dict[str, str]] = []

        for ingest_idx, (path, display_name, doc_desc) in enumerate(
            zip(downloaded, names, descriptions, strict=False),
            start=1,
        ):
            _emit_progress(
                on_progress,
                phase="ingest",
                current=work_done,
                total=work_total,
                message=f"Importando ({ingest_idx}/{len(downloaded)})",
                name=display_name,
            )
            desc = (
                f"{description_prefix}{doc_desc}".strip()
                if description_prefix
                else doc_desc
            )
            batch = ingest_batch_sync(
                [path],
                discipline_hint=discipline,
                content_type_hint=content_type,
                name=display_name,
                description=desc,
                force=force,
                copy=True,
            )
            total_ingested += batch.get("ingested", 0)
            total_skipped += batch.get("skipped", 0)
            ingest_errors.extend(batch.get("errors", []))
            for r in batch.get("results", []):
                file_log.append(
                    {
                        "filename": path.name,
                        "name": display_name,
                        "ingest_status": r.get("status"),
                        "document_id": r.get("document_id"),
                    }
                )
            work_done += 1
            _emit_progress(
                on_progress,
                phase="ingest",
                current=work_done,
                total=work_total,
                message=f"Importado ({total_ingested}/{len(downloaded)})",
                name=display_name,
            )

        errors.extend({"stage": "ingest", **e} if "stage" not in e else e for e in ingest_errors)

        _emit_progress(
            on_progress,
            phase="ingest",
            current=work_total,
            total=work_total,
            message=f"Importação concluída — {total_ingested} documento(s) no catálogo",
        )

        return {
            "page_url": page_url,
            "pages_fetched": len(page_urls),
            "discovered": len(links),
            "downloaded": len(downloaded),
            "ingested": total_ingested,
            "skipped": total_skipped,
            "errors": errors,
            "files": file_log,
        }
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
