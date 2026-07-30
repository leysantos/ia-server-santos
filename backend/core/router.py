import logging
import re
from typing import Optional

import requests

from config.settings import OLLAMA_BASE_URL, OLLAMA_LLM_MODEL
from core.agent_registry import get_agent_name

logger = logging.getLogger(__name__)

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
    "CHAT",
]

CHAT_AGENT_NAME = "chat_agent"

# Saudações exatas — fluxo conversacional (prioridade máxima no route)
SIMPLE_GREETING_PATTERNS = [
    r"^oi$",
    r"^olá$",
    r"^ola$",
    r"^hey$",
    r"^hi$",
    r"^hello$",
    r"^bom dia$",
    r"^boa tarde$",
    r"^boa noite$",
    r"^tudo bem$",
    r"^td bem$",
    r"^e aí$",
    r"^eai$",
]

# Perguntas gerais / identidade / capacidades (sem engenharia)
CONVERSATIONAL_PATTERNS = [
    r"^oi\s+",
    r"^olá\s+",
    r"^ola\s+",
    r"^bom dia\s+",
    r"^boa tarde\s+",
    r"^boa noite\s+",
    r"quem é (você|voce|vc)\b",
    r"quem e (voce|vc)\b",
    r"o que (você|voce|vc)\s",
    r"o que e (voce|vc)\s",
    r"(você|voce|vc) sabe",
    r"(você|voce|vc) consegue",
    r"(você|voce|vc) pode",
    r"sabe fazer",
    r"pode fazer",
    r"faz de melhor",
    r"do que (você|voce|vc)",
    r"como funciona",
    r"como (você|voce|vc) funciona",
    r"como (posso|eu posso|usar)",
    r"(fale|conte) sobre (você|voce|vc|o sistema|ia server)",
    r"qual (é )?(seu )?nome",
    r"(você|voce|vc) é (um )?(robo|robô|ia|bot|assistente)",
    r"(voce|vc) e (um )?(robo|ia|bot|assistente)",
    r"quais (são )?(suas|as) (capacidades|funções|especialidades)",
    r"em que (você|voce|vc) (pode|consegue)",
    r"me (ajuda|ajude)(\s|\?|$)",
    r"preciso de ajuda(\s|\?|$)",
]

# Fallback: frases com marcadores conversacionais (sem keyword de engenharia)
CONVERSATIONAL_MARKERS = [
    "sabe fazer",
    "pode fazer",
    "consegue fazer",
    "faz de melhor",
    "capacidades",
    "especialidades",
    "quem é",
    "quem e",
    "o que vc",
    "o que voce",
    "o que você",
    "como funciona",
    "como usar",
    "como posso usar",
    "seu nome",
    "você é",
    "voce e",
    "vc é",
    "ia server",
    "me ajuda",
    "preciso de ajuda",
    "bom dia",
    "boa tarde",
    "boa noite",
    "tudo bem",
]

