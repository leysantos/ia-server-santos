"""Utilitários compartilhados de formatação dos laudos (DOCX/PDF)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

# Cores institucionais
COLOR_BLUE = "1D4ED8"  # azul
COLOR_GRAY = "94A3B8"  # cinza
COLOR_BLUE_HEX = "#1D4ED8"
COLOR_GRAY_HEX = "#94A3B8"

# Capítulos de capa/estrutura que não entram na sequência numérica do corpo
_SKIP_CHAPTER_IDS = {
    "capa",
    "sumario",
    "cover",
    "fotografico",
    "relatorio_fotografico",
    "photo",
}


def format_generated_at(dt: datetime | None = None) -> str:
    d = dt or datetime.now()
    return d.strftime("%d/%m/%Y %H:%M")


def format_severity_distribution(dist: Any) -> str:
    """Converte dict bruto em texto legível (evita {'crítica': 5} no documento)."""
    if not dist:
        return "—"
    if isinstance(dist, str):
        return dist
    if isinstance(dist, dict):
        parts = []
        for key in ("crítica", "critica", "alta", "média", "media", "baixa"):
            if key in dist:
                label = key.replace("critica", "crítica").replace("media", "média")
                parts.append(f"{label}: {dist[key]}")
        if not parts:
            parts = [f"{k}: {v}" for k, v in dist.items()]
        return "; ".join(parts)
    return str(dist)


def ensure_chapter_number(title: str, number: int) -> str:
    """Sempre aplica numeração contínua (strip de prefixo antigo do Gemini)."""
    from core.inspection_report.protocol_order import strip_chapter_number

    t = strip_chapter_number(title or "")
    if not t:
        return f"{number}."
    return f"{number}. {t}"


def build_photographic_index_table(content: dict[str, Any]) -> dict[str, Any] | None:
    """Índice foto → título → elemento → gravidade → patologias (antes do anexo)."""
    import re

    photos = [
        p for p in (content.get("photographic_report") or []) if isinstance(p, dict)
    ]
    if not photos:
        return None

    known_codes = {
        str(p.get("code") or p.get("codigo") or "").strip().upper()
        for p in (content.get("pathologies") or [])
        if isinstance(p, dict) and (p.get("code") or p.get("codigo"))
    }

    def _clean_refs(raw: Any) -> list[str]:
        refs: list[str] = []
        for item in raw or []:
            s = str(item or "").strip()
            if not s:
                continue
            # Preferir códigos P01 / P1
            m = re.search(r"\bP0*\d+\b", s, re.I)
            if m:
                code = m.group(0).upper()
                if re.match(r"^P\d+$", code):
                    # normaliza P1 → P01 se existir no inventário
                    if code in known_codes:
                        refs.append(code)
                    else:
                        padded = f"P{int(code[1:]):02d}"
                        refs.append(padded if padded in known_codes else code)
                continue
            su = s.upper()
            if su in known_codes:
                refs.append(su)
                continue
            # ignora texto livre (NBR 9452, descrições…)
        # únicos preservando ordem
        seen: set[str] = set()
        out: list[str] = []
        for r in refs:
            if r not in seen:
                seen.add(r)
                out.append(r)
        return out

    ordered = sorted(photos, key=lambda p: int(p.get("photo_number") or 0))
    return {
        "caption": "Índice do relatório fotográfico",
        "headers": ["Foto", "Título", "Elemento", "Gravidade", "Patologias"],
        "rows": [
            [
                f"{int(p.get('photo_number') or 0):02d}",
                str(p.get("title") or p.get("legend") or "—")[:70],
                str(p.get("element_id") or p.get("element_hint") or "—"),
                str(p.get("severity") or "—"),
                ", ".join(_clean_refs(p.get("pathology_refs"))) or "—",
            ]
            for p in ordered
        ],
    }


def build_body_sections(content: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Monta seções do corpo em ordem de protocolo (CREA/perícia),
    com numeração contínua única (fonte do sumário).
    """
    from core.inspection_report.protocol_order import (
        is_analytics_like,
        is_skip_chapter,
        normalize_chapter_title,
        reorder_chapters_for_protocol,
    )

    sections: list[dict[str, Any]] = []
    n = 0
    seen_ids: set[str] = set()

    def _push(
        title: str,
        *,
        paragraphs=None,
        tables=None,
        charts=None,
        chapter_id: str = "",
        cards=None,
        chart_images=None,
    ):
        nonlocal n
        n += 1
        sec: dict[str, Any] = {
            "number": n,
            "chapter_id": chapter_id,
            "title": ensure_chapter_number(title, n),
            "paragraphs": list(paragraphs or []),
            "tables": list(tables or []),
            "charts": list(charts or []),
        }
        if cards is not None:
            sec["cards"] = cards
        if chart_images is not None:
            sec["chart_images"] = chart_images
        sections.append(sec)
        if chapter_id:
            seen_ids.add(chapter_id)

    # Solicitante (tabela) — uma vez
    sol_table = solicitante_table(content)
    if sol_table:
        _push("Dados do solicitante", tables=[sol_table], chapter_id="solicitante")

    # Capítulos já ordenados/deduplicados
    ordered_chapters = reorder_chapters_for_protocol(list(content.get("chapters") or []))
    pathologies = content.get("pathologies") or []
    classification = (
        content.get("classification")
        if isinstance(content.get("classification"), dict)
        else None
    )
    inventory = (
        content.get("element_inventory")
        if isinstance(content.get("element_inventory"), list)
        else None
    )
    interdiction = (
        content.get("interdiction")
        if isinstance(content.get("interdiction"), dict)
        else None
    )

    analytics_pushed = False

    for chapter in ordered_chapters:
        cid = str(chapter.get("id") or "").lower().strip()
        title = normalize_chapter_title(
            cid, str(chapter.get("title") or chapter.get("id") or "Capítulo")
        )
        if is_skip_chapter(cid, title):
            continue
        if cid and cid in seen_ids:
            continue
        # Evitar segundo solicitante
        if cid == "solicitante" and "solicitante" in seen_ids:
            continue

        if is_analytics_like(cid, title):
            if analytics_pushed:
                continue
            from core.inspection_report.analytics import build_pathology_analytics

            analytics = build_pathology_analytics(content)
            _push(
                "Análise quantitativa e qualitativa das patologias",
                paragraphs=analytics.get("summary_paragraphs")
                or chapter.get("paragraphs"),
                tables=analytics.get("tables") or chapter.get("tables"),
                chapter_id="analytics",
                cards=analytics.get("cards") or [],
                chart_images=analytics.get("charts") or [],
            )
            seen_ids.add("indicadores")
            seen_ids.add("gravidade")
            analytics_pushed = True
            continue

        _push(
            title,
            paragraphs=chapter.get("paragraphs"),
            tables=chapter.get("tables"),
            charts=chapter.get("charts"),
            chapter_id=cid or title.lower()[:40],
        )

    # Fallbacks se enrichment não materializou capítulos
    if (
        inventory
        and "inventario_elementos" not in seen_ids
    ):
        from core.inspection_report.elements import element_inventory_table

        _push(
            "Inventário estruturado de elementos",
            paragraphs=[
                f"Inventário com {len(inventory)} elemento(s) do catálogo da tipología."
            ],
            tables=[element_inventory_table(inventory)],
            chapter_id="inventario_elementos",
        )

    if pathologies and "patologias" not in seen_ids and "diagnostico" not in seen_ids:
        # Só se não houver capítulo narrativo de patologias
        if not any("patolog" in (s.get("title") or "").lower() for s in sections):
            rows = [
                [
                    p.get("code") or "—",
                    p.get("name") or "—",
                    p.get("element_id") or p.get("location") or "—",
                    p.get("severity") or "—",
                    f"{p.get('score') or '—'}/5",
                    p.get("solution") or "—",
                    p.get("urgency") or "—",
                ]
                for p in pathologies
                if isinstance(p, dict)
            ]
            _push(
                "Síntese de patologias",
                paragraphs=[
                    f"{p.get('code') or ''} {p.get('name')}: {p.get('description') or ''}"
                    for p in pathologies
                    if isinstance(p, dict)
                ],
                tables=[
                    {
                        "caption": "Quadro resumo de patologias",
                        "headers": [
                            "Código",
                            "Patologia",
                            "Elemento/Local",
                            "Severidade",
                            "Score",
                            "Solução",
                            "Urgência",
                        ],
                        "rows": rows,
                    }
                ],
                chapter_id="patologias",
            )

    if pathologies and "metrologia" not in seen_ids:
        from core.inspection_report.metrology import metrology_table, pathology_has_metrology

        if any(isinstance(p, dict) and pathology_has_metrology(p) for p in pathologies):
            _push(
                "Campos metrológicos tipados",
                paragraphs=[
                    "Medidas tipadas (estimativas de campo quando method≠measured). "
                    "Confirmar com ensaios instrumentados prioritários."
                ],
                tables=[metrology_table(pathologies)],
                chapter_id="metrologia",
            )

    if classification and "classificacao_dnit" not in seen_ids:
        from core.inspection_report.classification import (
            classification_elements_table,
            classification_summary_table,
        )

        note = classification.get("global_dnit_note")
        _push(
            "Classificação e parecer técnico (NBR 9452 / DNIT)",
            paragraphs=[
                (
                    f"Tipo de inspeção: {classification.get('inspection_type') or '—'}. "
                    f"Nota DNIT global: {note} ({classification.get('global_label') or '—'}). "
                    f"Elemento governante: {classification.get('governing_element_id') or '—'}."
                ),
                str(classification.get("rationale") or ""),
            ],
            tables=[
                classification_summary_table(classification),
                classification_elements_table(classification),
            ],
            chapter_id="classificacao_dnit",
        )

    if (
        interdiction
        and interdiction.get("required")
        and "interdicao" not in seen_ids
    ):
        _push(
            "Ato de interdição e restrição de uso",
            paragraphs=[
                str(interdiction.get("action_summary") or ""),
                f"Autoridade: {interdiction.get('authority') or '—'}. "
                f"Prazo: {interdiction.get('deadline') or '—'}.",
            ],
            tables=[
                {
                    "caption": "Ato de interdição / restrição de uso",
                    "headers": ["Campo", "Valor"],
                    "rows": [
                        ["Tipo", str(interdiction.get("restriction_type") or "—")],
                        ["Ação", str(interdiction.get("action_summary") or "—")],
                        [
                            "Patologias",
                            ", ".join(interdiction.get("pathology_refs") or []) or "—",
                        ],
                    ],
                }
            ],
            chapter_id="interdicao",
        )

    photos = content.get("photographic_report") or []
    indicators = content.get("indicators") or {}
    if (pathologies or photos) and not analytics_pushed and "analytics" not in seen_ids:
        from core.inspection_report.analytics import build_pathology_analytics

        analytics = build_pathology_analytics(content)
        _push(
            "Análise quantitativa e qualitativa das patologias",
            paragraphs=analytics.get("summary_paragraphs"),
            tables=analytics.get("tables"),
            chapter_id="analytics",
            cards=analytics.get("cards") or [],
            chart_images=analytics.get("charts") or [],
        )
    elif indicators and "indicadores" not in seen_ids and "analytics" not in seen_ids:
        dist_txt = format_severity_distribution(indicators.get("severity_distribution"))
        _push(
            "Indicadores de conservação",
            paragraphs=[
                f"Índice de comprometimento: {indicators.get('compromise_index_pct', '—')}%. "
                f"Índice de conservação aparente: {indicators.get('conservation_index_pct', '—')}%. "
                f"Distribuição por gravidade: {dist_txt}."
            ],
            chapter_id="indicadores",
        )

    schedule = content.get("schedule") or []
    if schedule and "cronograma" not in seen_ids:
        _push(
            "Cronograma de intervenções",
            tables=[
                {
                    "caption": "Cronograma de reparo por prioridade",
                    "headers": ["Ordem", "Fase", "Atividades", "Duração"],
                    "rows": [
                        [
                            str(s.get("order") or ""),
                            s.get("phase") or "—",
                            s.get("activities") or "—",
                            s.get("duration") or "—",
                        ]
                        for s in schedule
                    ],
                }
            ],
            chapter_id="cronograma",
        )

    conclusions = content.get("conclusions") or []
    if conclusions and "conclusao" not in seen_ids:
        _push(
            "Conclusões e recomendações",
            paragraphs=[str(c) for c in conclusions],
            chapter_id="conclusao",
        )

    refs = content.get("references") or []
    citations = content.get("normative_citations") or []
    if "referencias" not in seen_ids:
        if citations:
            from core.inspection_report.normative_rag import normative_citations_table

            _push(
                "Referências",
                paragraphs=[
                    "Citações normativas rastreáveis recuperadas por tipología (L15 — RAG).",
                ],
                tables=[normative_citations_table(list(citations))],
                chapter_id="referencias",
            )
        elif refs:
            _push("Referências", paragraphs=[str(r) for r in refs], chapter_id="referencias")

    return sections

