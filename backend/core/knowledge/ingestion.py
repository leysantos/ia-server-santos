"""
Knowledge Activation — ingestão flat.

Pipeline: arquivo → classifier → knowledge/raw/documents/ + .knowledge.json + catalog.jsonl
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from core.knowledge.catalog import append_catalog_entry
from core.knowledge.content_types import (
    default_content_type_for_discipline,
    infer_content_type_from_filename,
    normalize_content_type,
)
from core.knowledge.disciplines import slug_for_discipline
from core.knowledge.domain_detector import detect_domain
from core.knowledge.legacy_guard import assert_ingest_target, allowed_ingest_layer
from core.knowledge.metadata import build_metadata_record, write_metadata
from core.knowledge.resolver import file_content_hash, get_documents_dir
from memory.nbr_catalog import infer_discipline, parse_nbr_code

logger = logging.getLogger(__name__)

_INGESTABLE_SUFFIXES = {".pdf", ".csv", ".xlsx", ".xls", ".json", ".md", ".txt", ".docx"}
INGESTABLE_SUFFIXES = _INGESTABLE_SUFFIXES


@dataclass
class ClassificationResult:
    discipline_slug: str
    content_type: str
    confidence: float
    source: str
    mapped_discipline: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "discipline_slug": self.discipline_slug,
            "discipline": [self.discipline_slug],
            "content_type": self.content_type,
            "confidence": self.confidence,
            "source": self.source,
            "mapped_discipline": self.mapped_discipline,
            **self.metadata,
        }


class DisciplineIngester:
    """Classifica e ingere em knowledge/raw/documents/."""

    def _resolve_content_type(
        self,
        path: Path,
        slug: str,
        hint: str | None = None,
    ) -> str:
        if hint:
            return normalize_content_type(hint)
        inferred = infer_content_type_from_filename(path.name)
        if inferred:
            return inferred
        return default_content_type_for_discipline(slug)

    def classify(
        self,
        path: Path,
        discipline_hint: Optional[str] = None,
        content_type_hint: Optional[str] = None,
    ) -> ClassificationResult:
        if discipline_hint:
            slug = slug_for_discipline(discipline_hint)
            ct = self._resolve_content_type(path, slug, content_type_hint)
            return ClassificationResult(
                discipline_slug=slug,
                content_type=ct,
                confidence=1.0,
                source="hint",
                mapped_discipline=discipline_hint.upper(),
                metadata={"filename": path.name},
            )

        name_lower = path.name.lower()
        stem_lower = path.stem.lower()

        nbr = parse_nbr_code(path.name)
        if nbr:
            disc = infer_discipline(nbr) or "GERAL"
            slug = slug_for_discipline(disc)
            return ClassificationResult(
                discipline_slug=slug,
                content_type="nbrs",
                confidence=0.92,
                source="nbr_catalog",
                mapped_discipline=disc,
                metadata={"nbr": nbr, "filename": path.name},
            )

        if any(k in name_lower for k in ("sinapi", "tcpo", "sicro", "orcamento")):
            ct = "sinapi" if "sinapi" in name_lower or "sicro" in name_lower else "tcpo"
            return ClassificationResult(
                discipline_slug="orcamento",
                content_type=ct,
                confidence=0.88,
                source="filename_heuristic",
                mapped_discipline="ORÇAMENTO",
                metadata={"filename": path.name},
            )

        if any(k in stem_lower for k in ("tdr", "termo_de_referencia", "memorial")):
            return ClassificationResult(
                discipline_slug="geral",
                content_type="tdrs",
                confidence=0.85,
                source="filename_heuristic",
                mapped_discipline="GERAL",
                metadata={"filename": path.name},
            )

        domain = detect_domain(path.stem)
        domain_to_slug = {
            "structural": "estruturas",
            "cost": "orcamento",
            "budget": "orcamento",
            "geotechnical": "geotecnia",
            "hydraulic": "hidrossanitario",
            "electrical": "eletrica",
            "catalog": "arquitetura",
            "norm": "estruturas",
            "general": "geral",
        }
        slug = domain_to_slug.get(domain, "geral")
        ct = self._resolve_content_type(path, slug, content_type_hint)
        return ClassificationResult(
            discipline_slug=slug,
            content_type=ct,
            confidence=0.65,
            source="domain_detector",
            mapped_discipline=slug.upper(),
            metadata={"domain": domain, "filename": path.name},
        )

    def ingest(
        self,
        source: Path,
        *,
        discipline_hint: Optional[str] = None,
        content_type_hint: Optional[str] = None,
        layer: str = "raw",
        copy: bool = True,
        force: bool = False,
    ) -> dict[str, Any]:
        source = source.resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Arquivo não encontrado: {source}")
        if source.suffix.lower() not in _INGESTABLE_SUFFIXES:
            raise ValueError(
                f"Tipo não suportado: {source.suffix}. "
                f"Use: {', '.join(sorted(_INGESTABLE_SUFFIXES))}"
            )

        layer = allowed_ingest_layer(layer)
        classification = self.classify(
            source,
            discipline_hint=discipline_hint,
            content_type_hint=content_type_hint,
        )
        target_dir = get_documents_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / source.name

        assert_ingest_target(target_path)

        record: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": str(source),
            "target": str(target_path),
            "action": "copy" if copy else "classified_only",
            "classification": classification.to_dict(),
            "content_hash": file_content_hash(source),
            "integrated_path": "raw/documents",
        }

        if target_path.exists() and not force:
            existing_hash = file_content_hash(target_path)
            if existing_hash == record["content_hash"]:
                record["status"] = "skipped_duplicate"
                return record
            record["status"] = "skipped_exists"
            record["reason"] = "target exists — use --force to overwrite"
            return record

        meta_payload = build_metadata_record(
            discipline_slugs=[classification.discipline_slug],
            layer=layer,
            content_type=classification.content_type,
            source=classification.source,
            confidence=classification.confidence,
            filename=source.name,
            extra={
                "mapped_discipline": classification.mapped_discipline,
                "content_hash": record["content_hash"],
                **classification.metadata,
            },
        )

        if copy:
            shutil.copy2(source, target_path)
            meta_path = write_metadata(target_path, meta_payload)
            record["metadata_path"] = str(meta_path)
            record["document_id"] = meta_payload["id"]
            append_catalog_entry({
                "id": meta_payload["id"],
                "path": str(target_path),
                "discipline": meta_payload["discipline"],
                "layer": layer,
                "content_type": classification.content_type,
                "content_hash": record["content_hash"],
                "filename": source.name,
                "source": classification.source,
                "confidence": classification.confidence,
            })
            record["status"] = "copied"
            logger.info(
                "ingested %s → %s (disc=%s type=%s)",
                source.name,
                target_path,
                classification.discipline_slug,
                classification.content_type,
            )
        else:
            record["status"] = "classified"
            record["document_id"] = meta_payload["id"]

        return record

    def ingest_batch(
        self,
        sources: list[Path],
        **kwargs: Any,
    ) -> dict[str, Any]:
        results = []
        errors = []
        for src in sources:
            try:
                results.append(self.ingest(src, **kwargs))
            except Exception as exc:
                errors.append({"source": str(src), "error": str(exc)})
        return {
            "ingested": len([r for r in results if r.get("status") == "copied"]),
            "skipped": len([r for r in results if r.get("status", "").startswith("skipped")]),
            "results": results,
            "errors": errors,
        }


def get_ingester() -> DisciplineIngester:
    return DisciplineIngester()
