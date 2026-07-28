"""L13 — Ato de interdição / restrição de uso da obra.

Gerado deterministicamente a partir da classificação DNIT e patologias críticas.
Capítulo tipado para protocolo administrativo e perícia.
"""

from __future__ import annotations

from typing import Any


def apply_interdiction(content: dict[str, Any]) -> dict[str, Any]:
    """
    Preenche `interdiction` e injeta capítulo quando a nota DNIT ≤ 2
    ou houver patologia crítica.
    """
    out = dict(content or {})
    cls = out.get("classification") if isinstance(out.get("classification"), dict) else {}
    pathologies = [p for p in (out.get("pathologies") or []) if isinstance(p, dict)]

    try:
        note = int(cls.get("global_dnit_note")) if cls.get("global_dnit_note") is not None else None
    except (TypeError, ValueError):
        note = None

    critical_codes = [
        str(p.get("code") or p.get("codigo") or "")
        for p in pathologies
        if "crít" in str(p.get("severity") or "").lower() or "crit" in str(p.get("severity") or "").lower()
    ]
    critical_codes = [c for c in critical_codes if c]

    existing = out.get("interdiction") if isinstance(out.get("interdiction"), dict) else {}

    # Decisão
    if note is not None and note <= 1:
        restriction = "total"
        urgency = "imediata"
        action = "INTERDIÇÃO TOTAL E IMEDIATA ao tráfego veicular e de pedestres"
    elif note is not None and note == 2:
        restriction = "parcial"
        urgency = "urgente"
        action = "RESTRIÇÃO PARCIAL DE USO (faixa/carga/velocidade) até reabilitação"
    elif critical_codes:
        restriction = "total"
        urgency = "imediata"
        action = "INTERDIÇÃO TOTAL recomendada diante de patologia(s) crítica(s)"
    else:
        # Sem interdição formal — não injeta capítulo
        if existing.get("required"):
            out["interdiction"] = existing
        else:
            out["interdiction"] = {
                "required": False,
                "restriction_type": "nenhuma",
                "urgency": "rotina",
                "action_summary": "Sem ato de interdição — monitoramento e manutenção programada",
                "authority": existing.get("authority") or "Órgão gestor da via / solicitante",
                "conditions_for_release": [],
                "signage": [],
                "pathology_refs": [],
                "dnit_note": note,
            }
        return out

    governing = str(cls.get("governing_element_id") or existing.get("governing_element_id") or "")
    gov_paths = list(cls.get("governing_pathology_codes") or critical_codes)

    authority = str(
        existing.get("authority")
        or "Órgão gestor da via / solicitante do laudo (ex.: SEMINF, DER, DNIT)"
    )
    legal_basis = list(
        existing.get("legal_basis")
        or [
            "NBR 9452 — Inspeção de pontes, viadutos e passarelas de concreto",
            "DNIT 010/2004-PRO — Inspeções em pontes e viadutos",
            "Dever de cautela do responsável técnico perante risco à vida e ao patrimônio",
        ]
    )

    if restriction == "total":
        signage = existing.get("signage") or [
            "Bloqueio físico dos acessos (barreiras rígidas tipo New Jersey ou equivalente)",
            "Sinalização diurna e noturna de via interditada",
            "Desvio / itinerário alternativo comunicado ao órgão de trânsito",
        ]
        release = existing.get("conditions_for_release") or [
            "Campanha de ensaios instrumentados prioritários concluída e laudo complementar emitido",
            "Projeto de contenção/reforço aprovado pelo responsável técnico",
            "Execução das fases emergenciais de segurança (escoramento/contenção de margem, conforme plano)",
            "Nova inspeção com nota DNIT ≥ 3 (Regular) ou liberação condicionada documentada",
        ]
        deadline = existing.get("deadline") or "Imediato (0–24 h para bloqueio físico)"
    else:
        signage = existing.get("signage") or [
            "Sinalização de restrição de carga e/ou velocidade",
            "Cones/barreiras delimitando faixa interditada, se aplicável",
        ]
        release = existing.get("conditions_for_release") or [
            "Eliminação das patologias de nota 2 no elemento governante",
            "Reavaliação formal com atualização da classificação DNIT",
        ]
        deadline = existing.get("deadline") or "Até 7 dias para implantação da restrição"

    interdiction = {
        "required": True,
        "restriction_type": restriction,
        "urgency": urgency,
        "action_summary": action,
        "authority": authority,
        "legal_basis": legal_basis,
        "deadline": deadline,
        "signage": signage,
        "conditions_for_release": release,
        "governing_element_id": governing,
        "pathology_refs": gov_paths or critical_codes,
        "dnit_note": note,
        "rationale": str(
            existing.get("rationale")
            or cls.get("rationale")
            or "Classificação DNIT e patologias críticas fundamentam restrição de uso."
        ),
    }
    out["interdiction"] = interdiction
    out = _inject_interdiction_chapter(out, interdiction)
    return out


