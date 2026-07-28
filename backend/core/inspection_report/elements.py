"""L11 — Inventário estruturado de elementos por tipología de laudo.

Catálogos canônicos (OAE, erosão, edificação…) usados no prompt do Gemini
e no pós-processamento para garantir vínculo elemento ↔ patologia ↔ foto.
"""

from __future__ import annotations

from typing import Any

# element_id → (grupo, nome, descrição curta)
ElementDef = tuple[str, str, str]

OAE_ELEMENTS: list[tuple[str, str, str, str]] = [
    # (id, grupo, nome, descricao)
    ("sup_tabuleiro", "Superestrutura", "Tabuleiro / laje", "Laje de rolamento e tabuleiro"),
    ("sup_longarina", "Superestrutura", "Longarinas / vigas principais", "Vigas longitudinais de concreto ou aço"),
    ("sup_transversina", "Superestrutura", "Transversinas", "Vigas transversais / contraventamento"),
    ("sup_laje", "Superestrutura", "Laje estrutural", "Laje de concreto armado/protendido"),
    ("mes_pilar", "Mesoestrutura", "Pilares / pilares-estaca", "Elementos de apoio intermediários"),
    ("mes_cortina", "Mesoestrutura", "Cortinas / encontros intermediários", "Cortinas e encontros mesoesstruturais"),
    ("mes_apoio", "Mesoestrutura", "Aparelhos de apoio", "Neoprene, metálicos, pot, elastoméricos"),
    ("inf_encontro", "Infraestrutura", "Encontros", "Encontros de extremidade"),
    ("inf_fundacao", "Infraestrutura", "Fundações", "Sapatas, tubulões, estacas, blocos"),
    ("inf_margem", "Infraestrutura", "Proteção de margens / erosão", "Enrocamento, gabiões, solapamento"),
    ("acs_junta", "Acessórios", "Juntas de dilatação", "Juntas do tabuleiro"),
    ("acs_drenagem", "Acessórios", "Drenagem da pista", "Drenos, pingadeiras, descidas"),
    ("acs_guarda", "Acessórios", "Guarda-corpo / barreiras", "Guarda-corpos e barreiras de contenção"),
    ("acs_pavimento", "Acessórios", "Pavimento / revestimento", "Capa asfáltica ou concreto"),
    ("acs_sinalizacao", "Acessórios", "Sinalização / iluminação", "Sinalização vertical/horizontal e iluminação"),
]

EROSAO_ELEMENTS: list[tuple[str, str, str, str]] = [
    ("ero_talude", "Terreno", "Talude / encosta", "Superfície inclinada sujeita a erosão"),
    ("ero_vocoroca", "Terreno", "Voçoroca / ravina", "Canal erosivo concentrado"),
    ("ero_pe", "Terreno", "Pé de talude / base", "Zona de solapamento na base"),
    ("ero_crista", "Terreno", "Crista / topo", "Topo do talude e bordo"),
    ("ero_drenagem", "Drenagem", "Drenagem superficial", "Canaletas, dissipadores, descidas"),
    ("ero_protecao", "Proteção", "Proteção vegetal / biomanta", "Cobertura vegetal e geotêxteis"),
    ("ero_obra", "Obras", "Obra de contenção existente", "Muros, gabiões, terra armada"),
    ("ero_infra", "Interferências", "Infraestrutura ameaçada", "Vias, redes, edificações a jusante"),
]

EDIFICACAO_ELEMENTS: list[tuple[str, str, str, str]] = [
    ("edi_fund", "Estrutura", "Fundações", "Sapatas, radiers, estacas"),
    ("edi_pilares", "Estrutura", "Pilares", "Pilares de concreto/aço"),
    ("edi_vigas", "Estrutura", "Vigas", "Vigas principais e secundárias"),
    ("edi_lajes", "Estrutura", "Lajes", "Lajes de piso e cobertura"),
    ("edi_alvenaria", "Vedação", "Alvenaria / paredes", "Paredes de vedação e estruturais"),
    ("edi_fachada", "Vedação", "Fachadas / revestimentos", "Revestimentos externos"),
    ("edi_impermeab", "Impermeabilização", "Impermeabilização / cobertura", "Telhados, lajes impermeabilizadas"),
    ("edi_instal", "Instalações", "Instalações aparentes", "Hidráulica, elétrica, HVAC aparentes"),
    ("edi_escada", "Circulação", "Escadas / rampas", "Circulações verticais"),
]

