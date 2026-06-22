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

    def reconcile_with_disk(self) -> bool:
        """
        Garante que pastas BR-YYYY-MM no disco apareçam no index.json.
        Recupera períodos importados antes da correção de índice multi-período.
        """
        if not PRICE_BANK_ROOT.is_dir():
            return False
        known = {r.reference for r in self.references}
        changed = False
        for child in sorted(PRICE_BANK_ROOT.iterdir()):
            if not child.is_dir() or not REF_PATTERN.match(child.name):
                continue
            ref = child.name.upper()
            if ref in known:
                continue
            manifest_path = child / "manifest.json"
            if not manifest_path.is_file():
                continue
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            self.references.append(
                PriceBankReferenceEntry(
                    reference=ref,
                    source=str(data.get("source") or "sinapi"),
                    synced_at=str(data.get("synced_at") or ""),
                    default_uf=str(data.get("uf") or "SP").upper(),
                    counts=dict(data.get("counts") or {}),
                    metadata=dict(data.get("metadata") or {}),
                )
            )
            known.add(ref)
            changed = True
        if not changed:
            return False
        self.references.sort(
            key=lambda r: (r.reference[:3], r.reference),
            reverse=True,
        )
        self.save()
        return True

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
        set_active: bool = True,
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