def _inject_interdiction_chapter(
    content: dict[str, Any],
    interdiction: dict[str, Any],
) -> dict[str, Any]:
    out = dict(content)
    chapters = list(out.get("chapters") or [])
    by_id = {
        str(c.get("id") or "").lower(): i
        for i, c in enumerate(chapters)
        if isinstance(c, dict)
    }

    paras = [
        (
            f"Com fundamento na classificação DNIT nota {interdiction.get('dnit_note')} "
            f"({content.get('classification', {}).get('global_label') or '—'}) e nas patologias "
            f"{', '.join(interdiction.get('pathology_refs') or []) or 'críticas identificadas'}, "
            f"este laudo recomenda: {interdiction.get('action_summary')}."
        ),
        f"Urgência: {interdiction.get('urgency')}. Prazo para implantação: {interdiction.get('deadline')}.",
        f"Autoridade competente para execução do ato: {interdiction.get('authority')}.",
        "Bases normativas / dever de cautela: " + "; ".join(interdiction.get("legal_basis") or []) + ".",
        "Condições para liberação / reassentamento do uso: "
        + "; ".join(interdiction.get("conditions_for_release") or [])
        + ".",
    ]
    table = {
        "caption": "Ato de interdição / restrição de uso",
        "headers": ["Campo", "Valor"],
        "rows": [
            ["Tipo de restrição", str(interdiction.get("restriction_type") or "—")],
            ["Ação recomendada", str(interdiction.get("action_summary") or "—")],
            ["Urgência", str(interdiction.get("urgency") or "—")],
            ["Prazo", str(interdiction.get("deadline") or "—")],
            ["Autoridade", str(interdiction.get("authority") or "—")],
            ["Elemento governante", str(interdiction.get("governing_element_id") or "—")],
            ["Patologias de referência", ", ".join(interdiction.get("pathology_refs") or []) or "—"],
            ["Sinalização / bloqueio", "; ".join(interdiction.get("signage") or []) or "—"],
            [
                "Condições de liberação",
                "; ".join(interdiction.get("conditions_for_release") or []) or "—",
            ],
        ],
    }
    payload = {
        "id": "interdicao",
        "title": "Ato de interdição e restrição de uso",
        "paragraphs": paras,
        "tables": [table],
    }
    if "interdicao" in by_id:
        chapters[by_id["interdicao"]] = payload
    else:
        # Inserir após classificacao_dnit se existir
        insert_at = len(chapters)
        for i, c in enumerate(chapters):
            if str(c.get("id") or "").lower() == "classificacao_dnit":
                insert_at = i + 1
                break
        chapters.insert(insert_at, payload)

    out["chapters"] = chapters
    return out


def interdiction_prompt_block() -> str:
    return """
════════════════════════════════════════
ATO DE INTERDIÇÃO (L13 — QUANDO APLICÁVEL)
════════════════════════════════════════
Se a nota DNIT global for 1 ou 2, ou houver patologia crítica de segurança,
preencha `interdiction` com:
{
  "required": true,
  "restriction_type": "total|parcial",
  "urgency": "imediata|urgente",
  "action_summary": "…",
  "authority": "órgão gestor",
  "deadline": "…",
  "signage": ["…"],
  "conditions_for_release": ["…"],
  "pathology_refs": ["P01"],
  "rationale": "…"
}
Se a estrutura estiver em condição aceitável (nota ≥ 3 sem crítica de segurança),
use required=false.
""".strip()
