"""Orquestra L10–L15: classificação, inventário, metrologia, interdição e RAG normativo.

Aplicado após a resposta do Gemini e em prepare_report_content (export/GET).
"""

from __future__ import annotations

from typing import Any

from core.inspection_report.classification import (
    apply_classification,
    classification_elements_table,
    classification_prompt_block,
    classification_summary_table,
)
from core.inspection_report.elements import (
    element_catalog_prompt_block,
    element_inventory_table,
    ensure_element_inventory,
)
from core.inspection_report.interdiction import (
    apply_interdiction,
    interdiction_prompt_block,
)
from core.inspection_report.metrology import (
    apply_metrology,
    metrology_prompt_block,
    metrology_table,
)
from core.inspection_report.normative_rag import (
    apply_normative_citations,
    normative_prompt_block,
)
from core.inspection_report.assay_results import apply_assay_results_to_content
from core.inspection_report.editorial_postprocess import apply_editorial_postprocess
from core.inspection_report.protocol_order import reorder_chapters_for_protocol


def build_engineering_prompt_block(slug: str | None) -> str:
    """Blocos L10–L15 injetados no system prompt do Gemini."""
    return "\n\n".join(
        [
            classification_prompt_block(),
            element_catalog_prompt_block(slug),
            metrology_prompt_block(),
            interdiction_prompt_block(),
            normative_prompt_block(),
        ]
    )


def apply_engineering_enrichment(
    content: dict[str, Any],
    *,
    slug: str | None = None,
    normative: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Pipeline determinístico:
    1. Metrologia tipada (L12)
    2. Inventário de elementos (L11)
    3. Classificação NBR 9452 / DNIT (L10)
    4. Ato de interdição (L13)
    5. Citações normativas rastreáveis (L15)
    6. Resultados medidos de ensaios (L16)
    7. Capítulos oficiais + ordem de protocolo
    8. Pós-processamento editorial institucional (L20)
    """
    out = dict(content or {})
    out = apply_metrology(out)
    out = ensure_element_inventory(out, slug=slug)
    out = apply_classification(out, slug=slug)
    out = _inject_engineering_chapters(out)
    out = apply_interdiction(out)
    out = apply_normative_citations(out, normative=normative, slug=slug)
    out = apply_assay_results_to_content(out)
    out["chapters"] = reorder_chapters_for_protocol(list(out.get("chapters") or []))
    out = apply_editorial_postprocess(out)
    return out


def _inject_engineering_chapters(content: dict[str, Any]) -> dict[str, Any]:
    out = dict(content)
    chapters = list(out.get("chapters") or [])
    by_id = {
        str(c.get("id") or "").lower(): i
        for i, c in enumerate(chapters)
        if isinstance(c, dict)
    }

    cls = out.get("classification") if isinstance(out.get("classification"), dict) else {}
    inventory = out.get("element_inventory") if isinstance(out.get("element_inventory"), list) else []
    pathologies = out.get("pathologies") if isinstance(out.get("pathologies"), list) else []

    def _upsert(cid: str, title: str, paragraphs: list[str], tables: list[dict[str, Any]]) -> None:
        payload = {
            "id": cid,
            "title": title,
            "paragraphs": paragraphs,
            "tables": tables,
        }
        if cid in by_id:
            chapters[by_id[cid]] = payload
        else:
            chapters.append(payload)
            by_id[cid] = len(chapters) - 1

    if inventory:
        inspected = [
            e
            for e in inventory
            if isinstance(e, dict)
            and (
                e.get("pathology_refs")
                or e.get("photo_refs")
                or str(e.get("status") or "")
                not in ("não_inspecionado", "nao_inspecionado")
            )
        ]
        n_crit = sum(1 for e in inspected if str(e.get("status") or "").startswith("crít"))
        paras = [
            (
                f"Inventário com {len(inventory)} elemento(s) do catálogo da tipología; "
                f"{len(inspected)} com observação ou vínculo a patologia/foto"
                + (f"; {n_crit} em status crítico" if n_crit else "")
                + "."
            ),
            "Cada patologia e foto deve referenciar um element_id do inventário.",
        ]
        _upsert(
            "inventario_elementos",
            "Inventário estruturado de elementos",
            paras,
            [element_inventory_table(inventory)],
        )

    metro_tbl = metrology_table(pathologies)
    if metro_tbl.get("rows") and not (
        len(metro_tbl["rows"]) == 1 and metro_tbl["rows"][0][0] == "—"
    ):
        _upsert(
            "metrologia",
            "Campos metrológicos tipados",
            [
                "Medidas tipadas vinculadas às patologias. Valores com método "
                "«estimated» ou «visual» são estimativas de campo — não substituem "
                "ensaio instrumentado. Método «measured»/«instrumented» somente com "
                "medição ou ensaio documentado."
            ],
            [metro_tbl],
        )

    if cls:
        note = cls.get("global_dnit_note")
        label = cls.get("global_label") or ""
        paras = [
            (
                f"Tipo de inspeção (NBR 9452): {cls.get('inspection_type') or '—'}. "
                f"Normas: {', '.join(cls.get('standard_refs') or []) or '—'}."
            ),
            (
                f"Nota DNIT global: {note} ({label}). "
                f"Elemento governante (pior condição): {cls.get('governing_element_id') or '—'}. "
                f"Patologias governantes: "
                f"{', '.join(cls.get('governing_pathology_codes') or []) or '—'}."
            ),
            str(cls.get("rationale") or ""),
            (
                "A nota global é a menor nota entre os elementos com anomalia relevante "
                "(segurança estrutural e transitabilidade prevalecem sobre estética)."
            ),
        ]
        _upsert(
            "classificacao_dnit",
            "Classificação e parecer técnico (NBR 9452 / DNIT)",
            [p for p in paras if p],
            [
                classification_summary_table(cls),
                classification_elements_table(cls),
            ],
        )

    out["chapters"] = chapters
    return out
