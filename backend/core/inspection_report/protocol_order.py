"""Ordem canônica de capítulos para laudo de protocolo / CREA / perícia.

Fonte única usada por `build_body_sections` e pelo enrichment pós-Gemini.
"""

from __future__ import annotations

from typing import Any

# Prioridade crescente = aparece depois. Capítulos sem match usam 500+.
_CHAPTER_PRIORITY: list[tuple[int, frozenset[str], tuple[str, ...]]] = [
    # (priority, ids exatos, substrings no título)
    (10, frozenset({"solicitante", "dados_solicitante"}), ("dados do solicitante",)),
    (20, frozenset({"solicitacao", "solicitação"}), ("solicitação", "solicitacao")),
    (30, frozenset({"assunto"}), ("assunto",)),
    (40, frozenset({"local", "local_data", "local_e_data"}), ("local e data", "local e data")),
    (50, frozenset({"objetivo"}), ("objetivo",)),
    (60, frozenset({"responsabilidade", "responsabilidade_tecnica"}), ("responsabilidade técnica",)),
    (70, frozenset({"identificacao", "historico", "identificacao_historico"}), ("identificação", "histórico")),
    (80, frozenset({"ficha_tecnica", "concepcao", "concepção"}), ("ficha técnica", "concepção estrutural")),
    # L11 → patologias → L12 → L10 → L13
    (100, frozenset({"inventario_elementos", "inventario"}), ("inventário estruturado", "inventario estruturado")),
    (110, frozenset({"patologias", "diagnostico", "diagnóstico"}), ("patologia", "diagnóstico", "diagnostico")),
    (120, frozenset({"metrologia"}), ("metrológ", "metrolog")),
    (130, frozenset({"classificacao_dnit", "classificacao", "parecer", "parecer_tecnico"}), (
        "classificação estrutural",
        "classificacao estrutural",
        "parecer técnico",
        "parecer tecnico",
        "notas dnit",
    )),
    (140, frozenset({"interdicao", "ato_interdicao", "recomendacao_interdicao"}), (
        "interdição",
        "interdicao",
        "ato de interdição",
    )),
    (150, frozenset({"ensaios_instrumentados", "ensaios"}), ("ensaios instrumentados", "ensaio instrumentado")),
    (160, frozenset({"plano_correcao", "plano", "recuperacao"}), ("plano de correção", "plano de correcao", "plano de")),
    (170, frozenset({"cronograma"}), ("cronograma",)),
    (180, frozenset({"analytics", "indicadores", "gravidade", "ranking"}), (
        "análise quantitativa",
        "analise quantitativa",
        "indicadores",
        "ranking de criticidade",
        "tabela de gravidade",
        "cards-resumo",
        "cards resumo",
    )),
    (190, frozenset({"conclusao", "conclusões", "conclusoes"}), ("conclusão", "conclusao", "conclusões")),
    (200, frozenset({"referencias", "referências"}), ("referência", "referencia")),
]

# Capítulos Gemini redundantes quando o enrichment já gerou o bloco oficial
_DEDUPE_WHEN_OFFICIAL: dict[str, frozenset[str]] = {
    "classificacao_dnit": frozenset({"parecer", "parecer_tecnico"}),
    "analytics": frozenset({"indicadores", "gravidade", "ranking", "cards", "cards_resumo"}),
}


def strip_chapter_number(title: str) -> str:
    import re

    t = (title or "").strip()
    return re.sub(r"^\d+[\.\)]\s*", "", t).strip()


def chapter_priority(cid: str, title: str) -> int:
    cid_l = (cid or "").lower().strip()
    title_l = strip_chapter_number(title or "").lower()
    for pri, ids, needles in _CHAPTER_PRIORITY:
        if cid_l and cid_l in ids:
            return pri
        if any(n in title_l for n in needles):
            return pri
    return 500


def is_analytics_like(cid: str, title: str) -> bool:
    return chapter_priority(cid, title) == 180


def is_classification_like(cid: str, title: str) -> bool:
    return chapter_priority(cid, title) == 130


def is_skip_chapter(cid: str, title: str) -> bool:
    cid_l = (cid or "").lower().strip()
    title_l = (title or "").lower()
    if cid_l in {
        "capa",
        "sumario",
        "cover",
        "fotografico",
        "relatorio_fotografico",
        "photo",
        "indice_fotografico",
    }:
        return True
    if "capa" in title_l or "sumário" in title_l or "sumario" in title_l:
        return True
    if "relatório fotográfico" in title_l or "relatorio fotografico" in title_l:
        return True
    return False


