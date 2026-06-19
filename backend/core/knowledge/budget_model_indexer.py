"""Indexação FAISS de modelos de orçamento (PPD/WBS) para consulta pela IA."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from memory.embeddings import NomicEmbedder
from memory.models import DocumentChunk
from pricing.budget.budget_model_extractor import (
    budget_model_sidecar_path,
    extract_budget_model_summary,
    write_budget_model_sidecar,
)

logger = logging.getLogger(__name__)


def index_budget_model_document(document_path: Path, meta: dict) -> int:
    """Indexa resumo WBS do modelo no FAISS budget_models."""
    sidecar = budget_model_sidecar_path(document_path)
    if sidecar.is_file():
        model = json.loads(sidecar.read_text(encoding="utf-8"))
    else:
        model = extract_budget_model_summary(document_path)
        write_budget_model_sidecar(document_path, model)
        meta["budget_model_summary"] = model.get("summary_text", "")[:500]
        meta["service_count"] = model.get("service_count", 0)

    text = (model.get("summary_text") or "").strip()
    if not text:
        return 0

    try:
        from core.knowledge.multi_index_store import get_multi_index_store

        store = get_multi_index_store().get_store("budget_models")
        file_key = str(document_path.resolve())

        if store.is_indexed(file_key):
            store.remove_by_path(file_key)

        embedder = NomicEmbedder()
        embedding = embedder.embed_document(text[:8000])
        tags_flat = sorted(
            {
                tag
                for etapa in model.get("etapas") or []
                for svc in etapa.get("services") or []
                for tag in svc.get("tags") or []
            }
        )
        chunk = DocumentChunk(
            text=text[:12000],
            embedding=embedding,
            source="budget_model",
            doc_type="budget_model",
            discipline="ORCAMENTO",
            metadata={
                "path": file_key,
                "filename": document_path.name,
                "name": meta.get("name", document_path.stem),
                "document_id": meta.get("id"),
                "content_type": "modelos_orcamento",
                "obra_type": model.get("obra_type"),
                "service_count": model.get("service_count", 0),
                "publisher": model.get("publisher"),
                "region": model.get("region"),
                "tags_flat": tags_flat,
            },
        )
        store.add(chunk)
        store.save()
        logger.info("Modelo de orçamento indexado: %s", document_path.name)
        return 1
    except Exception as exc:
        logger.warning("Falha ao indexar modelo de orçamento %s: %s", document_path.name, exc)
        return 0
