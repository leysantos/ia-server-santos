"""L10 — Motor de classificação NBR 9452 / DNIT 010 para OAE e tipologías afins.

Converte severidade de patologias + status de elementos em notas DNIT (1–5)
e classificação global da obra (pior nota governa, com justificativa).
"""

from __future__ import annotations

from typing import Any

# Nota DNIT (Anexo C / prática de inspeção OAE): 5=excelente … 1=crítico
DNIT_NOTE_LABELS: dict[int, str] = {
    5: "Excelente",
    4: "Bom",
    3: "Regular",
    2: "Ruim",
    1: "Crítico",
}

SEVERITY_TO_DNIT: dict[str, int] = {
    "crítica": 1,
    "critica": 1,
    "critical": 1,
    "alta": 2,
    "high": 2,
    "média": 3,
    "media": 3,
    "medium": 3,
    "baixa": 4,
    "low": 4,
    "leve": 4,
    "info": 5,
    "informativa": 5,
}

STATUS_TO_DNIT: dict[str, int] = {
    "crítico": 1,
    "critico": 1,
    "degradado": 2,
    "observação": 3,
    "observacao": 3,
    "íntegro": 5,
    "integro": 5,
    "não_inspecionado": 0,  # não entra no min global
    "nao_inspecionado": 0,
}


def severity_to_dnit_note(severity: str | None) -> int:
    s = (severity or "").strip().lower()
    for key, note in SEVERITY_TO_DNIT.items():
        if key in s:
            return note
    return 3


def status_to_dnit_note(status: str | None) -> int | None:
    s = (status or "").strip().lower()
    note = STATUS_TO_DNIT.get(s)
    if note is None:
        for key, n in STATUS_TO_DNIT.items():
            if key in s:
                return n if n else None
        return None
    return note if note else None


def classification_prompt_block() -> str:
    return """
════════════════════════════════════════
CLASSIFICAÇÃO NBR 9452 / DNIT (L10 — OBRIGATÓRIO)
════════════════════════════════════════
Preencha `classification` com:
- inspection_type: rotineira | especial | extraordinária (NBR 9452)
- standard_refs: ["NBR 9452", "DNIT 010/2004-PRO"] (ou aplicáveis)
- global_dnit_note: inteiro 1–5 (1=crítico … 5=excelente)
- global_label: rótulo correspondente
- governing_element_id: elemento que define a nota global (pior condição)
- governing_pathology_codes: códigos das patologias que justificam a nota
- rationale: 2–4 frases técnicas justificando a classificação
- element_notes: [{element_id, dnit_note, label, justification}]

Regra: a nota global é a MENOR nota entre elementos com anomalia relevante
(segurança estrutural e transitabilidade prevalecem sobre estética).
""".strip()