def normalize_chapter_title(cid: str, title: str) -> str:
    """Remove jargão de UI e unifica títulos institucionais."""
    bare = strip_chapter_number(title)
    low = bare.lower()
    if "cards" in low and ("resumo" in low or "indicador" in low):
        return "Indicadores de conservação e criticidade"
    if is_classification_like(cid, bare) and "parecer" in low:
        return "Classificação e parecer técnico (NBR 9452 / DNIT)"
    if cid == "classificacao_dnit" or (
        "classificação estrutural" in low or "classificacao estrutural" in low
    ):
        return "Classificação e parecer técnico (NBR 9452 / DNIT)"
    if cid == "interdicao" or "interdi" in low:
        return "Ato de interdição e restrição de uso"
    if cid == "ensaios_instrumentados":
        return "Ensaios instrumentados prioritários"
    if cid == "metrologia":
        return "Campos metrológicos tipados"
    if cid == "inventario_elementos":
        return "Inventário estruturado de elementos"
    return bare or "Capítulo"


def reorder_chapters_for_protocol(chapters: list[Any]) -> list[dict[str, Any]]:
    """
    Ordena capítulos na sequência de protocolo e remove duplicatas
    (parecer vs classificação; cards/indicadores vs analytics).
    """
    items: list[dict[str, Any]] = []
    for raw in chapters or []:
        if not isinstance(raw, dict):
            continue
        cid = str(raw.get("id") or "").lower().strip()
        title = str(raw.get("title") or raw.get("id") or "Capítulo")
        if is_skip_chapter(cid, title):
            continue
        items.append(dict(raw))

    # Detectar oficiais
    has_class = any(
        str(c.get("id") or "").lower() == "classificacao_dnit"
        or is_classification_like(str(c.get("id") or ""), str(c.get("title") or ""))
        for c in items
    )
    has_analytics_official = any(
        str(c.get("id") or "").lower() == "analytics" for c in items
    )

    # Fundir parecer Gemini na classificação oficial
    parecer_paras: list[str] = []
    parecer_tables: list[Any] = []
    kept: list[dict[str, Any]] = []
    seen_bucket: set[int] = set()
    analytics_kept = False
    class_kept = False

    for c in items:
        cid = str(c.get("id") or "").lower().strip()
        title = str(c.get("title") or "")
        pri = chapter_priority(cid, title)

        # Parecer separado → acumular para merge
        if has_class and cid in ("parecer", "parecer_tecnico"):
            parecer_paras.extend(str(p) for p in (c.get("paragraphs") or []) if p)
            parecer_tables.extend(c.get("tables") or [])
            continue
        if has_class and pri == 130 and cid != "classificacao_dnit" and "parecer" in title.lower():
            parecer_paras.extend(str(p) for p in (c.get("paragraphs") or []) if p)
            parecer_tables.extend(c.get("tables") or [])
            continue

        # Dedupe analytics-like
        if pri == 180:
            if analytics_kept or (has_analytics_official and cid != "analytics"):
                # Preferir um único bloco; se já temos analytics id, pular indicadores/cards
                if cid != "analytics" and analytics_kept:
                    continue
                if has_analytics_official and cid != "analytics":
                    continue
            if analytics_kept:
                continue
            analytics_kept = True
            c = dict(c)
            c["id"] = "analytics"
            c["title"] = normalize_chapter_title("analytics", title)
            kept.append(c)
            continue

        # Uma única classificação
        if pri == 130:
            if class_kept and cid != "classificacao_dnit":
                continue
            if class_kept and cid == "classificacao_dnit":
                # substituir a anterior
                kept = [x for x in kept if chapter_priority(str(x.get("id") or ""), str(x.get("title") or "")) != 130]
            class_kept = True
            c = dict(c)
            c["id"] = "classificacao_dnit"
            c["title"] = normalize_chapter_title("classificacao_dnit", title)
            if parecer_paras:
                paras = list(c.get("paragraphs") or [])
                for p in parecer_paras:
                    if p not in paras:
                        paras.append(p)
                c["paragraphs"] = paras
                parecer_paras = []
            if parecer_tables:
                tables = list(c.get("tables") or [])
                tables.extend(parecer_tables)
                c["tables"] = tables
                parecer_tables = []
            kept.append(c)
            continue

        c = dict(c)
        c["title"] = normalize_chapter_title(cid, title)
        kept.append(c)

    # Se sobrou parecer e não havia classificação, emite como classificação
    if parecer_paras and not class_kept:
        kept.append(
            {
                "id": "classificacao_dnit",
                "title": "Classificação e parecer técnico (NBR 9452 / DNIT)",
                "paragraphs": parecer_paras,
                "tables": parecer_tables,
            }
        )

    kept.sort(
        key=lambda c: (
            chapter_priority(str(c.get("id") or ""), str(c.get("title") or "")),
            str(c.get("id") or ""),
        )
    )
    return kept


def soft_break_id(text: str) -> str:
    """Retorna o ID sem caracteres invisíveis (ZWSP quebrava em ■ no PDF/Word)."""
    return str(text or "")