BARRAGEM_ELEMENTS: list[tuple[str, str, str, str]] = [
    ("bar_macico", "Barragem", "Maciço / corpo", "Enrocamento ou terra"),
    ("bar_fund", "Barragem", "Fundação", "Contato maciço-fundação"),
    ("bar_extravasor", "Hidráulica", "Extravasor / vertedouro", "Canal de fuga e soleira"),
    ("bar_tomada", "Hidráulica", "Tomada d'água", "Torre/tomada e comportas"),
    ("bar_drenos", "Auscultação", "Drenos / filtros", "Sistema de drenagem interna"),
    ("bar_instrument", "Auscultação", "Instrumentação", "Piezômetros, marcos, vazões"),
    ("bar_jusante", "Entorno", "Pé de jusante / ombreiras", "Zona de jusante e ombreiras"),
]

DRENAGEM_ELEMENTS: list[tuple[str, str, str, str]] = [
    ("dre_meiofio", "Superficial", "Meio-fio / sarjeta", "Coleta longitudinal"),
    ("dre_boca", "Superficial", "Bocas de lobo / caixas", "Captação pontual"),
    ("dre_galeria", "Subterrânea", "Galerias / tubulações", "Condutos enterrados"),
    ("dre_dissip", "Dissipação", "Dissipadores / descidas", "Controle de energia"),
    ("dre_bacia", "Bacia", "Bacia de contribuição", "Área de drenagem"),
]

PAVIMENTO_ELEMENTS: list[tuple[str, str, str, str]] = [
    ("pav_revest", "Pavimento", "Revestimento", "Capa asfáltica ou concreto"),
    ("pav_base", "Pavimento", "Base / sub-base", "Camadas granulares ou tratadas"),
    ("pav_subleito", "Pavimento", "Subleito", "Solo de fundação do pavimento"),
    ("pav_acost", "Plataforma", "Acostamento / bordo", "Bordos e acostamentos"),
    ("pav_dren", "Drenagem", "Drenagem do pavimento", "Drenos laterais e transversais"),
]

MURO_ELEMENTS: list[tuple[str, str, str, str]] = [
    ("mur_corpo", "Estrutura", "Corpo do muro", "Face e corpo estrutural"),
    ("mur_fund", "Estrutura", "Fundação do muro", "Base e fundação"),
    ("mur_dren", "Drenagem", "Drenagem interna", "Barbacãs, geotêxtil, drenos"),
    ("mur_aterro", "Geotecnia", "Aterro / solo contido", "Maciço a montante"),
    ("mur_junta", "Detalhes", "Juntas / encontros", "Juntas de dilatação e encontros"),
]

GERAL_ELEMENTS: list[tuple[str, str, str, str]] = [
    ("ger_estrutura", "Geral", "Estrutura principal", "Sistema estrutural principal"),
    ("ger_fundacao", "Geral", "Fundação", "Sistema de fundação"),
    ("ger_vedacao", "Geral", "Vedações / revestimentos", "Vedações e acabamentos"),
    ("ger_drenagem", "Geral", "Drenagem", "Dispositivos de drenagem"),
    ("ger_entorno", "Geral", "Entorno / acessos", "Acessos e entorno imediato"),
]

ELEMENTS_BY_SLUG: dict[str, list[tuple[str, str, str, str]]] = {
    "pontes": OAE_ELEMENTS,
    "viadutos": OAE_ELEMENTS,
    "erosao": EROSAO_ELEMENTS,
    "edificacao": EDIFICACAO_ELEMENTS,
    "barragem": BARRAGEM_ELEMENTS,
    "drenagem": DRENAGEM_ELEMENTS,
    "pavimentacao": PAVIMENTO_ELEMENTS,
    "muro_contencao": MURO_ELEMENTS,
    "geral": GERAL_ELEMENTS,
}