def apply_classification(
    content: dict[str, Any],
    *,
    slug: str | None = None,
) -> dict[str, Any]:
    """
    Calcula/normaliza notas DNIT por elemento e classificação global.
    Atualiza element_inventory[].dnit_note e content['classification'].
    """
    out = dict(content or {})
    inventory = list(out.get("element_inventory") or [])
    pathologies = [p for p in (out.get("pathologies") or []) if isinstance(p, dict)]

    # Notas por patologia → elemento
    path_notes_by_elem: dict[str, list[tuple[int, str]]] = {}
    for p in pathologies:
        eid = str(p.get("element_id") or "").strip()
        if not eid:
            continue
        note = severity_to_dnit_note(str(p.get("severity") or ""))
        code = str(p.get("code") or p.get("codigo") or "")
        path_notes_by_elem.setdefault(eid, []).append((note, code))

    element_notes: list[dict[str, Any]] = []
    worst_note = 5
    worst_eid = ""
    governing_codes: list[str] = []

    for e in inventory:
        if not isinstance(e, dict):
            continue
        eid = str(e.get("element_id") or "")
        notes_from_paths = path_notes_by_elem.get(eid) or []
        path_min = min((n for n, _ in notes_from_paths), default=None)
        status_note = status_to_dnit_note(str(e.get("status") or ""))

        # Existente do Gemini
        existing = e.get("dnit_note")
        try:
            existing_i = int(existing) if existing is not None else None
        except (TypeError, ValueError):
            existing_i = None
        if existing_i is not None and not (1 <= existing_i <= 5):
            existing_i = None

        candidates = [c for c in (path_min, status_note, existing_i) if c is not None and c >= 1]
        if not candidates:
            # sem anomalia registrada → íntegro / não pontua como governante
            if str(e.get("status") or "").lower() in ("íntegro", "integro"):
                e["dnit_note"] = 5
            continue

        final = min(candidates)
        e["dnit_note"] = final
        label = DNIT_NOTE_LABELS.get(final, "Regular")
        codes = [c for _, c in notes_from_paths if c]
        just = e.get("condition_note") or ""
        if codes and not just:
            just = f"Patologias: {', '.join(codes)}"
        element_notes.append(
            {
                "element_id": eid,
                "name": e.get("name") or eid,
                "dnit_note": final,
                "label": label,
                "justification": just,
                "pathology_codes": codes,
            }
        )
        if final < worst_note:
            worst_note = final
            worst_eid = eid
            governing_codes = codes

    # Se não há elementos notados, derivar do pior pathology global
    if not element_notes and pathologies:
        worst_p = min(
            pathologies,
            key=lambda p: severity_to_dnit_note(str(p.get("severity") or "")),
        )
        worst_note = severity_to_dnit_note(str(worst_p.get("severity") or ""))
        governing_codes = [str(worst_p.get("code") or worst_p.get("codigo") or "")]
        worst_eid = str(worst_p.get("element_id") or "")

    existing_cls = out.get("classification") if isinstance(out.get("classification"), dict) else {}
    inspection_type = str(
        existing_cls.get("inspection_type")
        or existing_cls.get("tipo_inspecao")
        or "especial"
    ).lower()
    if inspection_type not in ("rotineira", "especial", "extraordinária", "extraordinaria"):
        inspection_type = "especial"
    if inspection_type == "extraordinaria":
        inspection_type = "extraordinária"

    standard_refs = existing_cls.get("standard_refs") or existing_cls.get("normas")
    if not isinstance(standard_refs, list) or not standard_refs:
        if (slug or "").lower() in ("pontes", "viadutos"):
            standard_refs = ["NBR 9452", "DNIT 010/2004-PRO"]
        else:
            standard_refs = ["NBR 9452", "Boas práticas de inspeção"]

    rationale = str(existing_cls.get("rationale") or existing_cls.get("justificativa") or "").strip()
    if not rationale:
        label = DNIT_NOTE_LABELS.get(worst_note, "Regular")
        if worst_eid:
            rationale = (
                f"Classificação global {worst_note} ({label}) determinada pelo elemento "
                f"'{worst_eid}', conforme matriz de severidade NBR 9452 / escala DNIT. "
            )
            if governing_codes:
                rationale += f"Patologias governantes: {', '.join(c for c in governing_codes if c)}."
        else:
            rationale = (
                f"Classificação global {worst_note} ({DNIT_NOTE_LABELS.get(worst_note, '')}) "
                "derivada das patologias registradas na vistoria."
            )

    # Preferir nota do Gemini só se for mais conservadora (menor);
    # o elemento governante SEMPRE é o de pior nota no inventário/element_notes.
    try:
        gemini_note = (
            int(existing_cls.get("global_dnit_note"))
            if existing_cls.get("global_dnit_note") is not None
            else None
        )
    except (TypeError, ValueError):
        gemini_note = None
    if gemini_note is not None and 1 <= gemini_note <= 5 and gemini_note < worst_note:
        worst_note = gemini_note

    # Governante = argmin das notas; empate → prioridade estrutural (longarina > tabuleiro…)
    _GOVERN_PRIORITY = {
        "sup_longarina": 0,
        "sup_transversina": 1,
        "mes_apoio": 2,
        "mes_pilar": 3,
        "inf_fundacao": 4,
        "inf_encontro": 5,
        "inf_margem": 6,
        "sup_tabuleiro": 10,
        "sup_laje": 11,
        "acs_junta": 12,
        "acs_pavimento": 13,
        "acs_drenagem": 14,
        "acs_guarda": 15,
    }
    if element_notes:
        best = min(
            element_notes,
            key=lambda n: (
                int(n.get("dnit_note") or 99),
                _GOVERN_PRIORITY.get(str(n.get("element_id") or ""), 50),
                str(n.get("element_id") or ""),
            ),
        )
        worst_eid = str(best.get("element_id") or worst_eid)
        governing_codes = list(best.get("pathology_codes") or governing_codes)
        elem_note = int(best.get("dnit_note") or worst_note)
        worst_note = min(worst_note, elem_note)

    # Rationale alinhada ao governante efetivo
    label = DNIT_NOTE_LABELS.get(worst_note, "Regular")
    if worst_eid:
        rationale = (
            f"Classificação global {worst_note} ({label}) determinada pelo elemento "
            f"'{worst_eid}' (pior condição na matriz elemento×anomalia), conforme "
            f"NBR 9452 / escala DNIT. "
        )
        if governing_codes:
            rationale += (
                f"Patologias governantes: {', '.join(c for c in governing_codes if c)}."
            )
        prev = str(existing_cls.get("rationale") or "")
        if "interdição" in prev.lower() or "interdicao" in prev.lower():
            if prev not in rationale:
                rationale = f"{rationale} {prev}".strip()
    elif not rationale:
        rationale = (
            f"Classificação global {worst_note} ({label}) "
            "derivada das patologias registradas na vistoria."
        )
    out["classification"] = {
        "inspection_type": inspection_type,
        "standard_refs": standard_refs,
        "global_dnit_note": worst_note,
        "global_label": DNIT_NOTE_LABELS.get(worst_note, "Regular"),
        "governing_element_id": worst_eid or "",
        "governing_pathology_codes": [c for c in governing_codes if c],
        "rationale": rationale,
        "element_notes": element_notes
        or list(existing_cls.get("element_notes") or []),
    }
    out["element_inventory"] = inventory
    return out


