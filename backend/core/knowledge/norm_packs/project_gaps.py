"""Gap analysis agregado para projetos / wizard de entrega."""

from __future__ import annotations

from typing import Any

from core.knowledge.disciplines import normalize_slug
from core.knowledge.norm_packs.presets import NORM_PACKS, get_norm_pack
from core.knowledge.norm_packs.service import NormPackService

# Slug de disciplina (agente) → pacote normativo
DISCIPLINE_SLUG_TO_PACK: dict[str, str] = {
    "arquitetura": "disc_arquitetura",
    "estruturas": "disc_estruturas",
    "estrutural": "disc_estruturas",
    "hidrossanitario": "disc_hidrossanitario",
    "hidraulica": "disc_hidrossanitario",
    "drenagem": "disc_drenagem",
    "eletrica": "disc_eletrica",
    "telecom": "disc_telecom",
    "incendio": "disc_incendio",
    "geotecnia": "disc_geotecnia",
    "transportes": "disc_transportes",
    "infraestrutura": "disc_infraestrutura",
    "saneamento": "disc_saneamento",
    "topografia": "disc_topografia",
}

ALWAYS_INCLUDE_PACKS = ("documentacao_projetos",)


def resolve_pack_ids_for_disciplines(disciplines: list[str], *, include_documentacao: bool = True) -> list[str]:
    """Pacotes NBR relevantes para as disciplinas detectadas no projeto."""
    pack_ids: list[str] = []
    seen: set[str] = set()

    if include_documentacao:
        for pid in ALWAYS_INCLUDE_PACKS:
            if pid not in seen:
                seen.add(pid)
                pack_ids.append(pid)

    for raw in disciplines:
        slug = normalize_slug(raw or "")
        pack_id = DISCIPLINE_SLUG_TO_PACK.get(slug)
        if pack_id and pack_id not in seen:
            seen.add(pack_id)
            pack_ids.append(pack_id)

    return pack_ids


def compute_project_norm_gaps(
    disciplines: list[str],
    *,
    include_documentacao: bool = True,
    critical_only: bool = False,
) -> dict[str, Any]:
    """
    Consolida pendências (comprar PDF / indexar) para disciplinas do projeto.
    Usado no Wizard de Entrega e alertas globais.
    """
    svc = NormPackService()
    pack_ids = resolve_pack_ids_for_disciplines(disciplines, include_documentacao=include_documentacao)

    pending_map: dict[str, dict[str, Any]] = {}
    packs_checked: list[dict[str, Any]] = []

    for pack_id in pack_ids:
        try:
            pack = get_norm_pack(pack_id)
            analysis = svc.analyze_pack(pack_id)
        except ValueError:
            continue

        packs_checked.append(
            {
                "pack_id": pack_id,
                "pack_label": pack.label,
                "coverage_pct": analysis["summary"]["coverage_pct"],
                "critical_missing": analysis["summary"]["critical_missing"],
            }
        )

        for item in analysis["items"]:
            if item["status"] == "indexed":
                continue
            if critical_only and not item.get("critical"):
                continue

            code = item["nbr_code"]
            existing = pending_map.get(code)
            priority = 0 if item["status"] == "missing" else 1
            if existing and existing.get("_priority", 9) <= priority:
                continue

            action = (
                "Adquirir PDF oficial na ABNT e fazer upload em Importações"
                if item["status"] == "missing"
                else "PDF presente — indexar em Pacotes NBR"
            )
            pending_map[code] = {
                "nbr_code": code,
                "title": item.get("title", ""),
                "status": item["status"],
                "critical": bool(item.get("critical")),
                "pack_id": pack_id,
                "pack_label": pack.label,
                "discipline": item.get("discipline", ""),
                "legal_source": item.get("legal_source"),
                "action": action,
                "_priority": priority,
            }

    pending_items = sorted(
        pending_map.values(),
        key=lambda x: (0 if x["critical"] else 1, 0 if x["status"] == "missing" else 1, x["nbr_code"]),
    )
    for row in pending_items:
        row.pop("_priority", None)

    critical_missing = [p for p in pending_items if p["critical"] and p["status"] == "missing"]
    critical_not_indexed = [p for p in pending_items if p["critical"] and p["status"] == "not_indexed"]
    missing_count = sum(1 for p in pending_items if p["status"] == "missing")
    not_indexed_count = sum(1 for p in pending_items if p["status"] == "not_indexed")

    has_critical_gaps = bool(critical_missing or critical_not_indexed)

    if critical_missing:
        summary_message = (
            f"{len(critical_missing)} NBR(s) crítica(s) sem PDF licenciado — "
            "carimbo e RAG normativo podem ficar incompletos."
        )
    elif critical_not_indexed:
        summary_message = (
            f"{len(critical_not_indexed)} NBR(s) crítica(s) aguardando indexação no FAISS."
        )
    elif pending_items:
        summary_message = f"{len(pending_items)} pendência(s) normativas (não críticas)."
    else:
        summary_message = "Acervo normativo do pacote está completo para as disciplinas desta entrega."

    return {
        "has_critical_gaps": has_critical_gaps,
        "has_any_gaps": bool(pending_items),
        "critical_missing_count": len(critical_missing),
        "critical_not_indexed_count": len(critical_not_indexed),
        "missing_purchase_count": missing_count,
        "not_indexed_count": not_indexed_count,
        "pending_total": len(pending_items),
        "packs_checked": packs_checked,
        "disciplines_resolved": disciplines,
        "pack_ids": pack_ids,
        "pending_items": pending_items,
        "summary_message": summary_message,
        "settings_path": "/settings/norm-packs",
    }


def disciplines_from_package_items(
    items: list[Any],
    *,
    project_discipline: str | None = None,
    selected_only: bool = True,
) -> list[str]:
    """Extrai disciplinas dos itens do pacote de entrega."""
    discs: list[str] = []
    if project_discipline:
        discs.append(project_discipline)

    for item in items:
        if selected_only and not getattr(item, "selected", True):
            continue
        disc = getattr(item, "disciplina", None)
        if disc:
            discs.append(str(disc))

    # dedupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for d in discs:
        key = normalize_slug(d)
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out