def elements_for_slug(slug: str | None) -> list[dict[str, str]]:
    key = (slug or "geral").strip().lower()
    rows = ELEMENTS_BY_SLUG.get(key) or GERAL_ELEMENTS
    return [
        {"id": eid, "group": group, "name": name, "description": desc}
        for eid, group, name, desc in rows
    ]


def element_catalog_prompt_block(slug: str | None) -> str:
    elems = elements_for_slug(slug)
    lines = [
        "════════════════════════════════════════",
        "INVENTÁRIO DE ELEMENTOS (L11 — OBRIGATÓRIO)",
        "════════════════════════════════════════",
        "Preencha `element_inventory` com TODOS os elementos aplicáveis ao objeto.",
        "Para cada patologia e foto, use `element_id` do catálogo abaixo.",
        "Status do elemento: íntegro | observação | degradado | crítico | não_inspecionado.",
        "",
        "CATÁLOGO:",
    ]
    current_group = ""
    for e in elems:
        if e["group"] != current_group:
            current_group = e["group"]
            lines.append(f"\n[{current_group}]")
        lines.append(f"- {e['id']}: {e['name']} — {e['description']}")
    lines.extend(
        [
            "",
            "Formato element_inventory[]:",
            '{"element_id":"sup_longarina","name":"Longarinas","group":"Superestrutura",'
            '"status":"degradado","condition_note":"…","pathology_refs":["P01"],'
            '"photo_refs":[1,3],"dnit_note":2}',
        ]
    )
    return "\n".join(lines)


def _match_element_id(text: str, slug: str | None) -> str | None:
    t = (text or "").lower()
    if not t:
        return None
    # Aliases comuns → id
    aliases: list[tuple[str, str]] = [
        ("longarina", "sup_longarina"),
        ("viga principal", "sup_longarina"),
        ("transversina", "sup_transversina"),
        ("tabuleiro", "sup_tabuleiro"),
        ("laje", "sup_laje"),
        ("pilar", "mes_pilar"),
        ("aparelho de apoio", "mes_apoio"),
        ("neoprene", "mes_apoio"),
        ("encontro", "inf_encontro"),
        ("fundação", "inf_fundacao"),
        ("fundacao", "inf_fundacao"),
        ("erosão", "inf_margem"),
        ("erosao", "inf_margem"),
        ("solapamento", "inf_margem"),
        ("junta", "acs_junta"),
        ("drenagem", "acs_drenagem"),
        ("guarda-corpo", "acs_guarda"),
        ("guarda corpo", "acs_guarda"),
        ("talude", "ero_talude"),
        ("voçoroca", "ero_vocoroca"),
        ("vocoroca", "ero_vocoroca"),
        ("fachada", "edi_fachada"),
        ("alvenaria", "edi_alvenaria"),
        ("maciço", "bar_macico"),
        ("vertedouro", "bar_extravasor"),
        ("extravasor", "bar_extravasor"),
        ("pavimento", "pav_revest"),
        ("muro", "mur_corpo"),
    ]
    catalog_ids = {e["id"] for e in elements_for_slug(slug)}
    for needle, eid in aliases:
        if needle in t and eid in catalog_ids:
            return eid
    # match by name fragment
    for e in elements_for_slug(slug):
        name_l = e["name"].lower()
        if name_l[:6] in t or any(w in t for w in name_l.split() if len(w) > 4):
            return e["id"]
    return None