def build_sumario_entries(content: dict[str, Any]) -> list[dict[str, str]]:
    """
    Monta o sumário institucional a partir das seções reais do corpo.
    Inclui responsáveis técnicos, índice fotográfico e o relatório fotográfico.
    """
    sections = build_body_sections(content)
    entries: list[dict[str, str]] = []
    for section in sections:
        entries.append(
            {
                "label": str(section.get("title") or ""),
                "chapter_id": str(section.get("chapter_id") or ""),
            }
        )

    if normalize_parties(content.get("responsaveis_tecnicos")):
        entries.append({"label": "Responsáveis técnicos", "chapter_id": "assinaturas"})

    next_n = (sections[-1]["number"] + 1) if sections else 1
    if build_photographic_index_table(content):
        entries.append(
            {
                "label": f"{next_n}. Índice do relatório fotográfico",
                "chapter_id": "indice_fotografico",
            }
        )
        next_n += 1
    entries.append(
        {
            "label": f"{next_n}. Relatório fotográfico",
            "chapter_id": "fotografico",
        }
    )
    return [e for e in entries if (e.get("label") or "").strip()]


def _truncate_header(text: str, max_len: int = 72) -> str:
    t = (text or "—").strip()
    if len(t) <= max_len:
        return t
    cut = t[: max_len - 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,;/-") + "…"


def header_meta_lines(content: dict[str, Any], *, generated_at: str) -> list[str]:
    """Linhas à direita do cabeçalho (sem truncar no meio da palavra)."""
    return [
        f"Nº: {content.get('numero_laudo') or '—'}",
        f"Objeto: {_truncate_header(str(content.get('objeto') or '—'), 72)}",
        f"Vistoria: {content.get('data_vistoria') or '—'}",
        f"Gerado em: {generated_at}",
    ]


def ensure_sumario_chapter(content: dict[str, Any]) -> dict[str, Any]:
    """
    Garante capítulo `sumario` no JSON do laudo (para preview/UI e auditoria).
    O export Word/PDF usa `build_sumario_entries` diretamente.
    """
    if not isinstance(content, dict):
        return content
    out = dict(content)
    entries = build_sumario_entries(out)
    paragraphs = [e["label"] for e in entries]
    chapters = list(out.get("chapters") or [])
    sumario = {
        "id": "sumario",
        "title": "Sumário",
        "paragraphs": paragraphs,
        "tables": [],
        "charts": [],
    }
    replaced = False
    for i, ch in enumerate(chapters):
        if not isinstance(ch, dict):
            continue
        cid = str(ch.get("id") or "").lower()
        title_l = str(ch.get("title") or "").lower()
        if cid == "sumario" or "sumário" in title_l or "sumario" in title_l:
            chapters[i] = {**ch, **sumario, "title": ch.get("title") or "Sumário"}
            replaced = True
            break
    if not replaced:
        insert_at = 0
        for i, ch in enumerate(chapters):
            if isinstance(ch, dict) and str(ch.get("id") or "").lower() in ("capa", "cover"):
                insert_at = i + 1
                break
        chapters.insert(insert_at, sumario)
    out["chapters"] = chapters
    out["sumario"] = paragraphs
    return out


def _dist_rows(dist: Any) -> list[list[str]]:
    if not isinstance(dist, dict):
        return []
    order = ["crítica", "critica", "alta", "média", "media", "baixa"]
    rows = []
    used = set()
    for key in order:
        if key in dist and key not in used:
            label = key.replace("critica", "crítica").replace("media", "média").title()
            rows.append([label, str(dist[key])])
            used.add(key)
    for k, v in dist.items():
        if k not in used:
            rows.append([str(k).title(), str(v)])
    return rows


def normalize_party(raw: Any) -> dict[str, str] | None:
    """Normaliza responsável técnico / de imagens."""
    if not isinstance(raw, dict):
        return None
    nome = str(raw.get("nome") or "").strip()
    if not nome:
        return None
    pid = str(raw.get("id") or "").strip()
    party = {
        "id": pid or nome.lower().replace(" ", "_")[:40],
        "nome": nome[:200],
        "profissao": str(raw.get("profissao") or "").strip()[:120],
        "crea": str(raw.get("crea") or "").strip()[:80],
        "art": str(raw.get("art") or "").strip()[:80],
        "email": str(raw.get("email") or "").strip()[:160],
        "telefone": str(raw.get("telefone") or "").strip()[:60],
        # L18 — ART rastreável
        "art_asset_id": str(raw.get("art_asset_id") or "").strip()[:80],
        "art_protocolo": str(raw.get("art_protocolo") or "").strip()[:120],
        "art_url": str(raw.get("art_url") or "").strip()[:400],
        # L19 — imagem de firma
        "signature_asset_id": str(raw.get("signature_asset_id") or "").strip()[:80],
    }
    return party


def normalize_parties(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in raw:
        party = normalize_party(item)
        if party:
            out.append(party)
    return out


def art_traceability_table(content: dict[str, Any] | None) -> dict[str, Any] | None:
    """Tabela L18 — ART / documentos técnicos vinculados aos RTs."""
    rts = normalize_parties((content or {}).get("responsaveis_tecnicos"))
    rows: list[list[str]] = []
    for rt in rts:
        has_trace = bool(rt.get("art") or rt.get("art_asset_id") or rt.get("art_protocolo") or rt.get("art_url"))
        if not has_trace and not rt.get("nome"):
            continue
        rows.append(
            [
                rt.get("nome") or "—",
                rt.get("crea") or "—",
                rt.get("art") or "—",
                rt.get("art_protocolo") or "—",
                "anexo" if rt.get("art_asset_id") else "—",
                (rt.get("art_url") or "—")[:60],
            ]
        )
    if not rows:
        return None
    return {
        "caption": "ART / documentos técnicos rastreáveis (L18)",
        "headers": ["Responsável", "CREA", "ART", "Protocolo", "Anexo", "URL / SICAR"],
        "rows": rows,
    }


def party_display_lines(party: dict[str, Any]) -> list[str]:
    """Linhas para bloco de assinatura (nome, profissão, CREA, ART, contato)."""
    lines: list[str] = []
    nome = str(party.get("nome") or "").strip()
    if nome:
        lines.append(nome.upper())
    prof = str(party.get("profissao") or "").strip()
    if prof:
        lines.append(prof.upper())
    crea = str(party.get("crea") or "").strip()
    if crea:
        lines.append(f"CREA: {crea}" if not crea.upper().startswith("CREA") else crea)
    art = str(party.get("art") or "").strip()
    if art:
        lines.append(f"ART: {art}" if not art.upper().startswith("ART") else art)
    contato = " · ".join(
        x for x in (str(party.get("telefone") or "").strip(), str(party.get("email") or "").strip()) if x
    )
    if contato:
        lines.append(contato)
    return lines


def month_year_label(content: dict[str, Any], *, fallback_dt: datetime | None = None) -> str:
    """Extrai mês/ano (ex.: 07/2026) da data da vistoria ou da data atual."""
    import re

    raw = str(content.get("data_vistoria") or "").strip()
    # dd/mm/yyyy ou mm/yyyy
    m = re.search(r"(\d{1,2})[/-](\d{4})", raw)
    if m:
        return f"{int(m.group(1)):02d}/{m.group(2)}"
    m2 = re.search(r"(\d{4})[/-](\d{1,2})", raw)
    if m2:
        return f"{int(m2.group(2)):02d}/{m2.group(1)}"
    d = fallback_dt or datetime.now()
    return d.strftime("%m/%Y")


def photo_authors_label(content: dict[str, Any]) -> str:
    nomes = [p["nome"] for p in normalize_parties(content.get("responsaveis_imagens")) if p.get("nome")]
    if not nomes:
        return ""
    if len(nomes) == 1:
        return nomes[0]
    return ", ".join(nomes[:-1]) + f" e {nomes[-1]}"


def photo_source_line(content: dict[str, Any], *, fallback_dt: datetime | None = None) -> str:
    """Fonte da fotografia: autor + mês/ano."""
    author = photo_authors_label(content) or "Autor não informado"
    return f"Fonte: {author} — {month_year_label(content, fallback_dt=fallback_dt)}"


def cover_parties_lines(content: dict[str, Any]) -> list[str]:
    """Linhas da capa: RT (CREA/ART) e responsáveis pelas fotos."""
    lines: list[str] = []
    rts = normalize_parties(content.get("responsaveis_tecnicos"))
    for i, rt in enumerate(rts, start=1):
        bits = [rt["nome"]]
        if rt.get("crea"):
            bits.append(f"CREA: {rt['crea']}")
        if rt.get("art"):
            bits.append(f"ART: {rt['art']}")
        prefix = "Responsável técnico" if len(rts) == 1 else f"Responsável técnico {i}"
        lines.append(f"{prefix}: " + " — ".join(bits))
    imgs = normalize_parties(content.get("responsaveis_imagens"))
    if imgs:
        nomes = ", ".join(p["nome"] for p in imgs)
        label = "Responsável pelas fotos" if len(imgs) == 1 else "Responsáveis pelas fotos"
        lines.append(f"{label}: {nomes}")
    return lines


def normalize_solicitante(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {"empresa": "", "cnpj": "", "endereco": "", "contato": ""}
    return {
        "empresa": str(raw.get("empresa") or "").strip()[:200],
        "cnpj": str(raw.get("cnpj") or "").strip()[:40],
        "endereco": str(raw.get("endereco") or "").strip()[:300],
        "contato": str(raw.get("contato") or "").strip()[:200],
    }


def solicitante_has_data(sol: dict[str, str] | None) -> bool:
    if not sol:
        return False
    return any(str(sol.get(k) or "").strip() for k in ("empresa", "cnpj", "endereco", "contato"))


def cover_solicitante_lines(content: dict[str, Any]) -> list[str]:
    sol = normalize_solicitante(content.get("solicitante"))
    if not solicitante_has_data(sol):
        return []
    lines: list[str] = []
    if sol["empresa"]:
        lines.append(f"Solicitante: {sol['empresa']}")
    if sol["cnpj"]:
        lines.append(f"CNPJ: {sol['cnpj']}")
    if sol["endereco"]:
        lines.append(f"Endereço do solicitante: {sol['endereco']}")
    if sol["contato"]:
        lines.append(f"Contato do solicitante: {sol['contato']}")
    return lines


def build_cover_layout(content: dict[str, Any], *, generated_at: str) -> dict[str, Any]:
    """
    Estrutura da 1ª folha do laudo: título + blocos em tabela (rótulo | valor).
    Usado por Word e PDF para layout institucional distribuído.
    """
    sol = normalize_solicitante(content.get("solicitante"))
    rts = normalize_parties(content.get("responsaveis_tecnicos"))
    imgs = normalize_parties(content.get("responsaveis_imagens"))

    ident_rows: list[list[str]] = []
    if content.get("numero_laudo"):
        ident_rows.append(["Nº do laudo", str(content.get("numero_laudo"))])
    ident_rows.append(["Objeto", str(content.get("objeto") or "—")])
    ident_rows.append(["Local", str(content.get("local") or "—")])
    ident_rows.append(["Data da vistoria", str(content.get("data_vistoria") or "—")])
    if content.get("tipo_vistoria"):
        ident_rows.append(["Tipo de vistoria", str(content.get("tipo_vistoria"))])

    blocks: list[dict[str, Any]] = [
        {"heading": "Identificação do objeto", "rows": ident_rows},
    ]

    if solicitante_has_data(sol):
        sol_rows: list[list[str]] = []
        if sol["empresa"]:
            sol_rows.append(["Empresa / órgão", sol["empresa"]])
        if sol["cnpj"]:
            sol_rows.append(["CNPJ", sol["cnpj"]])
        if sol["endereco"]:
            sol_rows.append(["Endereço", sol["endereco"]])
        if sol["contato"]:
            sol_rows.append(["Contato", sol["contato"]])
        blocks.append({"heading": "Solicitante", "rows": sol_rows})

    resp_rows: list[list[str]] = []
    for i, rt in enumerate(rts, start=1):
        prefix = "Responsável técnico" if len(rts) == 1 else f"Responsável técnico {i}"
        resp_rows.append([prefix, rt["nome"] or "—"])
        if rt.get("profissao"):
            resp_rows.append(["Profissão / título", rt["profissao"]])
        resp_rows.append(["CREA", rt.get("crea") or "não informado"])
        resp_rows.append(["ART", rt.get("art") or "não informada — preencher antes do protocolo"])
        if rt.get("email") or rt.get("telefone"):
            contact = " · ".join(
                x for x in (rt.get("email"), rt.get("telefone")) if x
            )
            if contact:
                resp_rows.append(["Contato do RT", contact])
    if imgs:
        label = "Responsável pelas fotos" if len(imgs) == 1 else "Responsáveis pelas fotos"
        resp_rows.append([label, ", ".join(p["nome"] for p in imgs)])
    if resp_rows:
        blocks.append({"heading": "Responsabilidade técnica (CREA / ART)", "rows": resp_rows})

    return {
        "titulo": str(content.get("titulo") or "Laudo Técnico de Vistoria"),
        "subtitulo": str(content.get("subtitulo") or "").strip(),
        "blocks": blocks,
        "compliance_note": str(content.get("compliance_note") or "").strip(),
        "generated_at": generated_at,
        "numero_laudo": str(content.get("numero_laudo") or "").strip(),
    }


def solicitante_table(content: dict[str, Any]) -> dict[str, Any] | None:
    sol = normalize_solicitante(content.get("solicitante"))
    if not solicitante_has_data(sol):
        return None
    rows = []
    if sol["empresa"]:
        rows.append(["Empresa / solicitante", sol["empresa"]])
    if sol["cnpj"]:
        rows.append(["CNPJ", sol["cnpj"]])
    if sol["endereco"]:
        rows.append(["Endereço", sol["endereco"]])
    if sol["contato"]:
        rows.append(["Contato", sol["contato"]])
    return {
        "caption": "Dados do solicitante",
        "headers": ["Campo", "Informação"],
        "rows": rows,
    }


def format_coordinates_label(lat: float | None, lon: float | None, fallback: str = "") -> str:
    if lat is None or lon is None:
        return fallback or "—"
    return f"{lat:.6f}, {lon:.6f} (WGS84)"


def inject_coordinates_into_object_tables(
    content: dict[str, Any],
    *,
    latitude: float | None,
    longitude: float | None,
    label: str | None = None,
) -> dict[str, Any]:
    """Insere/atualiza linha de Coordenadas na ficha técnica (e local_data se 2 colunas)."""
    import copy

    out = copy.deepcopy(content) if content else {}
    coord_label = label or format_coordinates_label(latitude, longitude)
    if not coord_label or coord_label == "—":
        return out

    def _upsert_rows(rows: list) -> list:
        new_rows: list = []
        found = False
        for row in rows or []:
            if not isinstance(row, (list, tuple)) or not row:
                continue
            key = str(row[0] or "").strip().lower()
            if "coordenad" in key or key in {"gps", "lat/long", "lat/lon", "wgs84"}:
                val = list(row)
                if len(val) < 2:
                    val.append(coord_label)
                else:
                    val[1] = coord_label
                new_rows.append(val)
                found = True
            else:
                new_rows.append(list(row))
        if not found:
            new_rows.append(["Coordenadas", coord_label])
        return new_rows

    for chapter in out.get("chapters") or []:
        cid = str(chapter.get("id") or "").lower()
        title_l = str(chapter.get("title") or "").lower()
        is_ficha = cid == "ficha_tecnica" or "ficha técnica" in title_l or "ficha tecnica" in title_l
        is_local = cid == "local_data" or ("local" in title_l and "data" in title_l)
        if not (is_ficha or is_local):
            continue
        tables = list(chapter.get("tables") or [])
        if not tables and is_ficha:
            tables = [
                {
                    "caption": "Dados técnicos do objeto",
                    "headers": ["Parâmetro", "Descrição"],
                    "rows": [["Coordenadas", coord_label]],
                }
            ]
        else:
            updated = []
            for table in tables:
                t = dict(table)
                headers = [str(h).lower() for h in (t.get("headers") or [])]
                if len(headers) == 2 or not headers:
                    t["rows"] = _upsert_rows(list(t.get("rows") or []))
                updated.append(t)
            tables = updated
        chapter["tables"] = tables

    geo = dict(out.get("georreferencia") or {})
    if latitude is not None:
        geo["latitude"] = latitude
    if longitude is not None:
        geo["longitude"] = longitude
    geo["label"] = coord_label
    out["georreferencia"] = geo
    return out


def build_photographic_presentation(content: dict[str, Any]) -> str:
    """
    Texto de apresentação do laudo sob o título do relatório fotográfico.
    Não menciona 'imagem anexo' nem instruções de diagramação.
    """
    titulo = str(content.get("titulo") or "laudo técnico de vistoria").strip()
    numero = str(content.get("numero_laudo") or "").strip()
    objeto = str(content.get("objeto") or "o objeto vistoriado").strip()
    local = str(content.get("local") or "o local da diligência").strip()
    data = str(content.get("data_vistoria") or "a data da vistoria").strip()
    tipo = str(content.get("tipo_vistoria") or "vistoria técnica").strip()
    photos = content.get("photographic_report") or []
    n_photos = len(photos) if isinstance(photos, list) else 0

    lead = f"O presente relatório fotográfico integra o {titulo}"
    if numero:
        lead += f", registrado sob o nº {numero}"
    lead += (
        f", elaborado a partir da {tipo} realizada em {local}, "
        f"na data de {data}, tendo por objeto {objeto}."
    )

    chunks = [lead]
    responsaveis = normalize_parties(content.get("responsaveis_imagens"))
    nomes = [p["nome"] for p in responsaveis if p.get("nome")]
    if nomes:
        if len(nomes) == 1:
            chunks.append(f"As fotografias foram produzidas sob responsabilidade de {nomes[0]}.")
        else:
            chunks.append(
                "As fotografias foram produzidas sob responsabilidade de "
                + ", ".join(nomes[:-1])
                + f" e {nomes[-1]}."
            )
    else:
        chunks.append(
            "As fotografias a seguir documentam as condições observadas in loco durante a diligência."
        )
    if n_photos:
        chunks.append(f"Total de registros fotográficos: {n_photos}.")
    return " ".join(chunks)