def classification_summary_table(classification: dict[str, Any]) -> dict[str, Any]:
    note = classification.get("global_dnit_note")
    return {
        "caption": "Classificação estrutural (NBR 9452 / DNIT)",
        "headers": ["Campo", "Valor"],
        "rows": [
            ["Tipo de inspeção (NBR 9452)", classification.get("inspection_type") or "—"],
            ["Normas de referência", ", ".join(classification.get("standard_refs") or []) or "—"],
            ["Nota DNIT global", f"{note} — {classification.get('global_label') or ''}"],
            ["Elemento governante", classification.get("governing_element_id") or "—"],
            [
                "Patologias governantes",
                ", ".join(classification.get("governing_pathology_codes") or []) or "—",
            ],
            ["Justificativa", (classification.get("rationale") or "—")[:400]],
        ],
    }


def classification_elements_table(classification: dict[str, Any]) -> dict[str, Any]:
    notes = classification.get("element_notes") or []
    return {
        "caption": "Notas DNIT por elemento",
        "headers": ["Elemento", "ID", "Nota", "Rótulo", "Patologias", "Justificativa"],
        "rows": [
            [
                n.get("name") or "—",
                n.get("element_id") or "—",
                str(n.get("dnit_note") if n.get("dnit_note") is not None else "—"),
                n.get("label") or "—",
                ", ".join(n.get("pathology_codes") or []) or "—",
                (n.get("justification") or "—")[:160],
            ]
            for n in notes
            if isinstance(n, dict)
        ]
        or [["—", "—", "—", "—", "—", "Sem elementos classificados"]],
    }