def ensure_element_inventory(
    content: dict[str, Any],
    *,
    slug: str | None,
) -> dict[str, Any]:
    """
    Garante `element_inventory` com catálogo da tipología, status derivado
    das patologias e vínculos pathology_refs / photo_refs.
    """
    out = dict(content or {})
    catalog = elements_for_slug(slug)
    by_id = {e["id"]: e for e in catalog}

    existing = out.get("element_inventory")
    inventory: dict[str, dict[str, Any]] = {}
    if isinstance(existing, list):
        for raw in existing:
            if not isinstance(raw, dict):
                continue
            eid = str(raw.get("element_id") or raw.get("id") or "").strip()
            if not eid:
                # tenta casar pelo nome
                eid = _match_element_id(str(raw.get("name") or ""), slug) or ""
            if not eid or eid not in by_id:
                continue
            inventory[eid] = {
                "element_id": eid,
                "name": str(raw.get("name") or by_id[eid]["name"]),
                "group": str(raw.get("group") or by_id[eid]["group"]),
                "status": str(raw.get("status") or "não_inspecionado").lower(),
                "condition_note": str(raw.get("condition_note") or raw.get("note") or ""),
                "pathology_refs": list(raw.get("pathology_refs") or []),
                "photo_refs": list(raw.get("photo_refs") or []),
                "dnit_note": raw.get("dnit_note"),
            }

    # Seed todos os elementos do catálogo
    for e in catalog:
        if e["id"] not in inventory:
            inventory[e["id"]] = {
                "element_id": e["id"],
                "name": e["name"],
                "group": e["group"],
                "status": "não_inspecionado",
                "condition_note": "",
                "pathology_refs": [],
                "photo_refs": [],
                "dnit_note": None,
            }

    # Vincular patologias
    for p in out.get("pathologies") or []:
        if not isinstance(p, dict):
            continue
        code = str(p.get("code") or p.get("codigo") or "").strip()
        eid = str(p.get("element_id") or "").strip()
        if not eid or eid not in inventory:
            eid = _match_element_id(
                " ".join(
                    str(p.get(k) or "")
                    for k in ("element", "location", "name", "description")
                ),
                slug,
            ) or ""
        if not eid or eid not in inventory:
            continue
        p["element_id"] = eid
        if code and code not in inventory[eid]["pathology_refs"]:
            inventory[eid]["pathology_refs"].append(code)
        sev = str(p.get("severity") or "").lower()
        status = inventory[eid]["status"]
        if "crít" in sev or "crit" in sev:
            inventory[eid]["status"] = "crítico"
        elif ("alt" in sev) and status not in ("crítico",):
            inventory[eid]["status"] = "degradado"
        elif status in ("não_inspecionado", "íntegro", "integro"):
            inventory[eid]["status"] = "observação"

    # Vincular fotos
    for ph in out.get("photographic_report") or []:
        if not isinstance(ph, dict):
            continue
        try:
            num = int(ph.get("photo_number") or 0)
        except (TypeError, ValueError):
            num = 0
        if not num:
            continue
        eid = str(ph.get("element_id") or "").strip()
        if not eid or eid not in inventory:
            eid = _match_element_id(
                " ".join(str(ph.get(k) or "") for k in ("title", "description", "legend")),
                slug,
            ) or ""
        if eid and eid in inventory:
            ph["element_id"] = eid
            if num not in inventory[eid]["photo_refs"]:
                inventory[eid]["photo_refs"].append(num)
            # Foto vinculada ⇒ elemento foi inspecionado visualmente
            st = str(inventory[eid].get("status") or "").lower()
            if st in ("não_inspecionado", "nao_inspecionado", "íntegro", "integro"):
                inventory[eid]["status"] = "observação"

    # Ordenação por grupo do catálogo
    ordered = [inventory[e["id"]] for e in catalog if e["id"] in inventory]
    out["element_inventory"] = ordered
    return out


def element_inventory_table(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    # Export: só elementos com evidência (patologia, foto ou status ≠ não_inspecionado)
    rows_src = [
        e
        for e in inventory
        if isinstance(e, dict)
        and (
            e.get("pathology_refs")
            or e.get("photo_refs")
            or str(e.get("status") or "").lower()
            not in ("não_inspecionado", "nao_inspecionado")
        )
    ]
    if not rows_src:
        rows_src = [e for e in inventory if isinstance(e, dict)][:8]

    return {
        "caption": "Inventário estruturado de elementos (NBR 9452 / tipología do objeto)",
        "headers": [
            "ID",
            "Grupo",
            "Elemento",
            "Status",
            "Nota DNIT",
            "Patologias",
            "Fotos",
            "Observação",
        ],
        "rows": [
            [
                str(e.get("element_id") or "—"),
                e.get("group") or "—",
                e.get("name") or "—",
                e.get("status") or "—",
                str(e.get("dnit_note") if e.get("dnit_note") is not None else "—"),
                ", ".join(str(x) for x in (e.get("pathology_refs") or [])) or "—",
                ", ".join(str(x) for x in (e.get("photo_refs") or [])) or "—",
                (e.get("condition_note") or "—")[:120],
            ]
            for e in rows_src
        ],
    }