# Regras fortes — prioridade sobre LLM.
# Score = soma dos comprimentos das keywords que batem (mais hits → mais peso).
# Tokens curtos usam limite de palavra (evita "estrutura" ⊂ "infraestrutura").
DISCIPLINE_RULES: dict[str, list[str]] = {
    "ESTRUTURAL": [
        "dimensionamento estrutural",
        "projeto estrutural",
        "análise estrutural",
        "analise estrutural",
        "cálculo estrutural",
        "calculo estrutural",
        "modelo estrutural",
        "disciplina estrutural",
        "concreto armado",
        "concreto protendido",
        "estrutura de concreto",
        "estrutura metálica",
        "estrutura metalica",
        "estruturas de aço",
        "estruturas de aco",
        "viga metálica",
        "viga metalica",
        "armadura passiva",
        "armadura de pele",
        "taxa de armadura",
        "dimensionar viga",
        "dimensionar laje",
        "dimensionar pilar",
        "momento fletor",
        "esforço cortante",
        "esforco cortante",
        "cisalhamento",
        "pórtico",
        "portico",
        "treliça",
        "trelica",
        "sapata isolada",
        "sapata corrida",
        "bloco sobre estacas",
        "ca-50",
        "ca-60",
        "fck",
        "elu",
        "els",
        "flecha",
        "protensão",
        "protensao",
        "armadura",
        "estrutural",
        "estruturas",
        "estrutura",
        "viga",
        "laje",
        "pilar",
        "pilares",
        "vigas",
        "lajes",
        "nbr 6118",
        "nbr 8800",
        "nbr 8681",
        "nbr 7191",
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
        "água quente",
        "agua quente",
        "esgoto",
        "hidráulica",
        "hidraulica",
        "barrilete",
        "ramal predial",
        "caixa de inspeção",
        "caixa de inspecao",
        "coluna de ventilação",
        "coluna de ventilacao",
        "nbr 5626",
        "nbr 8160",
        "nbr 7198",
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
        "nbr 5410",
    ],
    "GEOTECNIA": [
        "investigação geotécnica",
        "investigacao geotecnica",
        "sondagem spt",
        "sondagem",
        "estabilidade de talude",
        "capacidade de carga do solo",
        "geotecnia",
        "geotécnica",
        "geotecnica",
        "recalque",
        "aterro",
        "spt",
        "fundação superficial",
        "fundacao superficial",
        "fundação profunda",
        "fundacao profunda",
        "fundação",
        "fundacao",
        # "solo" sozinho é ambíguo demais — exige contexto geotécnico
        "solo residual",
        "solo de fundação",
        "solo de fundacao",
        "classificação do solo",
        "classificacao do solo",
        "nbr 6122",
        "nbr 7185",
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
        "arquitetura",
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

# Tokens curtos / ambíguos: match com limite de palavra (não substring).
_WORD_BOUNDARY_KEYWORDS = frozenset(
    {
        "viga",
        "vigas",
        "laje",
        "lajes",
        "pilar",
        "pilares",
        "estrutura",
        "estruturas",
        "estrutural",
        "armadura",
        "flecha",
        "protensão",
        "protensao",
        "cisalhamento",
        "pórtico",
        "portico",
        "treliça",
        "trelica",
        "fck",
        "elu",
        "els",
        "ca-50",
        "ca-60",
        "pci",
        "spt",
        "ete",
        "eta",
        "gis",
        "bdi",
        "bdí",
        "esgoto",
        "circuito",
        "hidrante",
        "sprinkler",
        "aterro",
        "recalque",
        "drenagem",
        "pluvial",
        "fachada",
        "arquitetura",
        "geotecnia",
        "topografia",
        "orçamento",
        "orcamento",
        "sinapi",
    }
)


def call_llm(prompt: str) -> str:
    """
    Fallback LLM do roteador de disciplina.
    Ordem: Gemini 3.6 (se chave + flag) → Model Router / Ollama local.
    """
    from config import settings

    use_gemini = bool(getattr(settings, "USE_GEMINI_DISCIPLINE_ROUTER", True))
    if use_gemini:
        try:
            from core.inspection_report.gemini_client import (
                gemini_available,
                generate_text,
                resolve_gemini_model,
            )

            if gemini_available():
                model = resolve_gemini_model() or "gemini-3.6-flash"
                result = generate_text(
                    prompt,
                    temperature=0.0,
                    max_output_tokens=64,
                    model=model,
                )
                if result:
                    logger.info("discipline_router via Gemini model=%s", model)
                    return result.strip().lower()
        except Exception as exc:
            logger.warning("Gemini discipline router falhou (%s) — fallback Ollama", exc)

    if settings.USE_MODEL_ROUTER or settings.USE_MODEL_EVALUATION:
        from core.models.model_router import routed_generate

        result, _model = routed_generate(
            prompt,
            "orchestration_synthesis",
            context={"text": prompt},
            module="router",
        )
        return result.strip().lower()

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


def _normalize_chat_text(text: str) -> str:
    normalized = text.strip().lower()
    normalized = re.sub(r"[^\w\sáàâãéêíóôõúç]", "", normalized, flags=re.UNICODE)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _has_conversational_markers(normalized: str) -> bool:
    return any(marker in normalized for marker in CONVERSATIONAL_MARKERS)


def route_by_chat(text: str) -> bool:
    """
    Detecta saudações e perguntas conversacionais simples (sem engenharia).
    """
    if route_by_rules(text):
        return False

    normalized = _normalize_chat_text(text)

    if any(re.match(pattern, normalized) for pattern in SIMPLE_GREETING_PATTERNS):
        return True

    if any(re.search(pattern, normalized) for pattern in CONVERSATIONAL_PATTERNS):
        return True

    return _has_conversational_markers(normalized)


def _keyword_matches(keyword: str, lowered: str) -> bool:
    """Substring para frases; limite de palavra para tokens curtos/ambíguos."""
    kw = keyword.lower().strip()
    if not kw:
        return False
    if " " in kw or "'" in kw:
        return kw in lowered
    if kw in _WORD_BOUNDARY_KEYWORDS or len(kw) <= 6:
        return bool(re.search(rf"(?<!\w){re.escape(kw)}(?!\w)", lowered, flags=re.UNICODE))
    return kw in lowered


def _discipline_from_nbr(text: str) -> Optional[str]:
    """Se a query cita NBR mapeada (ex.: 6118), prioriza a disciplina da norma."""
    from memory.nbr_catalog import NBR_PATTERN, infer_discipline, normalize_nbr_code

    match = NBR_PATTERN.search(text or "")
    if not match:
        return None
    code = normalize_nbr_code(match.group(1))
    disc = infer_discipline(code)
    if disc and disc in VALID_DISCIPLINES:
        return disc
    return None


def route_by_rules(text: str) -> Optional[str]:
    """
    Classificação determinística por palavras-chave de engenharia.
    Score = soma dos comprimentos das keywords que batem.
    NBR explícita na query tem prioridade alta (boost).
    """
    lowered = (text or "").lower()
    scores: dict[str, int] = {}

    nbr_disc = _discipline_from_nbr(text)
    if nbr_disc:
        scores[nbr_disc] = scores.get(nbr_disc, 0) + 50

    for discipline, keywords in DISCIPLINE_RULES.items():
        score = 0
        for keyword in keywords:
            if _keyword_matches(keyword, lowered):
                score += len(keyword)
        if score:
            scores[discipline] = scores.get(discipline, 0) + score

    if not scores:
        return None

    # Empate: preferir ESTRUTURAL sobre GEOTECNIA quando ambos pontuam
    # (ex.: "fundação rasa estrutural") — demais: maior score, depois ordem estável.
    best = max(scores.items(), key=lambda kv: (kv[1], kv[0] == "ESTRUTURAL", kv[0]))
    return best[0]


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
- ESTRUTURAL: vigas, lajes, pilares, concreto armado, estrutura metálica, NBR 6118/8800,
  momento fletor, armadura, pórtico, sapata/bloco estrutural, ELU/ELS, projeto estrutural
- HIDROSSANITÁRIO: água fria/quente, esgoto, tubulações, reservatórios, NBR 5626/8160
- ELÉTRICA: circuitos, cargas, fiação, quadros, NBR 5410
- GEOTECNIA: solo, sondagem SPT, investigação geotécnica, estabilidade de taludes, NBR 6122
  (fundação só é GEOTECNIA se o foco for solo/sondagem; dimensionamento de sapata/bloco → ESTRUTURAL)
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
"projeto estrutural de edifício" -> ESTRUTURAL
"o que diz a NBR 6118 sobre cobrimento" -> ESTRUTURAL
"estrutura metálica de galpão" -> ESTRUTURAL
"projeto de esgoto sanitário predial" -> HIDROSSANITÁRIO
"cálculo de carga elétrica do quadro" -> ELÉTRICA
"sondagem SPT para fundação" -> GEOTECNIA
"drenagem de águas pluviais" -> DRENAGEM
"sistema de sprinkler" -> INCÊNDIO

SOLICITAÇÃO:
{text}

DISCIPLINA:"""

    return call_llm(prompt)


def route_engineering_only(text: str) -> dict:
    """
    Roteamento técnico — ignora detecção CHAT.
    Usado pela Intent Layer v2 para segmentos de engenharia.
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

    agent = get_agent_name(discipline)

    return {
        "input": text,
        "discipline": discipline,
        "agent": agent,
    }


def route(text: str) -> dict:
    """
    Pipeline de roteamento: saudação > regras > LLM > GERAL
    """
    if route_by_chat(text):
        return {
            "input": text,
            "discipline": "CHAT",
            "agent": CHAT_AGENT_NAME,
        }

    discipline: Optional[str] = route_by_rules(text)

    if not discipline:
        try:
            llm_raw = route_engineering(text)
            discipline = normalize_discipline(llm_raw)
        except Exception:
            discipline = None

    if not discipline or discipline not in VALID_DISCIPLINES:
        discipline = "GERAL"

    # GERAL sem agente → fallback conversacional se não for técnico
    if discipline == "GERAL" and route_by_chat(text):
        discipline = "CHAT"

    agent = CHAT_AGENT_NAME if discipline == "CHAT" else get_agent_name(discipline)

    return {
        "input": text,
        "discipline": discipline,
        "agent": agent,
    }
