"""Monta sessão Budget a partir do plano OrçaFacil (códigos + memória detalhada)."""

from __future__ import annotations

from typing import Any

from pricing.budget.budget_session import SESSION_STORE
from pricing.budget.budget_structure import add_etapa, add_service_to_group, add_subetapa
from pricing.budget.memory_generator import _apply_memory_to_service
from pricing.budget.orca_facil.base_index import ModelPriceBaseIndex
from pricing.budget.ppd_template import create_empty_ppd_metadata
from pricing.models.price_item import PriceItem


def _qty(val: Any) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def build_session_from_plan(
    *,
    plan: dict[str, Any],
    project_info: dict[str, Any],
    base_index: ModelPriceBaseIndex,
    obra_type: str = "ED",
    title: str | None = None,
) -> dict[str, Any]:
    info = project_info or {}
    ot = str(info.get("obra_type") or obra_type or "ED").upper()
    meta = create_empty_ppd_metadata(
        projeto=str(info.get("projeto") or "") or "OrçaFacil",
        objeto=str(info.get("objeto") or info.get("projeto") or ""),
        local=str(info.get("local") or info.get("endereco") or ""),
        orcamento=str(info.get("orcamento") or ""),
        obra_type=ot if ot else "ED",
    )
    if info.get("processo"):
        meta.processo = str(info["processo"])
    if info.get("endereco") and not meta.local:
        meta.local = str(info["endereco"])
    meta.base_preco = base_index.sheet_name or "MODELO"

    roots: list = []
    warnings: list[str] = []
    resolved = 0
    needs_match = 0

    for stage in plan.get("stages") or []:
        stage_name = str(stage.get("name") or "").strip()
        if not stage_name:
            continue
        etapa = add_etapa(roots, stage_name, meta)

        def _add_items(container, items: list[dict[str, Any]]) -> None:
            nonlocal resolved, needs_match
            for raw in items or []:
                code = str(raw.get("code") or "").strip() or None
                desc = str(raw.get("description") or "").strip()
                unit = str(raw.get("unit") or "").strip()
                qty = _qty(raw.get("qty"))
                memory = str(raw.get("memory") or "").strip()
                flag_match = bool(raw.get("needs_match"))

                row = base_index.get_by_code(code) if code else None
                if row is None and desc:
                    hits = base_index.search_base(desc, top_k=1)
                    if hits and hits[0][1] >= 4.0:
                        row = hits[0][0]
                        code = row.code

                if row is not None:
                    price_data = row.as_price_data()
                    price = PriceItem(
                        code=price_data["code"],
                        description=price_data["description"],
                        unit=unit or price_data["unit"],
                        price=float(price_data["price"]),
                        source=str(price_data.get("source") or "seminf"),
                        metadata=dict(price_data.get("metadata") or {}),
                    )
                    resolved += 1
                else:
                    price = PriceItem(
                        code=code or "",
                        description=desc or "Serviço sem match",
                        unit=unit or "UN",
                        price=0.0,
                        source="pending",
                        metadata={"needs_match": True},
                    )
                    needs_match += 1
                    flag_match = True
                    warnings.append(f"Sem preço na base: {code or desc}")

                svc = add_service_to_group(
                    container,
                    price,
                    meta,
                    quantity=qty if qty > 0 else 1.0,
                    unit_hint=unit or None,
                )
                if not memory:
                    memory = (
                        f"{svc.name}\n"
                        f"{raw.get('qty_basis') or 'Quantitativo a revisar'}\n"
                        f"Qtd = {svc.quantity:g} {svc.unit}\n"
                        f"Total = {svc.quantity:g} {svc.unit}"
                    )
                _apply_memory_to_service(svc, memory)
                if flag_match:
                    svc.metadata["needs_match"] = True

        _add_items(etapa, list(stage.get("items") or []))

        for sub in stage.get("subetapas") or []:
            sub_name = str(sub.get("name") or "").strip()
            if not sub_name:
                continue
            subetapa = add_subetapa(roots, etapa.code, sub_name, meta)
            _add_items(subetapa, list(sub.get("items") or []))

        etapa.recompute_total()

    session_title = title or meta.orcamento or meta.objeto or meta.projeto or "OrçaFacil"
    session = SESSION_STORE.create(
        roots=roots,
        title=session_title,
        intent={"orca_facil": True, "project": meta.to_dict()},
        project=meta,
        source_priority=["seminf", "sinapi", "sicro", "orse"],
    )
    return {
        "session": session.to_dict(),
        "session_id": session.id,
        "stats": {
            "etapas": len(roots),
            "resolved": resolved,
            "needs_match": needs_match,
        },
        "warnings": warnings,
    }
