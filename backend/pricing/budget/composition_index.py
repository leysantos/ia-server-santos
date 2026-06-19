"""Índice FAISS das composições da base de preços ativa (SINAPI/PPD importada)."""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from pathlib import Path
from typing import Any, Optional

from config.settings import FAISS_INDEX_DIR
from memory.embeddings import NomicEmbedder
from memory.faiss_store import FaissVectorStore
from memory.models import DocumentChunk
from pricing.models.price_item import PriceItem

logger = logging.getLogger(__name__)

INDEX_DIR = FAISS_INDEX_DIR / "budget" / "compositions"
META_FILE = "source_meta.json"
BATCH_SIZE = 64

_index_lock = threading.Lock()
_index_instance: Optional["CompositionSearchIndex"] = None


class CompositionSearchIndex:
    """Busca semântica (FAISS + nomic-embed) sobre composições carregadas."""

    def __init__(self, index_dir: Path | None = None) -> None:
        self.index_dir = index_dir or INDEX_DIR
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.store = FaissVectorStore(index_dir=self.index_dir)
        self.embedder = NomicEmbedder()
        self._meta_path = self.index_dir / META_FILE
        self._meta: dict[str, Any] = self._load_meta()

    def _load_meta(self) -> dict[str, Any]:
        if not self._meta_path.is_file():
            return {}
        return json.loads(self._meta_path.read_text(encoding="utf-8"))

    def _save_meta(self, payload: dict[str, Any]) -> None:
        self._meta = payload
        self._meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _fingerprint(rows: list[dict[str, Any]]) -> str:
        sample = f"{len(rows)}|{rows[0].get('code') if rows else ''}|{rows[-1].get('code') if rows else ''}"
        return hashlib.sha256(sample.encode()).hexdigest()[:16]

    @staticmethod
    def _doc_text(row: dict[str, Any]) -> str:
        code = row.get("code", "")
        desc = row.get("description", "")
        unit = row.get("unit", "un")
        return f"{code} {desc} unidade {unit}"

    def is_current(self, rows: list[dict[str, Any]], label: str = "") -> bool:
        if not rows or self.store.count() == 0:
            return False
        fp = self._fingerprint(rows)
        indexed = self.store.count()
        expected = len(rows)
        return (
            self._meta.get("fingerprint") == fp
            and self._meta.get("label") == label
            and indexed >= max(1, int(expected * 0.95))
            and self._meta.get("count", 0) >= max(1, int(expected * 0.95))
        )

    def schedule_rebuild(
        self,
        rows: list[dict[str, Any]],
        *,
        label: str = "sinapi",
        source: str = "sinapi",
    ) -> None:
        """Dispara rebuild FAISS em thread (bases grandes)."""
        import threading

        def _run() -> None:
            try:
                self.rebuild(rows, label=label, source=source)
            except Exception as exc:
                logger.warning("FAISS rebuild background falhou: %s", exc)

        threading.Thread(target=_run, daemon=True, name="faiss-composition-rebuild").start()

    def rebuild(self, rows: list[dict[str, Any]], *, label: str = "sinapi", source: str = "sinapi") -> dict[str, Any]:
        """Reindexa composições (embeddings via Ollama)."""
        with _index_lock:
            self.store.clear()
            if not rows:
                self._save_meta({"count": 0, "fingerprint": "", "label": label})
                self.store.save()
                return {"indexed": 0, "errors": []}

            chunks: list[DocumentChunk] = []
            errors: list[str] = []
            texts = [self._doc_text(r) for r in rows]

            for start in range(0, len(texts), BATCH_SIZE):
                batch_texts = texts[start : start + BATCH_SIZE]
                batch_rows = rows[start : start + BATCH_SIZE]
                try:
                    embeddings = self.embedder.embed_batch(batch_texts, task="document")
                except Exception as exc:
                    logger.warning("FAISS embed batch falhou (%s), continuando próximo lote", exc)
                    errors.append(str(exc))
                    continue

                for row, text, emb in zip(batch_rows, batch_texts, embeddings):
                    chunks.append(
                        DocumentChunk(
                            text=text,
                            embedding=emb,
                            source=source,
                            doc_type="composition",
                            discipline="ORCAMENTO",
                            metadata={
                                "code": str(row.get("code", "")),
                                "description": str(row.get("description", "")),
                                "unit": str(row.get("unit", "un")),
                                "price": float(row.get("price") or 0),
                                "content_type": "sinapi",
                            },
                        )
                    )

            if chunks:
                self.store.add_many(chunks)
                self.store.save()

            fp = self._fingerprint(rows)
            self._save_meta(
                {
                    "count": len(chunks),
                    "fingerprint": fp,
                    "label": label,
                    "source": source,
                    "total_rows": len(rows),
                }
            )
            logger.info("CompositionSearchIndex: %s composições indexadas (%s)", len(chunks), label)
            return {"indexed": len(chunks), "total_rows": len(rows), "errors": errors}

    def search(
        self,
        query: str,
        *,
        unit: str | None = None,
        top_k: int = 10,
    ) -> list[tuple[PriceItem, float]]:
        if self.store.count() == 0 or not query.strip():
            return []

        try:
            query_emb = self.embedder.embed_query(query)
        except Exception as exc:
            logger.warning("CompositionSearchIndex embed query falhou: %s", exc)
            return []

        hits = self.store.search(query_embedding=query_emb, top_k=top_k * 3, min_score=0.25)
        results: list[tuple[PriceItem, float]] = []
        seen: set[str] = set()

        for chunk, score in hits:
            meta = chunk.metadata or {}
            code = str(meta.get("code", ""))
            if not code or code in seen:
                continue
            item_unit = str(meta.get("unit", "un"))
            if unit and not self._unit_ok(unit, item_unit):
                score *= 0.5
            seen.add(code)
            item = PriceItem(
                code=code,
                description=str(meta.get("description", chunk.text)),
                unit=item_unit,
                price=float(meta.get("price") or 0),
                source=str(chunk.source or "sinapi"),
                metadata={"faiss_score": score},
            )
            results.append((item, float(score)))
            if len(results) >= top_k:
                break

        return results

    @staticmethod
    def _unit_ok(expected: str, actual: str) -> bool:
        e = expected.lower().replace("²", "2").replace("³", "3").strip()
        a = actual.lower().replace("²", "2").replace("³", "3").strip()
        return e == a or (e in ("m2", "m²") and a in ("m2", "m²"))

    def status(self) -> dict[str, Any]:
        return {
            "indexed": self.store.count(),
            **self._meta,
        }


def get_composition_index() -> CompositionSearchIndex:
    global _index_instance
    if _index_instance is None:
        _index_instance = CompositionSearchIndex()
    return _index_instance


def rebuild_composition_index_from_provider(label: str = "sinapi") -> dict[str, Any]:
    from pricing.registry.provider_registry import ProviderRegistry

    provider = ProviderRegistry.get("sinapi")
    if not provider or not provider.is_loaded:
        return {"indexed": 0, "skipped": True}
    rows = getattr(provider, "_data", []) or []
    index = get_composition_index()
    if index.is_current(rows, label):
        return {"indexed": index.store.count(), "skipped": True, "cached": True}
    if len(rows) > 800:
        index.schedule_rebuild(rows, label=label, source=provider.name)
        return {
            "indexed": index.store.count(),
            "scheduled": True,
            "total_rows": len(rows),
            "message": "Indexação FAISS em background — matching lexical ativo",
        }
    return index.rebuild(rows, label=label, source=provider.name)
