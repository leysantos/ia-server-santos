"""Pacotes normativos curados — gap analysis por disciplina/agente."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from core.agent_registry import DISCIPLINE_TO_AGENT
from core.agents.base_agent_intelligent import DISCIPLINE_NBRS
from core.knowledge.disciplines import DISCIPLINE_TO_SLUG
from memory.nbr_catalog import NBR_DISCIPLINE_MAP

_NBR_CODE_RE = re.compile(r"(\d{4,5})")


@dataclass(frozen=True)
class NormPackItem:
    nbr_code: str
    title: str
    discipline: str
    critical: bool = True


@dataclass(frozen=True)
class NormPack:
    id: str
    label: str
    description: str
    items: tuple[NormPackItem, ...]
    tags: tuple[str, ...] = ()
    agent_slug: str = ""
    discipline_key: str = ""


# Títulos legíveis — expandir conforme acervo do escritório
NBR_TITLES: dict[str, str] = {
    "9050": "Acessibilidade a edificações, mobiliário, espaços e equipamentos urbanos",
    "15575": "Edificações habitacionais — desempenho",
    "6118": "Projeto de estruturas de concreto",
    "6120": "Ações para cálculo de estruturas — peso próprio",
    "6122": "Projeto e execução de fundações",
    "6123": "Forças devidas ao vento em edificações",
    "6484": "Sondagem de simples reconhecimento — método ensaio",
    "6492": "Representação de projetos de arquitetura",
    "7185": "Sondagem de simples reconhecimento — ensaio SPT",
    "7188": "Carga móvel em ponte rodoviária e passarela de pedestres",
    "7191": "Execução de desenhos — concreto armado",
    "7200": "Projeto e execução de pontes de concreto armado",
    "8196": "Folhas de desenho — layout e carimbo",
    "8160": "Sistemas prediais de água quente",
    "8681": "Ações e segurança nas estruturas",
    "8800": "Projeto de estruturas de aço e mistas",
    "8809": "Representação de instalações prediais",
    "9441": "Representação de projetos arquitetônicos (complementar)",
    "9575": "Projeto e execução de sistemas de drenagem pluvial",
    "9649": "Projeto de redes coletoras de esgoto sanitário",
    "9814": "Estudos e projetos de sistemas de esgotamento sanitário",
    "10067": "Princípios gerais de representação em desenho técnico",
    "10126": "Cotagem em desenho técnico",
    "10520": "Revisão de documentos técnicos",
    "10844": "Projeto e execução de drenagem pluvial superficial",
    "10898": "Saídas de emergência em edificações comerciais",
    "13133": "Levantamento topográfico — procedimentos",
    "13142": "Terminologia técnica e literatura",
    "13531": "Elaboração de projetos de edificações",
    "13714": "Sistemas de detecção e alarme de incêndio",
    "14039": "Instalações elétricas de alta tensão (referência)",
    "14166": "Levantamentos geodésicos",
    "14567": "Cabos ópticos para telecomunicações",
    "17240": "Saídas de emergência em edificações",
    "5261": "Símbolos gráficos — instalações elétricas",
    "5410": "Instalações elétricas de baixa tensão",
    "5626": "Instalação predial de água fria",
    "9077": "Saídas de emergência — rotas de fuga",
}

# Disciplinas sem pacote NBR (usam SINAPI, regional ou documentação)
_NON_NBR_DISCIPLINES = frozenset({"ORÇAMENTO", "GERAL", "MEIO_AMBIENTE", "GEOPROCESSAMENTO"})

# NBRs extras por disciplina além de DISCIPLINE_NBRS (desenho, complementares)
_DISCIPLINE_EXTRA_NBRS: dict[str, tuple[str, ...]] = {
    "ARQUITETURA": ("6492", "9441", "10126"),
    "ESTRUTURAL": ("6120", "7191", "10126"),
    "ELÉTRICA": ("5261", "10126"),
    "HIDROSSANITÁRIO": ("8809", "10126"),
    "DRENAGEM": ("10126",),
    "INCÊNDIO": ("9077", "13714"),
    "GEOTECNIA": ("6484",),
    "TELECOM": ("10126",),
    "TRANSPORTES": ("10126",),
    "INFRAESTRUTURA": ("6120", "8681"),
    "SANEAMENTO": ("10126",),
    "TOPOGRAFIA": ("14166", "10126"),
}

_DISCIPLINE_LABELS: dict[str, str] = {
    "ARQUITETURA": "Arquitetura",
    "ESTRUTURAL": "Estruturas",
    "HIDROSSANITÁRIO": "Hidráulica / hidrossanitário",
    "DRENAGEM": "Drenagem pluvial",
    "ELÉTRICA": "Elétrica",
    "TELECOM": "Telecomunicações",
    "INCÊNDIO": "Segurança contra incêndio (PCI)",
    "GEOTECNIA": "Geotecnia / fundações",
    "TRANSPORTES": "Transportes / pavimentos",
    "INFRAESTRUTURA": "Infraestrutura civil",
    "SANEAMENTO": "Saneamento",
    "TOPOGRAFIA": "Topografia",
}


def _parse_nbr_codes_from_labels(labels: list[str]) -> list[str]:
    codes: list[str] = []
    for label in labels:
        match = _NBR_CODE_RE.search(label.replace("/", " "))
        if match:
            codes.append(match.group(1))
    return codes


def _title_for_nbr(code: str) -> str:
    return NBR_TITLES.get(code, f"Norma ABNT NBR {code}")


def _codes_for_discipline(discipline: str) -> list[str]:
    """NBRs do agente + mapa global + extras curados."""
    primary = _parse_nbr_codes_from_labels(DISCIPLINE_NBRS.get(discipline, []))
    from_map = [code for code, disc in NBR_DISCIPLINE_MAP.items() if disc == discipline]
    extras = list(_DISCIPLINE_EXTRA_NBRS.get(discipline, ()))

    seen: set[str] = set()
    ordered: list[str] = []
    for code in primary + extras + from_map:
        if code not in seen:
            seen.add(code)
            ordered.append(code)
    return ordered


def _build_discipline_pack(discipline: str) -> NormPack | None:
    if discipline in _NON_NBR_DISCIPLINES:
        return None
    codes = _codes_for_discipline(discipline)
    if not codes:
        return None

    slug = DISCIPLINE_TO_SLUG.get(discipline, discipline.lower())
    primary_set = set(_parse_nbr_codes_from_labels(DISCIPLINE_NBRS.get(discipline, [])))
    label = _DISCIPLINE_LABELS.get(discipline, discipline.title())

    items = tuple(
        NormPackItem(
            nbr_code=code,
            title=_title_for_nbr(code),
            discipline=discipline,
            critical=code in primary_set,
        )
        for code in codes
    )

    agent_name = DISCIPLINE_TO_AGENT.get(discipline, "")
    normas_agent = ", ".join(DISCIPLINE_NBRS.get(discipline, [])[:4])

    return NormPack(
        id=f"disc_{slug}",
        label=label,
        description=(
            f"Pacote alinhado ao agente `{agent_name}` — normas base: {normas_agent or '—'}. "
            "Inclui NBRs complementares de desenho técnico quando aplicável."
        ),
        tags=("disciplina", slug, "agent"),
        items=items,
        agent_slug=slug,
        discipline_key=discipline,
    )


def _build_all_discipline_packs() -> dict[str, NormPack]:
    packs: dict[str, NormPack] = {}
    for discipline in DISCIPLINE_TO_AGENT:
        if discipline == "GERAL":
            continue
        pack = _build_discipline_pack(discipline)
        if pack:
            packs[pack.id] = pack
    return packs


# Pacotes transversais (workflow / cenários compostos)
_CURATED_PACKS: dict[str, NormPack] = {
    "documentacao_projetos": NormPack(
        id="documentacao_projetos",
        label="Documentação de projetos (desenho técnico)",
        description=(
            "Normas para folhas, carimbo, cotagem e representação — base do Workflow "
            "de entrega e carimbo auditável."
        ),
        tags=("workflow", "carimbo", "grd", "transversal"),
        items=(
            NormPackItem("8196", "Folhas de desenho — layout e carimbo", "DOCUMENTACAO"),
            NormPackItem("10067", "Princípios gerais de representação", "DOCUMENTACAO"),
            NormPackItem("10126", "Cotagem em desenho técnico", "DOCUMENTACAO"),
            NormPackItem("6492", "Representação de projetos de arquitetura", "ARQUITETURA"),
            NormPackItem("13142", "Terminologia técnica e literatura", "DOCUMENTACAO"),
            NormPackItem("10520", "Revisão de documentos técnicos", "DOCUMENTACAO"),
            NormPackItem("13531", "Gestão de documentos de projeto", "DOCUMENTACAO"),
        ),
        discipline_key="DOCUMENTACAO",
    ),
    "arquitetura_residencial": NormPack(
        id="arquitetura_residencial",
        label="Arquitetura — edificações residenciais (pacote composto)",
        description="Cenário residencial: arquitetura + interfaces disciplinares.",
        tags=("arquitetura", "residencial", "composto"),
        items=(
            NormPackItem("6492", "Representação de projetos de arquitetura", "ARQUITETURA"),
            NormPackItem("9050", "Acessibilidade a edificações", "ARQUITETURA"),
            NormPackItem("15575", "Desempenho de edificações habitacionais", "ARQUITETURA"),
            NormPackItem("8196", "Folhas de desenho — layout e carimbo", "DOCUMENTACAO"),
            NormPackItem("10067", "Princípios gerais de representação", "DOCUMENTACAO"),
            NormPackItem("10126", "Cotagem em desenho técnico", "DOCUMENTACAO"),
            NormPackItem("5626", "Instalação predial de água fria", "HIDROSSANITÁRIO", critical=False),
            NormPackItem("5410", "Instalações elétricas de baixa tensão", "ELÉTRICA", critical=False),
            NormPackItem("17240", "Saídas de emergência em edificações", "INCÊNDIO", critical=False),
        ),
        discipline_key="ARQUITETURA",
    ),
}

# Ordem de exibição: transversais → disciplinas (alfabético por label)
_DISCIPLINE_PACKS = _build_all_discipline_packs()
NORM_PACKS: dict[str, NormPack] = {
    **_CURATED_PACKS,
    **dict(sorted(_DISCIPLINE_PACKS.items(), key=lambda kv: kv[1].label)),
}


def list_norm_packs() -> list[dict[str, Any]]:
    transversal = [
        {
            "id": pack.id,
            "label": pack.label,
            "description": pack.description,
            "tags": list(pack.tags),
            "item_count": len(pack.items),
            "critical_count": sum(1 for i in pack.items if i.critical),
            "agent_slug": pack.agent_slug or None,
            "discipline": pack.discipline_key or None,
            "group": "transversal" if "transversal" in pack.tags or "composto" in pack.tags else "disciplina",
        }
        for pack in _CURATED_PACKS.values()
    ]
    disciplinas = [
        {
            "id": pack.id,
            "label": pack.label,
            "description": pack.description,
            "tags": list(pack.tags),
            "item_count": len(pack.items),
            "critical_count": sum(1 for i in pack.items if i.critical),
            "agent_slug": pack.agent_slug,
            "discipline": pack.discipline_key,
            "group": "disciplina",
        }
        for pack in sorted(_DISCIPLINE_PACKS.values(), key=lambda p: p.label)
    ]
    return transversal + disciplinas


def get_norm_pack(pack_id: str) -> NormPack:
    pack = NORM_PACKS.get(pack_id)
    if not pack:
        raise ValueError(f"Pacote normativo desconhecido: {pack_id}")
    return pack
