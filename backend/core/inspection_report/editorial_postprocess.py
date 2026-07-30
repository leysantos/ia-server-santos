"""L20 — Pós-processamento editorial institucional dos laudos.

Objetivo: aparência de consultoria (DNIT/DER/CREA/ABNT), sem floreios de IA.
Determinístico — não chama LLM. Aplicado após enrichment L10–L16 e antes do PDF.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any

# Frases típicas de LLM → equivalentes técnicos objetivos
_FLOURISH_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\batingiu um patamar crítico\b", re.I), "apresenta condição crítica"),
    (re.compile(r"\bsituação extremamente alarmante\b", re.I), "condição crítica identificada"),
    (re.compile(r"\bde forma absolutamente evidente\b", re.I), "conforme observado"),
    (re.compile(r"\belevado grau de excelência\b", re.I), "condição satisfatória"),
    (re.compile(r"\bexpressiva deterioração sem precedentes\b", re.I), "deterioração acentuada"),
    (re.compile(r"\bgrave cenário estrutural\b", re.I), "comprometimento estrutural relevante"),
    (re.compile(r"\bextremamente (preocupante|grave|alarmante)\b", re.I), r"\1"),
    (re.compile(r"\babsolutamente (necessário|essencial|crítico)\b", re.I), r"\1"),
    (re.compile(r"\bimprescindível\b", re.I), "necessário"),
    (re.compile(r"\bde suma importância\b", re.I), "relevante"),
    (re.compile(r"\bvale ressaltar que\b", re.I), ""),
    (re.compile(r"\bé importante destacar que\b", re.I), ""),
    (re.compile(r"\bnão se pode olvidar que\b", re.I), ""),
    (re.compile(r"\bem um cenário ideal\b", re.I), ""),
    (re.compile(r"\bsem sombra de dúvida\b", re.I), ""),
    (re.compile(r"\bde maneira cristalina\b", re.I), ""),
    (re.compile(r"\brevela-se (claramente|evidentemente)\b", re.I), "observa-se"),
    (re.compile(r"\bmostra-se (claramente|evidentemente)\b", re.I), "constata-se"),
    (re.compile(r"\bverifica-se de forma inequívoca\b", re.I), "verificou-se"),
    (re.compile(r"\bde forma inequívoca\b", re.I), ""),
    (re.compile(r"\bquadro preocupante\b", re.I), "condição desfavorável"),
    (re.compile(r"\bsinal de alerta\b", re.I), "indicativo de anomalia"),
    (re.compile(r"\bexige atenção imediata e urgente\b", re.I), "requer intervenção prioritária"),
]

# Padronização de nomenclatura (preferência → variantes a unificar)
_TERM_CANONICAL: list[tuple[str, list[str]]] = [
    ("Longarina Metálica", ["viga principal metálica", "perfil metálico principal", "viga mestra metálica"]),
    ("Longarina", ["viga principal", "viga mestra"]),
    ("Travessa", ["transversal metálica", "viga transversal"]),
    ("Aparato de apoio", ["aparelho de apoio", "apoio elastomérico", "neoprene"]),
    ("Encontro", ["encontros da obra", "encontros da ponte"]),
    ("Pilares", ["pilares de apoio", "pilares da infraestrutura"]),
    ("Tabuleiro", ["laje do tabuleiro", "laje do piso"]),
    ("Contenção", ["estrutura de contenção", "muro de contenção"]),
]

_NORM_BLURBS: dict[str, str] = {
    "9452": "Utilizada para classificação da condição estrutural de obras-de-arte especiais (OAE).",
    "6118": "Utilizada para avaliação de estruturas de concreto armado e critérios de desempenho.",
    "8800": "Utilizada para avaliação de estruturas de aço e mistas de aço e concreto.",
    "7187": "Utilizada para projeto e verificação de pontes de concreto armado e protendido.",
    "11682": "Utilizada para estabilidade de taludes e contenções.",
    "6122": "Utilizada para fundações (capacidade de carga e desempenho).",
    "9050": "Utilizada para acessibilidade quando aplicável ao objeto.",
    "dnit 010": "Utilizada como referência de procedimentos de inspeção de OAE (DNIT).",
    "010/2004": "Utilizada como referência de procedimentos de inspeção de OAE (DNIT).",
}

_MAX_CONCLUSIONS = 5
_DEDUP_SIMILARITY = 0.82


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _norm_key(text: str) -> str:
    t = _strip_accents(text).lower()
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _tokenize(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", _norm_key(text)) if len(t) >= 3}


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def sanitize_flourish_text(text: str) -> str:
    """Remove floreios típicos de IA e compacta espaços."""
    out = text or ""
    for pattern, repl in _FLOURISH_REPLACEMENTS:
        out = pattern.sub(repl, out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\s+\n", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def standardize_terms(text: str) -> str:
    """Unifica variantes terminológicas para o termo canônico."""
    out = text or ""
    for canonical, variants in _TERM_CANONICAL:
        for variant in variants:
            out = re.sub(re.escape(variant), canonical, out, flags=re.IGNORECASE)
    return out


def _rewrite_paragraph(text: str) -> str:
    return standardize_terms(sanitize_flourish_text(text))


def dedupe_paragraphs(paragraphs: list[str], *, seen: list[str] | None = None) -> list[str]:
    """Elimina parágrafos duplicados ou quase idênticos (Jaccard)."""
    pool = list(seen or [])
    result: list[str] = []
    for raw in paragraphs:
        p = _rewrite_paragraph(str(raw or ""))
        if not p or len(p) < 12:
            continue
        if any(_jaccard(p, prev) >= _DEDUP_SIMILARITY for prev in pool):
            continue
        result.append(p)
        pool.append(p)
    return result


def _shorten_conclusions(items: list[Any]) -> list[str]:
    cleaned = dedupe_paragraphs([str(c) for c in items if c])
    # Preferir estrutura objetiva: máx. 5 itens
    return cleaned[:_MAX_CONCLUSIONS]


def _ensure_plano_table(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Garante plano de correção/recuperação em tabela (Fase/Objetivo/Serviços/…)."""
    out: list[dict[str, Any]] = []
    headers = ["Fase", "Objetivo", "Serviços", "Prioridade", "Prazo", "Dependências"]
    for ch in chapters:
        if not isinstance(ch, dict):
            continue
        c = dict(ch)
        cid = str(c.get("id") or "").lower()
        title = str(c.get("title") or "").lower()
        is_plan = cid in ("plano_correcao", "plano", "recuperacao") or (
            "plano" in title and ("corre" in title or "recupera" in title)
        )
        if not is_plan:
            out.append(c)
            continue

        tables = [t for t in (c.get("tables") or []) if isinstance(t, dict)]
        has_plan_table = False
        for t in tables:
            hdrs = [str(h).lower() for h in (t.get("headers") or [])]
            if any("fase" in h for h in hdrs) or any("prioridade" in h for h in hdrs):
                has_plan_table = True
                # Normaliza cabeçalhos se incompletos
                if len(hdrs) < 4:
                    t["headers"] = headers
                break

        if not has_plan_table:
            rows: list[list[str]] = []
            # Extrai linhas a partir de schedule se existir no chapter context — fallback genérico
            paras = [str(p) for p in (c.get("paragraphs") or []) if p]
            if paras:
                rows.append(
                    [
                        "1",
                        "Contenção / segurança",
                        paras[0][:180],
                        "Alta",
                        "A definir",
                        "—",
                    ]
                )
            if len(paras) > 1:
                rows.append(
                    [
                        "2",
                        "Recuperação estrutural",
                        paras[1][:180],
                        "Média",
                        "A definir",
                        "Fase 1",
                    ]
                )
            if not rows:
                rows.append(["1", "A elaborar", "—", "—", "—", "—"])
            tables.append(
                {
                    "caption": "Plano de recuperação / correção",
                    "headers": headers,
                    "rows": rows,
                }
            )
            # Mantém 1 parágrafo introdutório objetivo
            c["paragraphs"] = dedupe_paragraphs(
                [
                    "O plano de recuperação está organizado por fases, com objetivos, "
                    "serviços, prioridade, prazo e dependências. Os serviços devem ser "
                    "detalhados em projeto executivo e orçamento específicos."
                ]
                + paras[:1]
            )
        c["tables"] = tables
        out.append(c)
    return out


