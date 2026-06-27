"""Índice de múltiplas referências mensais do banco de preços SINAPI."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import KNOWLEDGE_DIR

PRICE_BANK_ROOT = KNOWLEDGE_DIR / "price_bank"
INDEX_NAME = "index.json"
REF_PATTERN = re.compile(r"^BR-(\d{4})-(\d{2})$", re.I)
# Pastas BR-* com manifest (SINAPI, SICRO, SEMINF, …)
BANK_DIR_PATTERN = re.compile(r"^BR-.+$", re.I)


@dataclass
class PriceBankReferenceEntry:
    reference: str
    source: str = "sinapi"
    synced_at: str = ""
    default_uf: str = "SP"
    counts: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def label(self) -> str:
        m = REF_PATTERN.match(self.reference)
        if m:
            return f"{m.group(2)}/{m.group(1)}"
        return self.reference


@dataclass
class PriceBankIndex:
    active_reference: str = ""
    references: list[PriceBankReferenceEntry] = field(default_factory=list)

    @staticmethod
    def index_path() -> Path:
        return PRICE_BANK_ROOT / INDEX_NAME

    @classmethod
    def load(cls) -> PriceBankIndex:
        cls.migrate_legacy_flat_bank()
        path = cls.index_path()
        if not path.is_file():
            idx = cls()
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
            refs = [PriceBankReferenceEntry(**r) for r in data.get("references") or []]
            idx = cls(active_reference=str(data.get("active_reference") or ""), references=refs)
        idx.reconcile_with_disk()
        return idx

    def reconcile_with_disk(self, *, prune_orphans: bool = False) -> bool:
        """
        Sincroniza index.json com pastas BR-* no disco (manifest.json).
        - Adiciona referências presentes no disco mas ausentes do índice.
        - Atualiza contagens/metadados quando o manifest no disco mudou.
        - Com prune_orphans=True, remove entradas sem pasta correspondente.
        """
        if not PRICE_BANK_ROOT.is_dir():
            return False
        disk_refs: dict[str, PriceBankReferenceEntry] = {}
        for child in sorted(PRICE_BANK_ROOT.iterdir()):
            if not child.is_dir() or not BANK_DIR_PATTERN.match(child.name):
                continue
            manifest_path = child / "manifest.json"
            if not manifest_path.is_file():
                continue
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            ref = child.name.upper()
            disk_refs[ref] = PriceBankReferenceEntry(
                reference=ref,
                source=str(data.get("source") or "sinapi"),
                synced_at=str(data.get("synced_at") or ""),
                default_uf=str(data.get("uf") or "SP").upper(),
                counts=dict(data.get("counts") or {}),
                metadata=dict(data.get("metadata") or {}),
            )

        changed = False
        by_ref = {r.reference: r for r in self.references}
        for ref, entry in disk_refs.items():
            existing = by_ref.get(ref)
            if existing is None:
                self.references.append(entry)
                by_ref[ref] = entry
                changed = True
            elif (
                existing.source != entry.source
                or existing.synced_at != entry.synced_at
                or existing.default_uf != entry.default_uf
                or existing.counts != entry.counts
                or existing.metadata != entry.metadata
            ):
                existing.source = entry.source
                existing.synced_at = entry.synced_at
                existing.default_uf = entry.default_uf
                existing.counts = entry.counts
                existing.metadata = entry.metadata
                changed = True

        if prune_orphans:
            before = len(self.references)
            self.references = [r for r in self.references if r.reference in disk_refs]
            if len(self.references) != before:
                changed = True
            if self.active_reference and self.active_reference not in disk_refs:
                self.active_reference = self.references[0].reference if self.references else ""
                changed = True

        if not changed:
            return False
        self.references.sort(
            key=lambda r: (r.reference[:3], r.reference),
            reverse=True,
        )
        self.save()
        return True

    def prune_orphan_references(self) -> bool:
        """Remove do índice referências sem pasta/manifest no disco."""
        return self.reconcile_with_disk(prune_orphans=True)

    def save(self) -> None:
        PRICE_BANK_ROOT.mkdir(parents=True, exist_ok=True)
        self.index_path().write_text(
            json.dumps(
                {
                    "active_reference": self.active_reference,
                    "references": [r.to_dict() for r in self.references],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    @classmethod
    def migrate_legacy_flat_bank(cls) -> None:
        """Move price_bank/*.json plano para subpasta BR-YYYY-MM."""
        root = PRICE_BANK_ROOT
        legacy_manifest = root / "manifest.json"
        if not legacy_manifest.is_file() or cls.index_path().is_file():
            return
        data = json.loads(legacy_manifest.read_text(encoding="utf-8"))
        ref = str(data.get("reference") or "BR-local")
        ref = ref.replace("/", "-")
        if not ref.upper().startswith("BR-"):
            ref = f"BR-{ref}"
        dest = root / ref
        if dest.exists():
            return
        dest.mkdir(parents=True, exist_ok=True)
        for name in ("manifest.json", "compositions_closed.json", "compositions_open.json", "insumos.json"):
            src = root / name
            if src.is_file():
                shutil.move(str(src), str(dest / name))
        idx = cls()
        idx.references.append(
            PriceBankReferenceEntry(
                reference=ref,
                source=str(data.get("source") or "sinapi"),
                synced_at=str(data.get("synced_at") or ""),
                default_uf=str(data.get("uf") or "SP"),
                counts=dict(data.get("counts") or {}),
                metadata=dict(data.get("metadata") or {}),
            )
        )
        idx.active_reference = ref
        idx.save()

    def register(
        self,
        reference: str,
        *,
        source: str,
        default_uf: str,
        synced_at: str,
        counts: dict[str, int],
        metadata: dict[str, Any] | None = None,
        set_active: bool = False,
    ) -> None:
        reference = reference.replace("/", "-").upper()
        if not reference.startswith("BR-"):
            reference = f"BR-{reference}"
        entry = PriceBankReferenceEntry(
            reference=reference,
            source=source,
            synced_at=synced_at or datetime.now(timezone.utc).isoformat(),
            default_uf=default_uf.upper(),
            counts=counts,
            metadata=metadata or {},
        )
        self.references = [r for r in self.references if r.reference != reference]
        self.references.insert(0, entry)
        self.references.sort(
            key=lambda r: (r.reference[:3], r.reference),
            reverse=True,
        )
        if set_active:
            self.active_reference = reference
        self.save()

    def set_active(self, reference: str) -> None:
        reference = reference.replace("/", "-")
        if not any(r.reference == reference for r in self.references):
            raise ValueError(f"Referência '{reference}' não encontrada")
        self.active_reference = reference
        self.save()

    def delete_reference(self, reference: str) -> bool:
        """Remove referência do índice. Retorna False se não existia."""
        reference = reference.replace("/", "-")
        before = len(self.references)
        self.references = [r for r in self.references if r.reference != reference]
        if len(self.references) == before:
            return False
        if self.active_reference == reference:
            self.active_reference = self.references[0].reference if self.references else ""
        self.save()
        return True

    def list_references(self) -> list[dict[str, Any]]:
        return [
            {
                **r.to_dict(),
                "label": r.label,
                "active": r.reference == self.active_reference,
            }
            for r in self.references
        ]

    @classmethod
    def resolve_reference(cls, reference: str | None = None) -> str:
        idx = cls.load()
        if reference:
            return reference.replace("/", "-")
        if idx.active_reference:
            return idx.active_reference
        if idx.references:
            return idx.references[0].reference
        return "BR-local"

    @classmethod
    def reference_dir(cls, reference: str | None = None) -> Path:
        ref = cls.resolve_reference(reference)
        return PRICE_BANK_ROOT / ref
