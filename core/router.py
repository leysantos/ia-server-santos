import re
from typing import Optional

import requests

from config.settings import OLLAMA_BASE_URL, OLLAMA_LLM_MODEL

OLLAMA_URL = f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate"
MODEL = OLLAMA_LLM_MODEL

VALID_DISCIPLINES = [
    "ARQUITETURA",
    "ESTRUTURAL",
    "HIDROSSANITÁRIO",
    "DRENAGEM",
    "ELÉTRICA",
    "TELECOM",
    "INCÊNDIO",
    "GEOTECNIA",
    "TRANSPORTES",
    "INFRAESTRUTURA",
    "SANEAMENTO",
    "GEOPROCESSAMENTO",
    "TOPOGRAFIA",
    "ORÇAMENTO",
    "MEIO_AMBIENTE",
    "GERAL",
]

DISCIPLINE_TO_AGENT = {
    "ARQUITETURA": "arquitetura_agent",
    "ESTRUTURAL": "estruturas_agent",
    "HIDROSSANITÁRIO": "hidrossanitario_agent",
    "DRENAGEM": "drenagem_agent",
    "ELÉTRICA": "eletrica_agent",
    "TELECOM": "telecom_agent",
    "INCÊNDIO": "incendio_agent",
    "GEOTECNIA": "geotecnia_agent",
    "TRANSPORTES": "transportes_agent",
    "INFRAESTRUTURA": "infraestrutura_agent",
    "SANEAMENTO": "saneamento_agent",
    "GEOPROCESSAMENTO": "geoprocessamento_agent",
    "TOPOGRAFIA": "topografia_agent",
    "ORÇAMENTO": "orcamento_agent",
    "MEIO_AMBIENTE": "meio_ambiente_agent",
    "GERAL": "geral_agent",
}

# Regras fortes — prioridade sobre LLM (keywords mais longas têm peso maior)
DISCIPLINE_RULES: dict[str, list[str]] = {
    "ESTRUTURAL": [
        "dimensionamento estrutural",
        "concreto armado",
        "concreto protendido",
        "estrutura de concreto",
        "viga",
        "laje",
        "pilar",
        "viga metálica",
        "viga metalica",
        "armadura passiva",
        "dimensionar viga",
        "dimensionar laje",
    ],
    "HIDROSSANITÁRIO": [
        "hidrossanitário",
        "hidrossanitario",
        "instalações hidráulicas",
        "instalacoes hidraulicas",
        "água potável",
        "agua potavel",
        "esgoto sanitário",
        "esgoto sanitario",
        "tubulação",
        "tubulacao",
        "caixa d'água",
        "caixa dagua",
        "água fria",
        "agua fria",
        "esgoto",
        "hidráulica",
        "hidraulica",
    ],
    "ELÉTRICA": [
        "carga elétrica",
        "carga eletrica",
        "instalações elétricas",
        "instalacoes eletricas",
        "quadro elétrico",
        "quadro eletrico",
        "circuito elétrico",
        "circuito eletrico",
        "fiação",
        "fiacao",
        "circuito",
        "luminotécnica",
        "luminotecnica",
    ],
    "GEOTECNIA": [
        "investigação geotécnica",
        "investigacao geotecnica",
        "sondagem spt",
        "sondagem",
        "estabilidade de talude",
        "capacidade de carga do solo",
        "recalque",
        "aterro",
        "solo",
        "spt",
        "fundação superficial",
        "fundacao superficial",
        "fundação profunda",
        "fundacao profunda",
        "fundação",
        "fundacao",
    ],
    "DRENAGEM": [
        "águas pluviais",
        "aguas pluviais",
        "drenagem pluvial",
        "drenagem urbana",
        "bocas de lobo",
        "galeria pluvial",
        "drenagem",
        "pluvial",
    ],
    "INCÊNDIO": [
        "combate a incêndio",
        "combate a incendio",
        "sistema de sprinkler",
        "sprinkler",
        "hidrante",
        "detecção de incêndio",
        "deteccao de incendio",
        "pci",
        "saída de emergência",
        "saida de emergencia",
    ],
    "ARQUITETURA": [
        "acessibilidade",
        "nbr 9050",
        "plant baixa",
        "planta baixa",
        "fachada",
        "arquitetônico",
        "arquitetonico",
    ],
    "TELECOM": [
        "cabeamento estruturado",
        "fibra óptica",
        "fibra optica",
        "telecomunicações",
        "telecomunicacoes",
        "datacenter",
    ],
    "TRANSPORTES": [
        "pavimentação",
        "pavimentacao",
        "rodoviário",
        "rodoviario",
        "sinalização viária",
        "sinalizacao viaria",
        "tráfego",
        "trafego",
    ],
    "SANEAMENTO": [
        "estação de tratamento",
        "estacao de tratamento",
        "ete",
        "eta",
        "saneamento básico",
        "saneamento basico",
        "coleta de esgoto",
    ],
    "GEOPROCESSAMENTO": [
        "shapefile",
        "geoprocessamento",
        "coordenadas utm",
        "sistema de coordenadas",
        "gis",
    ],
    "TOPOGRAFIA": [
        "levantamento topográfico",
        "levantamento topografico",
        "topografia",
        "altimetria",
        "planialtimetria",
    ],
    "ORÇAMENTO": [
        "orçamento de obra",
        "orcamento de obra",
        "composição de custos",
        "composicao de custos",
        "sinapi",
        "bdí",
        "bdi",
        "orçamento",
        "orcamento",
    ],
    "MEIO_AMBIENTE": [
        "licenciamento ambiental",
        "eia-rima",
        "eia rima",
        "resolução conama",
        "resolucao conama",
        "meio ambiente",
    ],
    "INFRAESTRUTURA": [
        "infraestrutura urbana",
        "terraplanagem",
        "obra de infraestrutura",
    ],
}