def _enrich_norm_references(references: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in references:
        text = _rewrite_paragraph(str(raw or ""))
        if not text:
            continue
        key = _norm_key(text)
        if key in seen:
            continue
        seen.add(key)
        low = key
        blurb = ""
        for code, tip in _NORM_BLURBS.items():
            if code in low and tip.lower() not in low:
                blurb = tip
                break
        if blurb and "utilizada para" not in low and "—" not in text:
            text = f"{text} — {blurb}"
        result.append(text)
    return result


def _classification_decision_memory(content: dict[str, Any]) -> dict[str, Any] | None:
    """Tabela-memória da decisão de classificação (nunca só a nota)."""
    cls = content.get("classification") if isinstance(content.get("classification"), dict) else {}
    if not cls:
        return None
    note = cls.get("global_dnit_note")
    label = cls.get("global_label") or ""
    gov_el = cls.get("governing_element_id") or "—"
    # Nome legível do elemento
    inv = content.get("element_inventory") if isinstance(content.get("element_inventory"), list) else []
    el_name = gov_el
    for e in inv:
        if isinstance(e, dict) and str(e.get("element_id") or "") == str(gov_el):
            el_name = str(e.get("name") or gov_el)
            break
    codes = cls.get("governing_pathology_codes") or []
    path_names: list[str] = []
    for p in content.get("pathologies") or []:
        if isinstance(p, dict) and p.get("code") in codes:
            path_names.append(str(p.get("name") or p.get("code")))
    patho = ", ".join(path_names or [str(c) for c in codes]) or "—"
    standards = ", ".join(cls.get("standard_refs") or ["ABNT NBR 9452"])
    rationale = _rewrite_paragraph(str(cls.get("rationale") or "Conforme patologias e inventário."))
    return {
        "caption": "Memória resumida da classificação",
        "headers": ["Item", "Descrição"],
        "rows": [
            ["Elemento governante", el_name],
            ["Patologia(s) governante(s)", patho],
            ["Critério utilizado", standards],
            ["Resultado (nota DNIT)", f"{note} — {label}" if note is not None else label or "—"],
            ["Motivo", rationale[:400]],
        ],
    }


def _normalize_photo_entries(photos: list[Any]) -> list[dict[str, Any]]:
    """Garante Elemento / Patologia / Localização / Criticidade / descrição objetiva."""
    out: list[dict[str, Any]] = []
    seen_desc: list[str] = []
    for raw in photos:
        if not isinstance(raw, dict):
            continue
        p = dict(raw)
        desc = _rewrite_paragraph(str(p.get("description") or ""))
        if desc and any(_jaccard(desc, prev) >= _DEDUP_SIMILARITY for prev in seen_desc):
            desc = ""  # remove repetição
        if desc:
            seen_desc.append(desc)
        p["description"] = desc or _rewrite_paragraph(str(p.get("legend") or p.get("title") or ""))

        element = str(p.get("element") or p.get("element_id") or "").strip()
        pathology = ""
        refs = p.get("pathology_refs") or []
        if refs:
            pathology = ", ".join(str(r) for r in refs)
        legend = str(p.get("legend") or "")
        if "Patologia:" in legend and not pathology:
            m = re.search(r"Patologia:\s*([^|]+)", legend, re.I)
            if m:
                pathology = m.group(1).strip()
        location = str(p.get("location") or "").strip()
        severity = str(p.get("severity") or "").strip().upper() or "—"

        # Legenda padronizada objetiva
        title = _rewrite_paragraph(str(p.get("title") or f"Foto {p.get('photo_number') or ''}"))
        p["title"] = title
        parts = [
            f"Elemento: {element or '—'}",
            f"Patologia: {pathology or '—'}",
            f"Localização: {location or 'conforme registro fotográfico'}",
            f"Criticidade: {severity}",
        ]
        p["legend"] = " | ".join(parts)
        if element:
            p["element"] = standardize_terms(element)
        out.append(p)
    return out


def _coherence_fixes(content: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """
    Validações automáticas de coerência entre classificação, patologias e conclusão.
    Corrige textos incompatíveis quando possível.
    """
    warnings: list[str] = []
    out = dict(content)
    cls = out.get("classification") if isinstance(out.get("classification"), dict) else {}
    note = cls.get("global_dnit_note")
    pathologies = [p for p in (out.get("pathologies") or []) if isinstance(p, dict)]
    has_critical = any(
        "crít" in str(p.get("severity") or "").lower() or p.get("dnit_note") == 1
        for p in pathologies
    )
    conclusions = [str(c) for c in (out.get("conclusions") or [])]
    joined = " ".join(conclusions).lower()

    # Nota 1 / crítica → conclusão não pode ser só "monitoramento"
    if (note == 1 or has_critical) and conclusions:
        monitor_only = any(
            re.search(r"\b(apenas )?monitoramento\b", c, re.I)
            and not re.search(r"\b(interdi[cç]|interven|recupera|reparo|refor[cç])\b", c, re.I)
            for c in conclusions
        )
        if monitor_only or (
            "monitoramento" in joined
            and "interdi" not in joined
            and "interven" not in joined
            and "recupera" not in joined
        ):
            warnings.append(
                "Coerência: classificação crítica/nota 1 incompatível com conclusão só de monitoramento"
            )
            fix = (
                "Constatou-se condição crítica em elementos estruturais relevantes. "
                "A recomendação prioriza intervenção corretiva e, quando aplicável, "
                "restrição de uso, em conformidade com a classificação DNIT/NBR 9452 — "
                "não se limita a monitoramento."
            )
            conclusions = [fix] + [
                c
                for c in conclusions
                if not re.search(r"\bapenas monitoramento\b", c, re.I)
            ]
            out["conclusions"] = conclusions[:_MAX_CONCLUSIONS]

    # Justificar conclusão genérica de interdição
    new_conc: list[str] = []
    for c in out.get("conclusions") or []:
        text = str(c)
        if re.search(r"\binterdit", text, re.I) and len(text) < 80:
            text = (
                "A recomendação de interdição decorre da identificação de patologias "
                "classificadas como críticas, associadas à perda de seção resistente "
                "e/ou comprometimento de elementos principais, conforme critérios da "
                "ABNT NBR 9452 e classificação DNIT adotada neste laudo."
            )
            warnings.append("Conclusão de interdição ampliada com fundamentação técnica")
        new_conc.append(_rewrite_paragraph(text))
    if new_conc:
        out["conclusions"] = _shorten_conclusions(new_conc)

    return out, warnings


def apply_editorial_postprocess(content: dict[str, Any]) -> dict[str, Any]:
    """
    Pipeline editorial antes do PDF/DOCX:
    floreios → termos → dedupe → plano tabela → fotos → normas →
    memória de classificação → conclusão curta → coerência.
    """
    out = dict(content or {})
    editorial_warnings: list[str] = []

    # Capítulos
    chapters_in = [c for c in (out.get("chapters") or []) if isinstance(c, dict)]
    seen_paras: list[str] = []
    chapters_out: list[dict[str, Any]] = []
    for ch in chapters_in:
        c = dict(ch)
        paras = dedupe_paragraphs(
            [str(p) for p in (c.get("paragraphs") or [])],
            seen=seen_paras,
        )
        seen_paras.extend(paras)
        c["paragraphs"] = paras
        # Tabelas: sanitiza células texto
        tables = []
        for t in c.get("tables") or []:
            if not isinstance(t, dict):
                continue
            tt = dict(t)
            tt["caption"] = _rewrite_paragraph(str(tt.get("caption") or ""))
            rows = []
            for row in tt.get("rows") or []:
                if isinstance(row, (list, tuple)):
                    rows.append([_rewrite_paragraph(str(cell)) for cell in row])
                else:
                    rows.append(row)
            tt["rows"] = rows
            tables.append(tt)
        c["tables"] = tables
        if c.get("title"):
            c["title"] = _rewrite_paragraph(str(c["title"]))
        chapters_out.append(c)

    chapters_out = _ensure_plano_table(chapters_out)

    # Memória de classificação na tabela do capítulo classificacao_dnit
    mem = _classification_decision_memory(out)
    if mem:
        attached = False
        for c in chapters_out:
            cid = str(c.get("id") or "").lower()
            if cid in ("classificacao_dnit", "classificacao", "parecer", "parecer_tecnico"):
                tables = list(c.get("tables") or [])
                if not any(
                    isinstance(t, dict)
                    and "memória" in str(t.get("caption") or "").lower()
                    for t in tables
                ):
                    tables.insert(0, mem)
                c["tables"] = tables
                paras = list(c.get("paragraphs") or [])
                if not any("elemento governante" in p.lower() for p in paras):
                    paras.insert(
                        0,
                        (
                            "A classificação apresentada fundamenta-se no elemento governante, "
                            "nas patologias associadas e nos critérios da norma de referência, "
                            "conforme memória resumida a seguir."
                        ),
                    )
                c["paragraphs"] = dedupe_paragraphs(paras)
                attached = True
                break
        if not attached:
            chapters_out.append(
                {
                    "id": "classificacao_dnit",
                    "title": "Classificação e parecer técnico (NBR 9452 / DNIT)",
                    "paragraphs": [
                        "A classificação apresentada fundamenta-se no elemento governante, "
                        "nas patologias associadas e nos critérios da norma de referência, "
                        "conforme memória resumida a seguir."
                    ],
                    "tables": [mem],
                }
            )

    out["chapters"] = chapters_out

    # Patologias
    path_out = []
    for p in out.get("pathologies") or []:
        if not isinstance(p, dict):
            continue
        pp = dict(p)
        for key in ("name", "location", "element", "description", "cause", "solution", "urgency"):
            if pp.get(key):
                pp[key] = _rewrite_paragraph(str(pp[key]))
        # Honesty visual em notes de metrologia
        metro = pp.get("metrology") if isinstance(pp.get("metrology"), dict) else None
        if metro:
            method = str(metro.get("method") or "visual").lower()
            if method in ("visual", "estimated") and not metro.get("reliability_note"):
                metro = dict(metro)
                metro["reliability_note"] = (
                    f"Método: {method} | Confiabilidade: baixa | "
                    "Necessita confirmação por ensaio ou medição documentada."
                )
                pp["metrology"] = metro
        path_out.append(pp)
    out["pathologies"] = path_out

    # Fotos
    out["photographic_report"] = _normalize_photo_entries(
        list(out.get("photographic_report") or [])
    )

    # Referências / normas
    out["references"] = _enrich_norm_references(list(out.get("references") or []))

    # Conclusões
    out["conclusions"] = _shorten_conclusions(list(out.get("conclusions") or []))

    # Campos de capa
    for key in ("titulo", "subtitulo", "objeto", "local", "compliance_note"):
        if out.get(key):
            out[key] = _rewrite_paragraph(str(out[key]))

    out, coh_warns = _coherence_fixes(out)
    editorial_warnings.extend(coh_warns)

    # Fingerprint editorial (rastreabilidade)
    blob = str(out.get("titulo") or "") + str(len(out.get("chapters") or []))
    out["editorial_postprocess"] = {
        "version": "L20",
        "applied": True,
        "warnings": editorial_warnings,
        "fingerprint": hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16],
    }
    return out


def editorial_checklist(content: dict[str, Any] | None) -> dict[str, Any]:
    """Itens editoriais para o checklist pré-export (warnings, não bloqueantes por padrão)."""
    content = content if isinstance(content, dict) else {}
    warnings: list[dict[str, str]] = []
    issues: list[dict[str, str]] = []

    ep = content.get("editorial_postprocess") if isinstance(content.get("editorial_postprocess"), dict) else {}
    if not ep.get("applied"):
        warnings.append(
            {
                "code": "editorial_missing",
                "message": "Pós-processamento editorial (L20) ainda não aplicado — regenere ou exporte via prepare",
            }
        )
    for w in ep.get("warnings") or []:
        warnings.append({"code": "editorial_coherence", "message": str(w)})

    conclusions = content.get("conclusions") or []
    if len(conclusions) > _MAX_CONCLUSIONS:
        warnings.append(
            {
                "code": "conclusions_long",
                "message": f"Conclusão com {len(conclusions)} itens — recomenda-se no máximo {_MAX_CONCLUSIONS}",
            }
        )

    # Plano com tabela?
    has_plan_table = False
    for ch in content.get("chapters") or []:
        if not isinstance(ch, dict):
            continue
        cid = str(ch.get("id") or "").lower()
        title = str(ch.get("title") or "").lower()
        if cid in ("plano_correcao", "plano") or "plano" in title:
            for t in ch.get("tables") or []:
                if isinstance(t, dict) and t.get("rows"):
                    has_plan_table = True
    if not has_plan_table:
        warnings.append(
            {
                "code": "plano_table",
                "message": "Plano de correção sem tabela Fase/Objetivo/Serviços/Prioridade/Prazo",
            }
        )

    cls = content.get("classification") if isinstance(content.get("classification"), dict) else {}
    if cls.get("global_dnit_note") is not None and not (cls.get("rationale") or "").strip():
        issues.append(
            {
                "code": "classification_rationale",
                "message": "Classificação DNIT sem fundamentação (rationale) — obrigatório justificar a nota",
            }
        )

    return {
        "issues": issues,
        "warnings": warnings,
    }
