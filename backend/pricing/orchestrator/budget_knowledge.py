"""Contexto RAG — modelos de orçamento e referências para geração."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def fetch_budget_generation_context(user_text: str, top_k: int = 3) -> tuple[str, list[dict[str, Any]]]:
    """
    Busca modelos de orçamento indexados (FAISS budget_models) relevantes ao prompt.
    Retorna (texto para prompt, hits metadata).
    """
    refs: list[dict[str, Any]] = []
    try:
        from core.knowledge.multi_index_store import get_multi_index_store

        store = get_multi_index_store()
        if "budget_models" not in store._stores:
            return "", refs
        if store.get_store("budget_models").count() == 0:
            return _fallback_catalog_context(user_text), refs

        hits = store.search_many(
            ["budget_models"],
            user_text,
            top_k=top_k,
        )
        if not hits:
            return _fallback_catalog_context(user_text), refs

        blocks: list[str] = [
            "=== MODELOS DE ORÇAMENTO DE REFERÊNCIA (consulte antes de estruturar) ==="
        ]
        for chunk, score in hits:
            meta = chunk.metadata or {}
            title = meta.get("name") or meta.get("filename") or "Modelo"
            blocks.append(f"\n--- {title} (relevância {score:.2f}) ---")
            blocks.append(chunk.text[:4000])
            refs.append(
                {
                    "name": title,
                    "score": round(score, 4),
                    "document_id": meta.get("document_id"),
                    "path": meta.get("path"),
                }
            )
        blocks.append("\n=== FIM DOS MODELOS — use a estrutura WBS/ETAPAs acima como guia ===")
        return "\n".join(blocks), refs
    except Exception as exc:
        logger.warning("fetch_budget_generation_context falhou: %s", exc)
        return _fallback_catalog_context(user_text), refs


def _fallback_catalog_context(user_text: str) -> str:
    """Fallback: lê sidecars .budget_model.json no catálogo."""
    try:
        from core.knowledge.catalog import read_catalog
        from core.knowledge.metadata import read_metadata
        from pricing.budget.budget_model_extractor import budget_model_sidecar_path

        lower = user_text.lower()
        snippets: list[str] = []
        for row in read_catalog()[-50:]:
            if row.get("content_type") != "modelos_orcamento":
                continue
            path = Path(row.get("path", ""))
            if not path.is_file():
                continue
            sidecar = budget_model_sidecar_path(path)
            if sidecar.is_file():
                import json

                data = json.loads(sidecar.read_text(encoding="utf-8"))
                summary = data.get("summary_text", "")
            else:
                meta = read_metadata(path) or {}
                summary = meta.get("budget_model_summary", "")
            if not summary:
                continue
            name = row.get("name") or path.stem
            if any(k in lower for k in ("passarela", "ponte")) and "passarela" not in name.lower() and "ponte" not in summary.lower():
                continue
            snippets.append(f"--- {name} ---\n{summary[:3000]}")
            if len(snippets) >= 2:
                break
        if snippets:
            return "=== MODELOS DE ORÇAMENTO (catálogo) ===\n" + "\n\n".join(snippets)
    except Exception:
        pass
    return ""
