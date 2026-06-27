"""
Banco de preços estruturado — composições fechadas, abertas (CPU) e insumos.

Persistência: backend/knowledge/price_bank/
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pricing.budget.price_bank_index import PriceBankIndex, PRICE_BANK_ROOT

PRICE_BANK_DIR = PRICE_BANK_ROOT  # compat — diretório raiz; dados em subpastas BR-YYYY-MM
MANIFEST_NAME = "manifest.json"
CLOSED_NAME = "compositions_closed.json"
OPEN_NAME = "compositions_open.json"
INSUMOS_NAME = "insumos.json"
LABOR_CHARGES_NAME = "labor_charges.json"


@dataclass
class CompositionItem:
    item_type: str  # insumo | mao_obra | equipamento | composicao
    code: str
    description: str
    unit: str
    coefficient: float
    unit_price: float
    partial_cost: float
    unit_price_sem: float = 0.0
    partial_cost_sem: float = 0.0
    tp2: str = ""  # marcação regional SEMINF (ex. AS = associado a São Paulo)
    classificacao: str = ""  # SINAPI ISD: SERVIÇOS, MATERIAL, MAO DE OBRA…
    origem_preco: str = ""  # SINAPI ISD: C, CR…
    situacao: str = ""  # SINAPI Analítico: COM CUSTO, EM ESTUDO…

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CompositionOpen:
    code: str
    description: str
    unit: str
    total_price: float  # com desoneração (CCD) — sintético regional
    items: list[CompositionItem] = field(default_factory=list)
    total_price_sem: float = 0.0  # sem desoneração (CSD) — sintético regional
    grupo: str = ""  # SINAPI: Alvenaria de Vedação, Acessibilidade…
    tp2: str = ""  # AS quando %AS > 0 (SINAPI) ou marcação SEMINF

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "description": self.description,
            "unit": self.unit,
            "total_price": self.total_price,
            "total_price_sem": self.total_price_sem or self.total_price,
            "grupo": self.grupo,
            "tp2": self.tp2,
            "items": [i.to_dict() for i in self.items],
        }


@dataclass
class CompositionClosed:
    code: str
    description: str
    unit: str
    price: float  # com desoneração (ComD) — UF padrão na importação
    price_sem_desoneracao: float = 0.0  # sem desoneração (SemD) — UF padrão
    regional: dict[str, dict[str, float]] = field(
        default_factory=dict
    )  # UF -> {comd, semd, pct_as_comd, pct_as_semd}
    tp2: str = ""  # marcação regional da aba Base SEMINF (ex. AS = São Paulo)
    grupo: str = ""  # SINAPI CSD/CCD: grupo da composição

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def price_for_uf(self, uf: str, *, sem: bool = False) -> float:
        uf = uf.upper()
        reg = self.regional.get(uf) or {}
        if sem:
            return float(reg.get("semd") or reg.get("sem") or self.price_sem_desoneracao or self.price)
        return float(reg.get("comd") or reg.get("com") or self.price)


@dataclass
class InsumoRecord:
    code: str
    description: str
    unit: str
    price: float  # com desoneração (ComD)
    origin: str = ""  # aba de origem: ISD | ICD
    price_sem_desoneracao: float = 0.0
    regional: dict[str, dict[str, float]] = field(default_factory=dict)
    regional_as: dict[str, dict[str, float]] = field(
        default_factory=dict
    )  # UF → {comd, semd, ise} — preco_regional_as (fórmula Caixa col. L/M/N)
    classificacao: str = ""  # SINAPI: SERVIÇOS, MATERIAL, MAO DE OBRA…
    origem_preco: str = ""  # SINAPI: C, CR…

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def price_for_uf(self, uf: str, *, sem: bool = False) -> float:
        uf = uf.upper()
        reg = self.regional.get(uf) or {}
        if sem:
            return float(reg.get("semd") or reg.get("sem") or self.price_sem_desoneracao or self.price)
        return float(reg.get("comd") or reg.get("com") or self.price)


@dataclass
class PriceBankManifest:
    source: str
    reference: str
    uf: str = ""
    desonerado: bool = True
    synced_at: str = ""
    counts: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PriceBankStore:
    def __init__(self, root: Path | None = None, reference: str | None = None) -> None:
        if root is not None:
            self.root = root
        else:
            PriceBankIndex.migrate_legacy_flat_bank()
            self.root = PriceBankIndex.reference_dir(reference)
        self.root.mkdir(parents=True, exist_ok=True)

    @classmethod
    def for_reference(cls, reference: str) -> PriceBankStore:
        return cls(reference=reference)

    @property
    def manifest_path(self) -> Path:
        return self.root / MANIFEST_NAME

    def save_bank(
        self,
        *,
        source: str,
        reference: str,
        closed: list[CompositionClosed],
        open_compositions: dict[str, CompositionOpen],
        insumos: list[InsumoRecord],
        uf: str = "",
        desonerado: bool = True,
        metadata: dict[str, Any] | None = None,
        labor_charges: dict[str, Any] | None = None,
        set_active: bool = False,
    ) -> PriceBankManifest:
        open_items_total = sum(len(c.items) for c in open_compositions.values())
        meta = dict(metadata or {})
        if labor_charges:
            meta["labor_charges"] = True
        manifest = PriceBankManifest(
            source=source,
            reference=reference,
            uf=uf,
            desonerado=desonerado,
            synced_at=datetime.now(timezone.utc).isoformat(),
            counts={
                "compositions_closed": len(closed),
                "compositions_open": len(open_compositions),
                "insumos": len(insumos),
                "open_items_total": open_items_total,
            },
            metadata=meta,
        )

        if labor_charges:
            (self.root / LABOR_CHARGES_NAME).write_text(
                json.dumps(labor_charges, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        (self.root / CLOSED_NAME).write_text(
            json.dumps([c.to_dict() for c in closed], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (self.root / OPEN_NAME).write_text(
            json.dumps(
                {k: v.to_dict() for k, v in open_compositions.items()},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (self.root / INSUMOS_NAME).write_text(
            json.dumps([i.to_dict() for i in insumos], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.manifest_path.write_text(
            json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        idx = PriceBankIndex.load()
        idx.register(
            reference,
            source=source,
            default_uf=uf.upper() or "SP",
            synced_at=manifest.synced_at,
            counts=manifest.counts,
            metadata={
                **(metadata or {}),
                "all_ufs": bool(closed and getattr(closed[0], "regional", None)),
            },
            set_active=set_active,
        )
        return manifest

    def load_manifest(self) -> PriceBankManifest | None:
        if not self.manifest_path.is_file():
            return None
        data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return PriceBankManifest(**data)

    def load_closed(self) -> list[dict[str, Any]]:
        path = self.root / CLOSED_NAME
        if not path.is_file():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def load_open(self) -> dict[str, dict[str, Any]]:
        path = self.root / OPEN_NAME
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def load_insumos(self) -> list[dict[str, Any]]:
        path = self.root / INSUMOS_NAME
        if not path.is_file():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def load_labor_charges(self) -> dict[str, Any]:
        path = self.root / LABOR_CHARGES_NAME
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
        manifest = self.load_manifest()
        if manifest and isinstance(manifest.metadata.get("labor_charges_snapshot"), dict):
            return manifest.metadata["labor_charges_snapshot"]
        return {}

    @staticmethod
    def _stored_open_items_stale(raw: dict[str, Any], applied: dict[str, Any]) -> bool:
        """Detecta itens gravados com preço 0 que passam a ter valor após fallback SP (%AS)."""
        old_by_code = {str(i.get("code") or ""): i for i in (raw.get("items") or [])}
        for item in applied.get("items") or []:
            code = str(item.get("code") or "")
            old = old_by_code.get(code)
            if not old:
                continue
            new_unit = float(item.get("unit_price") or 0)
            old_unit = float(old.get("unit_price") or 0)
            if old_unit <= 0 and new_unit > 0:
                return True
        return False

    def _patch_stored_open_items(self, code: str, applied_items: list[dict[str, Any]]) -> None:
        path = self.root / OPEN_NAME
        if not path.is_file():
            return
        raw_open = self.load_open()
        comp = raw_open.get(code)
        if not comp:
            return
        by_code = {str(i.get("code") or ""): i for i in applied_items}
        price_keys = ("unit_price", "partial_cost", "unit_price_sem", "partial_cost_sem", "tp2")
        for item in comp.get("items") or []:
            src = by_code.get(str(item.get("code") or ""))
            if not src:
                continue
            for key in price_keys:
                if item.get(key) != src.get(key):
                    item[key] = src[key]
        path.write_text(
            json.dumps(raw_open, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_open_composition(
        self,
        code: str,
        *,
        uf: str = "SP",
    ) -> dict[str, Any] | None:
        from pricing.budget.price_bank_regional import (
            _resolve_display_totals,
            apply_uf_to_open_composition,
        )

        key = str(code).strip()
        raw = self.load_open().get(key)
        if not raw:
            return None
        closed = self.load_closed()
        insumos = self.load_insumos()
        manifest = self.load_manifest()
        default_uf = (manifest.uf if manifest else "") or "SP"
        use_uf = (uf or default_uf).upper()
        has_regional = any((r.get("regional") for r in closed if r.get("regional")))
        if not has_regional:
            result = dict(raw)
            if manifest:
                result["price_uf"] = default_uf
            closed_com = float(result.get("total_price") or 0)
            closed_sem = float(result.get("total_price_sem") or closed_com)
            for row in closed:
                if str(row.get("code", "")).strip() == key:
                    closed_com = float(row.get("price") or closed_com)
                    closed_sem = float(
                        row.get("price_sem_desoneracao") or row.get("price") or closed_sem
                    )
                    break
            items = result.get("items") or []
            analytical_com = round(
                sum(float(i.get("partial_cost") or 0) for i in items), 2
            )
            analytical_sem = round(
                sum(float(i.get("partial_cost_sem") or i.get("partial_cost") or 0) for i in items),
                2,
            )
            display_com, display_sem = _resolve_display_totals(
                raw=raw,
                closed_com=closed_com,
                closed_sem=closed_sem,
                analytical_com=analytical_com,
                analytical_sem=analytical_sem,
            )
            result["total_price"] = display_com
            result["total_price_sem"] = display_sem
            result["analytical_total_com"] = analytical_com
            result["analytical_total_sem"] = analytical_sem
            return result

        result = apply_uf_to_open_composition(
            raw,
            uf=use_uf,
            closed_rows=closed,
            insumo_rows=insumos,
            labor_charges=self.load_labor_charges(),
        )
        if use_uf == default_uf and self._stored_open_items_stale(raw, result):
            self._patch_stored_open_items(key, result.get("items") or [])
        return result

    def closed_as_provider_rows(self, uf: str | None = None) -> list[dict[str, Any]]:
        """Linhas tabulares para SINAPI provider (composições fechadas)."""
        manifest = self.load_manifest()
        use_uf = (uf or (manifest.uf if manifest else "SP") or "SP").upper()
        rows: list[dict[str, Any]] = []
        for row in self.load_closed():
            reg = row.get("regional") or {}
            if use_uf in reg:
                price_com = float(reg[use_uf].get("comd") or reg[use_uf].get("com") or 0)
                price_sem = float(reg[use_uf].get("semd") or reg[use_uf].get("sem") or price_com)
            else:
                price_com = float(row.get("price") or 0)
                price_sem = float(row.get("price_sem_desoneracao") or price_com)
            rows.append(
                {
                    "code": row.get("code", ""),
                    "description": row.get("description", ""),
                    "unit": row.get("unit", "un"),
                    "price": price_com,
                    "metadata": {"price_sem_desoneracao": price_sem, "uf": use_uf},
                }
            )
        return rows

    @staticmethod
    def list_all_references() -> list[dict[str, Any]]:
        return PriceBankIndex.load().list_references()

    @staticmethod
    def set_active_reference(reference: str) -> str:
        idx = PriceBankIndex.load()
        idx.set_active(reference)
        return idx.active_reference

    def stats(self) -> dict[str, Any]:
        manifest = self.load_manifest()
        if not manifest:
            return {
                "loaded": False,
                "counts": {
                    "compositions_closed": 0,
                    "compositions_open": 0,
                    "insumos": 0,
                    "open_items_total": 0,
                },
            }
        return {
            "loaded": True,
            "manifest": manifest.to_dict(),
            "counts": manifest.counts,
            "sample_closed": self.load_closed()[:3],
            "sample_open_codes": list(self.load_open().keys())[:5],
            "references": PriceBankIndex.load().list_references(),
            "active_reference": PriceBankIndex.load().active_reference,
        }

