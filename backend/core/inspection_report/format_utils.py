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
    """Garante prefixo numérico no título do capítulo (ex.: '3. Local e Data')."""
    t = (title or "").strip()
    if not t:
        return f"{number}."
    # Já começa com número (1. / 1 / 16.)
    import re

    if re.match(r"^\d+[\.\)]\s*", t):
        return t
    return f"{number}. {t}"


def build_body_sections(content: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Monta seções do corpo em ordem técnica, com numeração contínua.
    Evita duplicar capa/sumário/fotográfico e formata indicadores.
    """
    sections: list[dict[str, Any]] = []
    n = 0

    def _push(title: str, *, paragraphs=None, tables=None, charts=None, chapter_id: str = ""):
        nonlocal n
        n += 1
        sections.append(
            {
                "number": n,
                "chapter_id": chapter_id,
                "title": ensure_chapter_number(title, n),
                "paragraphs": list(paragraphs or []),
                "tables": list(tables or []),
                "charts": list(charts or []),
            }
        )

    seen_ids: set[str] = set()

    sol_table = solicitante_table(content)
    if sol_table:
        _push("Dados do solicitante", tables=[sol_table], chapter_id="solicitante")
        seen_ids.add("solicitante")

    for chapter in content.get("chapters") or []:
        cid = str(chapter.get("id") or "").lower().strip()
        title = str(chapter.get("title") or chapter.get("id") or "Capítulo")
        title_l = title.lower()
        if cid in _SKIP_CHAPTER_IDS:
            continue
        if "capa" in title_l or "sumário" in title_l or "sumario" in title_l:
            continue
        if "relatório fotográfico" in title_l or "relatorio fotografico" in title_l:
            continue
        if cid:
            seen_ids.add(cid)
        _push(
            title,
            paragraphs=chapter.get("paragraphs"),
            tables=chapter.get("tables"),
            charts=chapter.get("charts"),
            chapter_id=cid,
        )

    # Blocos estruturados extras (só se não houver capítulo equivalente)
    pathologies = content.get("pathologies") or []
    if pathologies and "patologias" not in seen_ids and "diagnostico" not in seen_ids:
        rows = [
            [
                p.get("code") or "—",
                p.get("name") or "—",
                p.get("location") or "—",
                p.get("severity") or "—",
                f"{p.get('score') or '—'}/5",
                p.get("solution") or "—",
                p.get("urgency") or "—",
            ]
            for p in pathologies
        ]
        paras = []
        for p in pathologies:
            paras.append(
                f"{p.get('code') or ''} {p.get('name')}: {p.get('description') or ''} "
                f"Causa provável: {p.get('cause') or '—'}. "
                f"Solução: {p.get('solution') or '—'}."
            )
        _push(
            "Síntese de patologias",
            paragraphs=paras,
            tables=[
                {
                    "caption": "Quadro resumo de patologias",
                    "headers": [
                        "Código",
                        "Patologia",
                        "Local",
                        "Severidade",
                        "Score",
                        "Solução",
                        "Urgência",
                    ],
                    "rows": rows,
                }
            ],
        )

    indicators = content.get("indicators") or {}
    photos = content.get("photographic_report") or []
    # Seção analítica (cards + tabelas + gráficos) — sempre que houver dados
    if (pathologies or photos) and "analytics" not in seen_ids:
        from core.inspection_report.analytics import build_pathology_analytics

        analytics = build_pathology_analytics(content)
        _push(
            "Análise quantitativa e qualitativa das patologias",
            paragraphs=analytics.get("summary_paragraphs"),
            tables=analytics.get("tables"),
            charts=[],  # gráficos PNG tratados via campo extra
        )
        sections[-1]["cards"] = analytics.get("cards") or []
        sections[-1]["chart_images"] = analytics.get("charts") or []
        seen_ids.add("analytics")
        seen_ids.add("indicadores")
    elif indicators and "indicadores" not in seen_ids:
        dist_txt = format_severity_distribution(indicators.get("severity_distribution"))
        _push(
            "Indicadores de comprometimento",
            paragraphs=[
                f"Índice de comprometimento: {indicators.get('compromise_index_pct', '—')}%. "
                f"Índice de conservação aparente: {indicators.get('conservation_index_pct', '—')}%. "
                f"Distribuição por gravidade: {dist_txt}."
            ],
            tables=[
                {
                    "caption": "Distribuição por gravidade",
                    "headers": ["Gravidade", "Quantidade"],
                    "rows": _dist_rows(indicators.get("severity_distribution")),
                }
            ]
            if indicators.get("severity_distribution")
            else [],
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
        )

    conclusions = content.get("conclusions") or []
    if conclusions and "conclusao" not in seen_ids and "conclusões" not in " ".join(seen_ids):
        _push("Conclusões e recomendações", paragraphs=[str(c) for c in conclusions])

    refs = content.get("references") or []
    if refs and "referencias" not in seen_ids and "referências" not in " ".join(seen_ids):
        _push("Referências", paragraphs=[str(r) for r in refs])

    return sections


def build_sumario_entries(content: dict[str, Any]) -> list[dict[str, str]]:
    """
    Monta o sumário institucional a partir das seções reais do corpo.
    Inclui responsáveis técnicos (se houver) e o relatório fotográfico.
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

    photo_num = (sections[-1]["number"] + 1) if sections else 1
    entries.append(
        {
            "label": f"{photo_num}. Relatório fotográfico",
            "chapter_id": "fotografico",
        }
    )
    return [e for e in entries if (e.get("label") or "").strip()]


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
        # Insere após capa, se existir; senão no início
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


def header_meta_lines(content: dict[str, Any], *, generated_at: str) -> list[str]:
    """Linhas à direita do cabeçalho."""
    lines = [
        f"Nº: {content.get('numero_laudo') or '—'}",
        f"Objeto: {(content.get('objeto') or '—')[:48]}",
        f"Vistoria: {content.get('data_vistoria') or '—'}",
        f"Gerado em: {generated_at}",
    ]
    return lines


def normalize_party(raw: Any) -> dict[str, str] | None:
    """Normaliza responsável técnico / de imagens."""
    if not isinstance(raw, dict):
        return None
    nome = str(raw.get("nome") or "").strip()
    if not nome:
        return None
    pid = str(raw.get("id") or "").strip()
    return {
        "id": pid or nome.lower().replace(" ", "_")[:40],
        "nome": nome[:200],
        "profissao": str(raw.get("profissao") or "").strip()[:120],
        "crea": str(raw.get("crea") or "").strip()[:80],
        "art": str(raw.get("art") or "").strip()[:80],
        "email": str(raw.get("email") or "").strip()[:160],
        "telefone": str(raw.get("telefone") or "").strip()[:60],
    }


def normalize_parties(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in raw:
        party = normalize_party(item)
        if party:
            out.append(party)
    return out


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
        bits = [rt["nome"]]
        if rt.get("profissao"):
            bits.append(rt["profissao"])
        if rt.get("crea"):
            bits.append(f"CREA: {rt['crea']}")
        if rt.get("art"):
            bits.append(f"ART: {rt['art']}")
        label = "Responsável técnico" if len(rts) == 1 else f"Responsável técnico {i}"
        resp_rows.append([label, " — ".join(bits)])
    if imgs:
        label = "Responsável pelas fotos" if len(imgs) == 1 else "Responsáveis pelas fotos"
        resp_rows.append([label, ", ".join(p["nome"] for p in imgs)])
    if resp_rows:
        blocks.append({"heading": "Responsabilidade técnica", "rows": resp_rows})

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
