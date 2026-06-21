"""
RAG por projeto — índice FAISS isolado por project_id (multi-formato).
"""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import Any, Optional

from core.project_rag.project_file_extractors import (
    PROJECT_INDEXABLE_SUFFIXES,
    extract_project_file_segments,
    is_indexable_project_file,
)
from memory.chunker import split_text
from memory.embeddings import NomicEmbedder
from memory.faiss_store import FaissVectorStore
from memory.models import DocumentChunk

logger = logging.getLogger(__name__)

PROJECT_INDEX_DIRNAME = "faiss_index"
PROJECT_CONTEXT_LIMIT = 6000
PROJECT_TOP_K = 6

_PROJECTS_ROOT = Path(__file__).resolve().parents[2] / "data" / "projects"


def project_index_dir(project_id: str) -> Path:
    return _PROJECTS_ROOT / project_id / PROJECT_INDEX_DIRNAME


def get_project_store(project_id: str) -> FaissVectorStore:
    return FaissVectorStore(index_dir=project_index_dir(project_id))


def index_project_file(
    project_id: str,
    file_path: str | Path,
    filename: Optional[str] = None,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Indexa arquivo do projeto (PDF, Office, CAD, IFC, texto...) no FAISS dedicado."""
    path = Path(file_path).resolve()
    name = filename or path.name

    if not is_indexable_project_file(path):
        return {
            "status": "skipped",
            "reason": "unsupported_format",
            "filename": name,
            "format": path.suffix.lower(),
            "supported": sorted(PROJECT_INDEXABLE_SUFFIXES),
            "chunks": 0,
        }

    store = get_project_store(project_id)
    file_key = str(path)

    if store.is_indexed(file_key) and not force:
        return {"status": "skipped", "reason": "already_indexed", "filename": name, "chunks": 0}

    if force and store.is_indexed(file_key):
        store.remove_by_path(file_key)

    try:
        segments, fmt = extract_project_file_segments(path)
    except ImportError as exc:
        logger.warning("project_rag missing dep %s: %s", name, exc)
        return {
            "status": "error",
            "filename": name,
            "format": path.suffix.lower(),
            "error": str(exc),
            "chunks": 0,
        }
    except Exception as exc:
        logger.warning("project_rag index failed %s: %s", name, exc)
        return {
            "status": "error",
            "filename": name,
            "format": path.suffix.lower(),
            "error": str(exc),
            "chunks": 0,
        }

    try:
        from core.knowledge.resolver import file_content_hash

        content_hash = file_content_hash(path)
    except Exception:
        content_hash = ""

    embedder = NomicEmbedder()
    metadata_base = {
        "path": file_key,
        "filename": name,
        "project_id": project_id,
        "content_hash": content_hash,
        "content_type": "project",
        "format": fmt,
    }

    chunks: list[DocumentChunk] = []
    embed_errors = 0
    try:
        for segment in segments:
            for chunk_text in split_text(segment.text):
                try:
                    embedding = embedder.embed_document(chunk_text)
                except Exception as exc:
                    embed_errors += 1
                    logger.warning("project_rag embed failed %s (chunk %d): %s", name, embed_errors, exc)
                    if embed_errors >= 3 and not chunks:
                        return {
                            "status": "error",
                            "filename": name,
                            "format": fmt,
                            "error": f"embedding_unavailable: {exc}",
                            "chunks": 0,
                            "hint": (
                                "Ollama não respondeu ao embedding após várias tentativas. "
                                "Aguarde análises visuais/LLM terminarem e use «Reindexar RAG»."
                            ),
                        }
                    continue
                chunks.append(
                    DocumentChunk(
                        text=chunk_text,
                        embedding=embedding,
                        source=name,
                        doc_type="project",
                        discipline="PROJETO",
                        page=segment.section_num or None,
                        metadata={
                            **metadata_base,
                            "section": segment.section,
                        },
                    )
                )
    except Exception as exc:
        logger.warning("project_rag chunk build failed %s: %s", name, exc)
        return {
            "status": "error",
            "filename": name,
            "format": fmt,
            "error": str(exc),
            "chunks": 0,
        }

    if not chunks:
        return {"status": "error", "filename": name, "format": fmt, "error": "no_chunks", "chunks": 0}

    try:
        store.add_many(chunks)
        store.save()
    except Exception as exc:
        logger.warning("project_rag store failed %s: %s", name, exc)
        return {
            "status": "error",
            "filename": name,
            "format": fmt,
            "error": str(exc),
            "chunks": 0,
        }

    logger.info(
        "project_rag indexed project=%s file=%s format=%s chunks=%d embed_errors=%d",
        project_id,
        name,
        fmt,
        len(chunks),
        embed_errors,
    )
    result: dict[str, Any] = {
        "status": "indexed",
        "filename": name,
        "format": fmt,
        "chunks": len(chunks),
    }
    if embed_errors:
        result["partial"] = True
        result["embed_errors"] = embed_errors
        result["hint"] = f"{embed_errors} trecho(s) ignorado(s) por falha temporária de embedding."
    return result


def remove_project_file_index(project_id: str, file_path: str | Path) -> int:
    store = get_project_store(project_id)
    removed = store.remove_by_path(str(Path(file_path).resolve()))
    if removed:
        store.save()
    return removed


def build_project_context(query: str, project_id: str, top_k: int = PROJECT_TOP_K) -> str:
    """Recupera trechos dos documentos do projeto para a query."""
    store = get_project_store(project_id)
    if store.count() == 0:
        return ""

    embedder = NomicEmbedder()
    query_vec = embedder.embed_query(query)
    hits = store.search(
        query_vec,
        top_k=top_k,
        doc_type="project",
    )

    if not hits:
        return ""

    blocks: list[str] = []
    seen: set[str] = set()
    total = 0

    header = "CONTEXTO DO PROJETO (documentos enviados pelo usuário):\n"
    blocks.append(header)
    total += len(header)

    for chunk, score in hits:
        sig = hashlib.sha256(chunk.text[:200].encode()).hexdigest()[:12]
        if sig in seen:
            continue
        seen.add(sig)

        fname = chunk.metadata.get("filename") or chunk.source or "documento"
        fmt = chunk.metadata.get("format") or "doc"
        section = chunk.metadata.get("section") or f"p.{chunk.page or '?'}"
        block_header = f"[PROJETO | {fname} | {fmt} | {section} | score={score:.3f}]"
        block = f"{block_header}\n{chunk.text}"

        if total + len(block) > PROJECT_CONTEXT_LIMIT:
            remaining = PROJECT_CONTEXT_LIMIT - total
            if remaining > 200:
                blocks.append(block[:remaining] + "…")
            break
        blocks.append(block)
        total += len(block)

    return "\n\n---\n\n".join(blocks)


def augment_route_with_project_context(route_result: dict[str, Any]) -> dict[str, Any]:
    """Anexa contexto RAG do projeto ao route_result."""
    project_id = route_result.get("_project_id")
    if not project_id or route_result.get("_use_rag") is False:
        return route_result

    query = route_result.get("input", "")
    if not query:
        return route_result

    project_ctx = build_project_context(query, str(project_id))
    if not project_ctx:
        return route_result

    enriched = dict(route_result)
    existing = enriched.get("context") or ""
    if existing:
        enriched["context"] = f"{project_ctx}\n\n---\n\n{existing}"
    else:
        enriched["context"] = project_ctx

    enriched.setdefault("project_rag", {})
    enriched["project_rag"].update(
        {
            "active": True,
            "project_id": str(project_id),
            "context_length": len(project_ctx),
            "indexed_chunks": get_project_store(str(project_id)).count(),
        }
    )
    return enriched


def reindex_project(project_id: str, files: list[dict[str, Any]], *, force: bool = True) -> dict:
    """Reindexa todos os arquivos suportados do projeto."""
    summary = {"indexed": 0, "skipped": 0, "errors": [], "total_chunks": 0}
    for row in files:
        path = row.get("storage_path")
        name = row.get("filename", "")
        if not path:
            continue
        result = index_project_file(project_id, path, name, force=force)
        if result.get("status") == "indexed":
            summary["indexed"] += 1
            summary["total_chunks"] += result.get("chunks", 0)
        elif result.get("status") == "skipped":
            summary["skipped"] += 1
        else:
            summary["errors"].append(result)
    return summary


def supported_formats() -> list[dict[str, str]]:
    labels = {
        ".pdf": "PDF",
        ".docx": "Word (DOCX)",
        ".xlsx": "Excel (XLSX)",
        ".xls": "Excel legado (XLS)",
        ".csv": "CSV",
        ".txt": "Texto",
        ".md": "Markdown",
        ".json": "JSON",
        ".dxf": "AutoCAD DXF",
        ".dwg": "AutoCAD DWG (strings parciais)",
        ".ifc": "BIM IFC",
        ".rtf": "RTF",
        ".png": "Imagem PNG",
        ".jpg": "Imagem JPG",
        ".jpeg": "Imagem JPEG",
        ".webp": "Imagem WebP",
        ".heic": "Imagem HEIC",
        ".heif": "Imagem HEIF",
        ".zip": "ZIP",
    }
    return [
        {"ext": ext, "label": labels.get(ext, ext.upper())}
        for ext in sorted(PROJECT_INDEXABLE_SUFFIXES)
    ]