def call_llm(prompt: str) -> str:
    response = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "prompt": prompt, "stream": False},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["response"].strip().lower()


def normalize_discipline(raw: str) -> Optional[str]:
    """Normaliza resposta bruta para disciplina válida."""
    if not raw:
        return None

    token = raw.strip().upper()
    token = re.sub(r"[^A-ZÁÀÂÃÉÊÍÓÔÕÚÇ_ÁÀÂÃÉÊÍÓÔÕÚÇ\s]", "", token)
    token = token.replace(" ", "_")

    aliases = {
        "HIDROSSANITARIO": "HIDROSSANITÁRIO",
        "ELETRICA": "ELÉTRICA",
        "INCENDIO": "INCÊNDIO",
        "ORCAMENTO": "ORÇAMENTO",
        "ESTRUTURAS": "ESTRUTURAL",
    }
    token = aliases.get(token, token)

    if token in VALID_DISCIPLINES:
        return token

    for discipline in VALID_DISCIPLINES:
        if discipline in raw.upper():
            return discipline

    return None


def route_by_rules(text: str) -> Optional[str]:
    """
    Classificação determinística por palavras-chave de engenharia.
    Retorna a disciplina com melhor correspondência (keyword mais específica).
    """
    lowered = text.lower()
    best_discipline: Optional[str] = None
    best_score = 0

    for discipline, keywords in DISCIPLINE_RULES.items():
        for keyword in keywords:
            if keyword in lowered and len(keyword) > best_score:
                best_score = len(keyword)
                best_discipline = discipline

    return best_discipline


def route_engineering(text: str) -> str:
    """Fallback LLM com prompt técnico para engenharia civil multidisciplinar."""
    prompt = f"""
Você é um roteador técnico de engenharia civil e infraestrutura multidisciplinar.

Sua função é classificar solicitações técnicas em EXATAMENTE UMA disciplina de engenharia.

DISCIPLINAS VÁLIDAS:
ARQUITETURA, ESTRUTURAL, HIDROSSANITÁRIO, DRENAGEM, ELÉTRICA, TELECOM,
INCÊNDIO, GEOTECNIA, TRANSPORTES, INFRAESTRUTURA, SANEAMENTO,
GEOPROCESSAMENTO, TOPOGRAFIA, ORÇAMENTO, MEIO_AMBIENTE, GERAL

CONTEXTO TÉCNICO:
- ESTRUTURAL: vigas, lajes, pilares, concreto armado, dimensionamento estrutural, NBR 6118
- HIDROSSANITÁRIO: água fria/quente, esgoto, tubulações, reservatórios, NBR 5626/8160
- ELÉTRICA: circuitos, cargas, fiação, quadros, NBR 5410
- GEOTECNIA: solo, sondagem SPT, fundações, estabilidade, NBR 6122
- DRENAGEM: águas pluviais, galerias, bocas de lobo, NBR 10844
- INCÊNDIO: sprinkler, hidrantes, PCI, NBR 17240

REGRAS DE RESPOSTA:
- responda APENAS o nome da disciplina
- uma palavra ou termo com underscore
- sem explicações, sem pontuação
- sempre MAIÚSCULO
- use GERAL somente se não houver disciplina técnica identificável

EXEMPLOS:
"dimensionar viga de concreto armado" -> ESTRUTURAL
"dimensionamento de laje maciça" -> ESTRUTURAL
"projeto de esgoto sanitário predial" -> HIDROSSANITÁRIO
"cálculo de carga elétrica do quadro" -> ELÉTRICA
"sondagem SPT para fundação" -> GEOTECNIA
"drenagem de águas pluviais" -> DRENAGEM
"sistema de sprinkler" -> INCÊNDIO

SOLICITAÇÃO:
{text}

DISCIPLINA:"""

    return call_llm(prompt)


def route(text: str) -> dict:
    """
    Pipeline de roteamento: regras > LLM > GERAL
    """
    discipline: Optional[str] = route_by_rules(text)

    if not discipline:
        try:
            llm_raw = route_engineering(text)
            discipline = normalize_discipline(llm_raw)
        except Exception:
            discipline = None

    if not discipline or discipline not in VALID_DISCIPLINES:
        discipline = "GERAL"

    return {
        "input": text,
        "discipline": discipline,
        "agent": DISCIPLINE_TO_AGENT.get(discipline, "geral_agent"),
    }
