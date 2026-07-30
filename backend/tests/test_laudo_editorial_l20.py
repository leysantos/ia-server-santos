"""L20 — testes do pós-processamento editorial institucional."""

from __future__ import annotations

from core.inspection_report.editorial_postprocess import (
    apply_editorial_postprocess,
    editorial_checklist,
    sanitize_flourish_text,
    standardize_terms,
)
from core.inspection_report.engineering_enrichment import apply_engineering_enrichment


def test_sanitize_flourish():
    raw = "A estrutura atingiu um patamar crítico e de forma absolutamente evidente."
    out = sanitize_flourish_text(raw)
    assert "patamar crítico" not in out.lower()
    assert "absolutamente evidente" not in out.lower()
    assert "condição crítica" in out.lower() or "conforme observado" in out.lower()


def test_standardize_terms():
    assert "Longarina" in standardize_terms("A viga principal apresenta corrosão")


def test_dedupe_and_short_conclusions():
    content = {
        "titulo": "LAUDO",
        "chapters": [
            {
                "id": "patologias",
                "title": "Patologias",
                "paragraphs": [
                    "Foi constatada corrosão na longarina com perda de seção.",
                    "Foi constatada corrosão na longarina com perda de seção resistente.",
                ],
            },
            {
                "id": "plano_correcao",
                "title": "12. Plano de Correção Estrutural",
                "paragraphs": ["Recuperar elementos críticos."],
                "tables": [],
            },
        ],
        "pathologies": [
            {
                "code": "P01",
                "name": "Corrosão",
                "severity": "crítica",
                "dnit_note": 1,
                "element": "viga principal",
                "description": "Perda de seção.",
                "metrology": {"method": "visual", "section_loss_pct": 30},
            }
        ],
        "classification": {
            "global_dnit_note": 1,
            "global_label": "Crítico",
            "governing_element_id": "sup_longarina",
            "governing_pathology_codes": ["P01"],
            "rationale": "Perda significativa da capacidade resistente.",
            "standard_refs": ["NBR 9452"],
        },
        "element_inventory": [
            {"element_id": "sup_longarina", "name": "Longarina Metálica", "status": "crítico"}
        ],
        "photographic_report": [
            {
                "photo_number": 1,
                "title": "Foto genérica",
                "description": "Registro fotográfico da vistoria",
                "severity": "crítica",
                "element_id": "sup_longarina",
                "pathology_refs": ["P01"],
            }
        ],
        "references": ["ABNT NBR 9452"],
        "conclusions": [
            "Apenas monitoramento.",
            "Apenas monitoramento da obra.",
            "Seguir acompanhando.",
            "Extra 4",
            "Extra 5",
            "Extra 6",
        ],
    }
    out = apply_editorial_postprocess(content)
    assert out["editorial_postprocess"]["applied"] is True
    # Dedupe nos capítulos
    paras = out["chapters"][0]["paragraphs"]
    assert len(paras) == 1
    # Plano virou tabela
    plan = next(c for c in out["chapters"] if "plano" in str(c.get("id") or "").lower())
    assert plan["tables"]
    assert any("Fase" in (t.get("headers") or []) for t in plan["tables"])
    # Conclusões curtas e coerentes com nota 1
    assert len(out["conclusions"]) <= 5
    joined = " ".join(out["conclusions"]).lower()
    assert "monitoramento" not in joined or "interven" in joined or "interdi" in joined
    # Foto padronizada
    photo = out["photographic_report"][0]
    assert "Elemento:" in photo["legend"]
    assert "Criticidade:" in photo["legend"]
    # Norma com blurb
    assert any("Utilizada para" in r for r in out["references"])
    # Memória de classificação
    class_ch = next(
        c
        for c in out["chapters"]
        if "classific" in str(c.get("id") or "").lower()
        or "parecer" in str(c.get("id") or "").lower()
    )
    assert any(
        isinstance(t, dict) and "memória" in str(t.get("caption") or "").lower()
        for t in (class_ch.get("tables") or [])
    )
    # Metrology honesty note
    assert "baixa" in str(out["pathologies"][0]["metrology"].get("reliability_note") or "").lower()


def test_enrichment_runs_editorial():
    content = {
        "chapters": [{"id": "objetivo", "title": "Objetivo", "paragraphs": ["Vistoria."]}],
        "pathologies": [],
        "conclusions": ["Ok."],
        "photographic_report": [],
        "references": [],
    }
    out = apply_engineering_enrichment(content, slug="pontes")
    assert out.get("editorial_postprocess", {}).get("applied") is True


def test_editorial_checklist_flags_missing_rationale():
    content = {
        "editorial_postprocess": {"applied": True, "warnings": []},
        "classification": {"global_dnit_note": 2, "rationale": ""},
        "chapters": [{"id": "plano_correcao", "title": "Plano", "tables": [{"headers": ["Fase"], "rows": [["1"]]}]}],
        "conclusions": ["a"],
    }
    chk = editorial_checklist(content)
    assert any(i["code"] == "classification_rationale" for i in chk["issues"])
