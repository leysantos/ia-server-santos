"""Recálculo / fork de bases SEMINF — preserva referências anteriores no histórico."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pricing.budget.price_bank_store import CompositionClosed, CompositionItem, CompositionOpen, PriceBankStore
from pricing.budget.seminf_base_parser import is_seminf_regional_code
from pricing.budget.seminf_open_parser import normalize_seminf_code

_REVISION_SUFFIX = re.compile(r"-R(\d+)$", re.I)
_SINAPI_PERIOD = re.compile(r"^BR-(\d{4})-(\d{2})$", re.I)
_SEMINF_PERIOD = re.compile(r"^BR-(?:DP-SEMINF|SEMINF)-(\d{4})-(\d{2})$", re.I)


@dataclass
class SeminfRefreshResult:
    reference: str
    sinapi_reference: str
    uf: str
    parent_reference: str = ""
    compositions_updated: int = 0
    items_updated: int = 0
    items_missing_price: int = 0
    warnings: list[str] = field(default_factory=list)


def seminf_source_slug(reference: str) -> str:
    ref = reference.replace("/", "-").upper()
    if ref.startswith("BR-DP-SEMINF-"):
        return "DP-SEMINF"
    if ref.startswith("BR-SEMINF-"):
        return "SEMINF"
    return "DP-SEMINF"


def seminf_root_reference(reference: str) -> str:
    """Remove sufixo legado -R01 (bases antigas)."""
    ref = reference.replace("/", "-").upper()
    return _REVISION_SUFFIX.sub("", ref)


def parse_seminf_reference_period(reference: str) -> tuple[int, int] | None:
    ref = seminf_root_reference(reference)
    m = _SEMINF_PERIOD.match(ref)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _period_key(year: int, month: int) -> int:
    return year * 100 + month


def validate_seminf_refresh_source(
    source_reference: str,
    target_reference: str,
    *,
    allow_backfill: bool = False,
) -> bool:
    """
    Fonte deve ser estritamente anterior ao mês destino (ex. 02→03, 04→05).

    Com allow_backfill=True, aceita fonte posterior (ex. 04→03) para preencher lacunas
    no histórico — retorna True quando foi backfill.
    """
    src = parse_seminf_reference_period(source_reference)
    tgt = parse_seminf_reference_period(target_reference)
    if not src or not tgt:
        return False
    if _period_key(*src) >= _period_key(*tgt):
        if not allow_backfill:
            raise ValueError(
                f"A base fonte ({source_reference}) deve ser de um mês anterior ao destino "
                f"({target_reference}). Para o primeiro mês do histórico, importe a pasta SEMINF "
                f"do período diretamente."
            )
        return True
    return False


def infer_seminf_reference_from_sinapi(
    sinapi_reference: str,
    *,
    source_slug: str = "DP-SEMINF",
) -> str:
    """BR-2026-05 → BR-DP-SEMINF-2026-05 (mês da atualização SINAPI)."""
    ref = sinapi_reference.replace("/", "-").upper()
    m = _SINAPI_PERIOD.match(ref)
    if not m:
        raise ValueError(
            f"Referência SINAPI inválida: {sinapi_reference} — esperado BR-YYYY-MM"
        )
    slug = source_slug.upper().replace("/", "-")
    return f"BR-{slug}-{m.group(1)}-{m.group(2)}"


class _SeminfPriceResolver:
    """SINAPI → sinapi_ref; SEMINF regional → seminf_ref (base fonte)."""

    def __init__(
        self,
        *,
        sinapi_ref: str,
        seminf_ref: str,
        uf: str = "AM",
    ) -> None:
        self.uf = uf.upper()
        sinapi = PriceBankStore.for_reference(sinapi_ref)
        seminf = PriceBankStore.for_reference(seminf_ref)
        self._closed_sinapi = {str(r["code"]).strip(): r for r in sinapi.load_closed()}
        self._insumos_sinapi = {str(r["code"]).strip(): r for r in sinapi.load_insumos()}
        self._closed_seminf = {
            normalize_seminf_code(str(r["code"])): r for r in seminf.load_closed()
        }
        self._missing: set[str] = set()

    def lookup(self, code: str, item_type: str, *, sem: bool = False) -> float | None:
        raw = str(code or "").strip()
        if not raw:
            return None

        nc = normalize_seminf_code(raw)
        if is_seminf_regional_code(nc) or nc.endswith(".SEMINF"):
            row = self._closed_seminf.get(nc)
            if row:
                reg = (row.get("regional") or {}).get(self.uf) or {}
                price = float(
                    reg.get("semd" if sem else "comd")
                    or reg.get("sem" if sem else "com")
                    or (row.get("price_sem_desoneracao") if sem else row.get("price"))
                    or 0
                )
                return price if price > 0 else None
            self._missing.add(nc)
            return None

        digits = raw.replace(" ", "")
        if digits.startswith("0") and len(digits) > 1:
            key_variants = [digits, digits.lstrip("0")]
        else:
            key_variants = [digits.split(".")[0] if "." in digits else digits]

        stores: list[dict[str, Any]] = (
            [self._insumos_sinapi, self._closed_sinapi]
            if item_type == "insumo"
            else [self._closed_sinapi, self._insumos_sinapi]
        )

        for key in key_variants:
            for store in stores:
                row = store.get(key)
                if not row:
                    continue
                reg = (row.get("regional") or {}).get(self.uf) or {}
                price = float(
                    reg.get("semd" if sem else "comd")
                    or reg.get("sem" if sem else "com")
                    or (row.get("price_sem_desoneracao") if sem else row.get("price"))
                    or 0
                )
                if price > 0:
                    return price

        self._missing.add(raw)
        return None


def refresh_seminf_open_compositions(
    seminf_reference: str,
    *,
    sinapi_reference: str,
    seminf_price_reference: str | None = None,
    uf: str = "AM",
) -> tuple[dict[str, CompositionOpen], SeminfRefreshResult]:
    structure_ref = seminf_root_reference(seminf_reference)
    seminf_prices_ref = seminf_root_reference(seminf_price_reference or seminf_reference)

    store = PriceBankStore.for_reference(structure_ref)
    raw_open = store.load_open()
    if not raw_open:
        raise ValueError(
            f"Referência {structure_ref} não possui composições abertas — importe o lote completo primeiro."
        )

    resolver = _SeminfPriceResolver(
        sinapi_ref=sinapi_reference,
        seminf_ref=seminf_prices_ref,
        uf=uf,
    )

    updated: dict[str, CompositionOpen] = {}
    result = SeminfRefreshResult(
        reference=structure_ref,
        parent_reference=seminf_prices_ref,
        sinapi_reference=sinapi_reference,
        uf=uf.upper(),
    )

    for code, comp_data in raw_open.items():
        items_raw = comp_data.get("items") or []
        new_items: list[CompositionItem] = []
        comp_changed = False

        for item_data in items_raw:
            item_type = str(item_data.get("item_type") or "insumo")
            item_code = str(item_data.get("code") or "").strip()
            coef = float(item_data.get("coefficient") or 0)

            unit_com = resolver.lookup(item_code, item_type, sem=False)
            unit_sem = resolver.lookup(item_code, item_type, sem=True)

            old_com = float(item_data.get("unit_price") or 0)
            old_sem = float(item_data.get("unit_price_sem") or old_com)

            if unit_com is None:
                unit_com = old_com
                if unit_com <= 0:
                    result.items_missing_price += 1
            if unit_sem is None:
                unit_sem = old_sem if old_sem > 0 else unit_com

            partial_com = (
                round(coef * unit_com, 4) if coef and unit_com else float(item_data.get("partial_cost") or 0)
            )
            partial_sem = (
                round(coef * unit_sem, 4) if coef and unit_sem else float(item_data.get("partial_cost_sem") or partial_com)
            )

            if abs(unit_com - old_com) > 0.001 or abs(unit_sem - old_sem) > 0.001:
                comp_changed = True
                result.items_updated += 1

            new_items.append(
                CompositionItem(
                    item_type=item_type,
                    code=item_code,
                    description=str(item_data.get("description") or ""),
                    unit=str(item_data.get("unit") or ""),
                    coefficient=coef,
                    unit_price=unit_com,
                    partial_cost=partial_com,
                    unit_price_sem=unit_sem,
                    partial_cost_sem=partial_sem,
                    tp2=str(item_data.get("tp2") or "").strip(),
                )
            )

        total_com = round(sum(i.partial_cost for i in new_items), 4)
        total_sem = round(sum(i.partial_cost_sem for i in new_items), 4)

        if comp_changed or abs(total_com - float(comp_data.get("total_price") or 0)) > 0.01:
            result.compositions_updated += 1

        updated[code] = CompositionOpen(
            code=str(comp_data.get("code") or code),
            description=str(comp_data.get("description") or code),
            unit=str(comp_data.get("unit") or "un"),
            total_price=total_com,
            total_price_sem=total_sem,
            items=new_items,
        )

    if resolver._missing:
        sample = sorted(resolver._missing)[:8]
        result.warnings.append(
            f"{len(resolver._missing)} código(s) sem preço nas bases vinculadas (ex.: {', '.join(sample)})."
        )

    return updated, result


def _sync_closed_from_open(
    closed_rows: list[CompositionClosed],
    open_map: dict[str, CompositionOpen],
    *,
    uf: str,
) -> list[CompositionClosed]:
    """Atualiza preços sintéticos regionais a partir da CPU analítica recalculada."""
    uf = uf.upper()
    synced: list[CompositionClosed] = []
    for row in closed_rows:
        open_comp = open_map.get(row.code)
        if not open_comp:
            synced.append(row)
            continue
        regional = dict(row.regional or {})
        regional[uf] = {
            **(regional.get(uf) or {}),
            "comd": round(float(open_comp.total_price), 4),
            "semd": round(float(open_comp.total_price_sem or open_comp.total_price), 4),
        }
        synced.append(
            CompositionClosed(
                code=row.code,
                description=row.description,
                unit=row.unit,
                price=round(float(open_comp.total_price), 4),
                price_sem_desoneracao=round(
                    float(open_comp.total_price_sem or open_comp.total_price), 4
                ),
                regional=regional,
                tp2=row.tp2,
                grupo=row.grupo,
            )
        )
    return synced


def fork_seminf_price_base(
    source_reference: str,
    *,
    sinapi_reference: str,
    new_reference: str | None = None,
    uf: str = "AM",
    set_active: bool = False,
) -> SeminfRefreshResult:
    """
    Gera base do mês SINAPI (ex. fonte 04/2026 + SINAPI 05/2026 → BR-DP-SEMINF-2026-05).

    A base fonte (ex. abril) permanece intacta no histórico.
    """
    source_reference = seminf_root_reference(source_reference)
    slug = seminf_source_slug(source_reference)
    new_ref = seminf_root_reference(
        new_reference or infer_seminf_reference_from_sinapi(sinapi_reference, source_slug=slug)
    )

    if new_ref == source_reference:
        raise ValueError(
            f"A base destino ({new_ref}) coincide com a fonte — use SINAPI de outro mês "
            f"ou importe a pasta do período {new_ref.split('-')[-2]}/{new_ref.split('-')[-1]}."
        )

    validate_seminf_refresh_source(source_reference, new_ref, allow_backfill=True)
    is_backfill = False
    src_period = parse_seminf_reference_period(source_reference)
    tgt_period = parse_seminf_reference_period(new_ref)
    if src_period and tgt_period and _period_key(*src_period) >= _period_key(*tgt_period):
        is_backfill = True

    target_store = PriceBankStore.for_reference(new_ref)
    if target_store.manifest_path.is_file():
        existing = target_store.load_manifest()
        meta = (existing.metadata or {}) if existing else {}
        is_folder_import = meta.get("import_mode") == "bundle" and meta.get("generation") != "sinapi_refresh_fork"
        if is_folder_import:
            raise ValueError(
                f"{new_ref} já foi importada da pasta SEMINF. "
                "Exclua-a ou use outra base como fonte de estrutura."
            )

    source_store = PriceBankStore.for_reference(source_reference)
    source_manifest = source_store.load_manifest()
    if not source_manifest:
        raise ValueError(f"Referência fonte {source_reference} não encontrada.")

    if not source_store.load_open():
        raise ValueError(
            f"{source_reference} não possui CPUs abertas — importe o lote completo da pasta primeiro."
        )

    open_map, refresh_result = refresh_seminf_open_compositions(
        source_reference,
        sinapi_reference=sinapi_reference,
        seminf_price_reference=source_reference,
        uf=uf,
    )

    closed = [CompositionClosed(**row) for row in source_store.load_closed()]
    closed = _sync_closed_from_open(closed, open_map, uf=uf.upper())

    meta = dict(source_manifest.metadata or {})
    meta.update(
        {
            "generation": "sinapi_refresh_fork",
            "parent_reference": source_reference,
            "structure_reference": source_reference,
            "sinapi_reference": sinapi_reference,
            "forked_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    PriceBankStore.for_reference(new_ref).save_bank(
        source=source_manifest.source,
        reference=new_ref,
        closed=closed,
        open_compositions=open_map,
        insumos=[],
        uf=uf.upper(),
        desonerado=source_manifest.desonerado,
        metadata=meta,
        set_active=set_active,
    )

    refresh_result.reference = new_ref
    refresh_result.parent_reference = source_reference
    lead_warnings: list[str] = [
        f"Nova base {new_ref} criada — {source_reference} preservada no histórico.",
    ]
    if is_backfill and src_period and tgt_period:
        lead_warnings.append(
            f"Estrutura reutilizada de {src_period[1]:02d}/{src_period[0]} (mês posterior ao destino "
            f"{tgt_period[1]:02d}/{tgt_period[0]}) — preços do SINAPI {sinapi_reference}."
        )
    refresh_result.warnings = lead_warnings + refresh_result.warnings
    return refresh_result


def apply_seminf_open_refresh(
    seminf_reference: str,
    *,
    sinapi_reference: str,
    uf: str = "AM",
    set_active: bool = False,
) -> SeminfRefreshResult:
    """Gera nova base do mês SINAPI sem alterar a fonte."""
    return fork_seminf_price_base(
        seminf_reference,
        sinapi_reference=sinapi_reference,
        uf=uf,
        set_active=set_active,
    )
