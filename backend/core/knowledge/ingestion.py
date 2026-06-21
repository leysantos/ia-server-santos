"""
Knowledge Activation — ingestão flat.

Pipeline: arquivo → classifier → knowledge/raw/documents/ + .knowledge.json + catalog.jsonl
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import unicodedata
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

_INGESTABLE_SUFFIXES = {
    ".pdf", ".csv", ".xlsx", ".xls", ".xlsm", ".json", ".md", ".txt", ".docx", ".xml",
}
INGESTABLE_SUFFIXES = _INGESTABLE_SUFFIXES


def _slugify_storage_name(label: str, suffix: str, max_len: int = 72) -> str:
    text = unicodedata.normalize("NFKD", label)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[-\s]+", "_", text.strip()).strip("_")
    if not text:
        text = "documento"
    return f"{text[:max_len]}{suffix}"


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

    def _resolve_collision_target(
        self,
        source: Path,
        target_dir: Path,
        *,
        name: Optional[str],
        role: str,
    ) -> tuple[Path, bool]:
        """
        Mesmo nome de upload, conteúdo diferente — gera caminho único no disco.
        Permite coexistir base de preços + modelo de orçamento (PPD exporta o mesmo nome).
        """
        incoming_hash = file_content_hash(source)
        suffix = source.suffix.lower()
        role_tag = {"modelo_orcamento": "modelo-orcamento", "base_precos": "base-precos"}.get(
            role, "import"
        )

        candidates: list[str] = []
        if name and name.strip():
            candidates.append(_slugify_storage_name(name.strip(), suffix))
        candidates.append(f"{source.stem}--{role_tag}{suffix}")

        for candidate in candidates:
            path = target_dir / candidate
            if not path.exists():
                return path, True
            if file_content_hash(path) == incoming_hash:
                return path, False

        counter = 2
        while counter < 100:
            path = target_dir / f"{source.stem}--{role_tag}-{counter}{suffix}"
            if not path.exists():
                return path, True
            if file_content_hash(path) == incoming_hash:
                return path, False
            counter += 1

        raise ValueError("Não foi possível alocar nome único para o arquivo na biblioteca")

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
        name: Optional[str] = None,
        description: Optional[str] = None,
        register_price_base: bool = False,
        register_budget_model: bool = False,
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

        should_register_model = register_budget_model or classification.content_type == "modelos_orcamento"
        should_register_price = register_price_base or classification.content_type in (
            "sinapi",
            "tcpo",
        )

        target_path = target_dir / source.name
        storage_renamed = False

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
                if should_register_model:
                    return self._attach_budget_model_to_existing(
                        target_path,
                        record,
                        classification,
                        name=name,
                        description=description,
                        layer=layer,
                    )
                record["status"] = "skipped_duplicate"
                record["reason"] = (
                    "Arquivo idêntico já está no catálogo."
                    + (" Marque «Substituir» para atualizar metadados." if should_register_model else "")
                )
                return record

            role: str | None = None
            if should_register_model:
                role = "modelo_orcamento"
            elif should_register_price:
                role = "base_precos"

            if role:
                target_path, storage_renamed = self._resolve_collision_target(
                    source, target_dir, name=name, role=role
                )
                record["target"] = str(target_path)
                if storage_renamed:
                    record["storage_renamed"] = True
                    record["original_upload_name"] = source.name
                    role_label = "modelo de orçamento" if role == "modelo_orcamento" else "base de preços"
                    record["reason"] = (
                        f"Salvo como «{target_path.name}» — o nome original já é usado por outro "
                        f"documento ({role_label} separado no catálogo)."
                    )
            else:
                record["status"] = "skipped_exists"
                record["reason"] = (
                    "Já existe outro arquivo com o mesmo nome. "
                    "Marque «Substituir arquivo existente» para sobrescrever."
                )
                return record

        assert_ingest_target(target_path)

        extra_meta: dict[str, Any] = {
            "mapped_discipline": classification.mapped_discipline,
            "content_hash": record["content_hash"],
            **classification.metadata,
        }
        if storage_renamed:
            extra_meta["original_upload_name"] = source.name
            extra_meta["storage_renamed"] = True

        from core.knowledge.norm_packs.legal import legal_source_for_ingest

        legal_src = legal_source_for_ingest(classification.content_type)
        if legal_src:
            extra_meta["legal_source"] = legal_src

        meta_payload = build_metadata_record(
            discipline_slugs=[classification.discipline_slug],
            layer=layer,
            content_type=classification.content_type,
            source=classification.source,
            confidence=classification.confidence,
            filename=target_path.name,
            name=name,
            description=description,
            extra=extra_meta,
        )

        if copy:
            shutil.copy2(source, target_path)
            meta_path = write_metadata(target_path, meta_payload)
            record["metadata_path"] = str(meta_path)
            record["document_id"] = meta_payload["id"]

            price_rows: list[dict[str, Any]] = []
            is_tabular = source.suffix.lower() in (".xlsm", ".csv", ".xlsx", ".xls")
            parse_prices = should_register_price or (
                is_tabular and not should_register_model
            )
            if parse_prices:
                from core.knowledge.price_registry import (
                    is_price_content_type,
                    parse_price_rows_from_file,
                    set_active_price_document,
                    write_price_items,
                )

                price_rows = parse_price_rows_from_file(target_path)
                if price_rows:
                    items_path = write_price_items(target_path, price_rows)
                    record["price_items_path"] = str(items_path)
                    record["price_item_count"] = len(price_rows)
                    meta_payload["price_item_count"] = len(price_rows)
                    meta_payload["has_price_items"] = True
                    write_metadata(target_path, meta_payload)
                    set_active_price_document(meta_payload["id"])
                    record["price_base_active"] = True
                elif should_register_price and is_price_content_type(classification.content_type):
                    record["price_base_warning"] = "Nenhum item de preço detectado no arquivo"

            if should_register_model:
                self._process_budget_model(target_path, meta_payload, record)

            append_catalog_entry({
                "id": meta_payload["id"],
                "name": meta_payload.get("name", target_path.stem),
                "description": meta_payload.get("description", ""),
                "path": str(target_path),
                "discipline": meta_payload["discipline"],
                "layer": layer,
                "content_type": classification.content_type,
                "content_hash": record["content_hash"],
                "filename": target_path.name,
                "original_upload_name": source.name if storage_renamed else None,
                "source": classification.source,
                "confidence": classification.confidence,
                "price_item_count": record.get("price_item_count", 0),
                "has_price_items": bool(price_rows),
                "has_budget_model": bool(record.get("budget_model_indexed") or should_register_model),
                "service_count": record.get("service_count", 0),
            })
            record["status"] = "copied"
            if storage_renamed:
                record["saved_as"] = target_path.name
            logger.info(
                "ingested %s → %s (disc=%s type=%s%s)",
                source.name,
                target_path,
                classification.discipline_slug,
                classification.content_type,
                " renamed" if storage_renamed else "",
            )
        else:
            record["status"] = "classified"
            record["document_id"] = meta_payload["id"]

        return record

    def _process_budget_model(
        self,
        target_path: Path,
        meta_payload: dict[str, Any],
        record: dict[str, Any],
    ) -> None:
        from core.knowledge.budget_model_indexer import index_budget_model_document
        from core.knowledge.metadata import write_metadata
        from pricing.budget.budget_model_extractor import (
            extract_budget_model_summary,
            write_budget_model_sidecar,
        )

        try:
            model = extract_budget_model_summary(target_path)
            write_budget_model_sidecar(target_path, model)
            meta_payload["budget_model_summary"] = (model.get("summary_text") or "")[:500]
            meta_payload["service_count"] = model.get("service_count", 0)
            meta_payload["has_budget_model"] = True
            write_metadata(target_path, meta_payload)
            indexed = index_budget_model_document(target_path, meta_payload)
            record["budget_model_indexed"] = indexed
            record["service_count"] = model.get("service_count", 0)
            if model.get("error"):
                record["budget_model_warning"] = str(model["error"])
        except Exception as exc:
            logger.warning("Falha ao extrair/indexar modelo de orçamento: %s", exc)
            record["budget_model_warning"] = str(exc)

    def _attach_budget_model_to_existing(
        self,
        target_path: Path,
        record: dict[str, Any],
        classification: ClassificationResult,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        layer: str = "raw",
    ) -> dict[str, Any]:
        """Arquivo já no disco — indexa WBS sem recopiar (ex.: PPD já importado como base de preço)."""
        from core.knowledge.metadata import read_metadata, write_metadata

        existing = read_metadata(target_path) or {}
        meta_payload: dict[str, Any] = dict(existing)
        if name:
            meta_payload["name"] = name
        if description:
            meta_payload["description"] = description
        meta_payload["has_budget_model"] = True

        self._process_budget_model(target_path, meta_payload, record)
        write_metadata(target_path, meta_payload)

        record["document_id"] = meta_payload.get("id")
        record["metadata_path"] = str(target_path.with_name(target_path.name + ".knowledge.json"))
        if record.get("budget_model_warning") and not record.get("budget_model_indexed"):
            record["status"] = "error"
            record["reason"] = record["budget_model_warning"]
            return record

        record["status"] = "budget_model_attached"
        record["reason"] = (
            "Arquivo já estava na biblioteca — modelo WBS extraído e indexado para a IA."
        )

        append_catalog_entry({
            "id": meta_payload.get("id", ""),
            "name": meta_payload.get("name", target_path.stem),
            "description": meta_payload.get("description", ""),
            "path": str(target_path),
            "discipline": meta_payload.get("discipline", [classification.discipline_slug]),
            "layer": layer,
            "content_type": classification.content_type
            if classification.content_type == "modelos_orcamento"
            else meta_payload.get("content_type", classification.content_type),
            "content_hash": record.get("content_hash", ""),
            "filename": target_path.name,
            "source": classification.source,
            "confidence": classification.confidence,
            "price_item_count": meta_payload.get("price_item_count", 0),
            "has_price_items": meta_payload.get("has_price_items", False),
            "has_budget_model": True,
            "service_count": record.get("service_count", 0),
        })
        logger.info("budget model attached to existing %s", target_path.name)
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
            "ingested": len(
                [r for r in results if r.get("status") in ("copied", "budget_model_attached")]
            ),
            "skipped": len([r for r in results if r.get("status", "").startswith("skipped")]),
            "results": results,
            "errors": errors,
        }


def process_budget_model_sync(
    target_path: Path,
    meta_payload: dict[str, Any],
    record: dict[str, Any],
) -> None:
    """Entry point síncrono — usar com await run_sync(...)."""
    get_ingester()._process_budget_model(target_path, meta_payload, record)


def ingest_batch_sync(sources: list[Path], **kwargs: Any) -> dict[str, Any]:
    """Ingestão em lote fora do event loop asyncio."""
    return get_ingester().ingest_batch(sources, **kwargs)


def get_ingester() -> DisciplineIngester:
    return DisciplineIngester()
