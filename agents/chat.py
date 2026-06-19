"""
ChatAgent — fluxo conversacional do IA Server Santos.

Pipeline:
  input → intent check → system prompt fixo → qwen3:8b → post-formatter
  (saudações exatas → template instantâneo)
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from agents.base_agent import BaseAgent
from config.settings import CHAT_USE_LLM, OLLAMA_CHAT_MODEL, OLLAMA_CHAT_TIMEOUT
from models.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt fixo — identidade, escopo e tom
# ---------------------------------------------------------------------------

CHAT_SYSTEM_PROMPT = """Você é o ChatAgent do sistema IA Server Santos.

IDENTIDADE:
- Nome: ChatAgent (IA Server Santos)
- Papel: recepcionista inteligente da plataforma — apresenta o sistema e orienta o usuário
- Você NÃO é engenheiro calculista nem substituto dos agentes técnicos

FUNÇÃO:
- Responder perguntas gerais de forma curta e clara (2 a 5 frases)
- Apresentar o IA Server Santos e suas capacidades em alto nível
- Orientar o usuário a formular demandas técnicas para roteamento correto
- NÃO executar cálculos de engenharia
- NÃO simular normas técnicas nem citar tabelas normativas
- NÃO substituir agentes de engenharia (estrutural, hidráulica, elétrica, etc.)

O QUE O SISTEMA FAZ (contexto):
- Chat: roteia dúvidas técnicas para agentes especializados por disciplina
- Orquestrar: coordena múltiplas disciplinas em um único projeto
- Disciplinas: estrutural, hidráulica, elétrica, geotecnia, incêndio, orçamento e outras

TOM:
- Profissional, direto, técnico leve
- Português brasileiro
- Sem emojis excessivos; markdown simples permitido

Se o usuário pedir dimensionamento, norma ou cálculo:
→ Explique que isso é escopo dos agentes técnicos e peça para descrever o problema no chat."""

# ---------------------------------------------------------------------------
# Templates offline (mesma identidade do system prompt)
# ---------------------------------------------------------------------------

TEMPLATE_GREETING = (
    "Olá! Sou o **ChatAgent** do IA Server Santos — plataforma de engenharia civil com IA.\n\n"
    "Oriento sobre o sistema e encaminho demandas técnicas aos especialistas "
    "(estrutural, hidráulica, elétrica e outras disciplinas).\n\n"
    "Como posso ajudar?"
)

TEMPLATE_IDENTITY = (
    "Sou o **ChatAgent** do IA Server Santos — a camada conversacional da plataforma.\n\n"
    "Minha função é apresentar o sistema e orientar você. "
    "Os cálculos e análises normativas ficam com os agentes técnicos especializados "
    "em cada disciplina de engenharia."
)

TEMPLATE_CAPABILITIES = (
    "O IA Server Santos cobre **engenharia civil multidisciplinar**. "
    "Posso orientar sobre:\n\n"
    "- **Estrutural** — concreto armado, vigas, lajes (agente dedicado)\n"
    "- **Hidráulica** — água, esgoto, instalações prediais\n"
    "- **Elétrica** — circuitos, cargas, quadros\n"
    "- **Orquestração** — projetos com várias disciplinas simultaneamente\n\n"
    "Descreva seu problema técnico que roteio ao especialista certo."
)

TEMPLATE_HOW_IT_WORKS = (
    "O IA Server Santos opera em dois modos:\n\n"
    "1. **Chat** — você descreve uma dúvida; o router encaminha ao agente da disciplina\n"
    "2. **Orquestrar** — para projetos multidisciplinares, vários agentes trabalham em conjunto\n\n"
    "Para respostas precisas, inclua contexto: tipo de obra, elemento, norma ou disciplina."
)

TEMPLATE_GENERAL = TEMPLATE_GREETING

_INSTANT_GREETINGS = frozenset({
    "oi", "olá", "ola", "hey", "hi", "hello",
    "bom dia", "boa tarde", "boa noite",
    "tudo bem", "td bem", "e aí", "eai",
})

_INTENT_RULES: list[tuple[str, tuple[str, ...], float]] = [
    ("identity", ("quem é", "quem e", "seu nome", "você é", "voce e", "vc é"), 0.96),
    ("capabilities", (
        "sabe fazer", "pode fazer", "consegue fazer", "faz de melhor",
        "capacidades", "especialidade", "do que você", "do que voce", "do que vc",
    ), 0.95),
    ("how_it_works", (
        "como funciona", "como usar", "como posso usar", "como te uso",
    ), 0.94),
    ("help", ("me ajuda", "preciso de ajuda", "pode ajudar"), 0.90),
]

_TEMPLATE_BY_INTENT = {
    "greeting": TEMPLATE_GREETING,
    "identity": TEMPLATE_IDENTITY,
    "capabilities": TEMPLATE_CAPABILITIES,
    "how_it_works": TEMPLATE_HOW_IT_WORKS,
    "help": TEMPLATE_GENERAL,
    "general": TEMPLATE_GENERAL,
}


@dataclass(frozen=True)
class ChatIntent:
    name: str
    confidence: float


def _normalize(text: str) -> str:
    normalized = text.strip().lower()
    normalized = re.sub(r"[^\w\sáàâãéêíóôõúç]", "", normalized, flags=re.UNICODE)
    return re.sub(r"\s+", " ", normalized).strip()


def detect_intent(text: str) -> ChatIntent:
    """Classifica intenção conversacional (determinístico, sem LLM)."""
    normalized = _normalize(text)

    if normalized in _INSTANT_GREETINGS:
        return ChatIntent("greeting", 1.0)

    for intent, keywords, confidence in _INTENT_RULES:
        if any(kw in normalized for kw in keywords):
            return ChatIntent(intent, confidence)

    return ChatIntent("general", 0.78)


def is_instant_greeting(text: str) -> bool:
    return detect_intent(text).name == "greeting" and detect_intent(text).confidence == 1.0


def pick_template_response(intent: ChatIntent) -> str:
    return _TEMPLATE_BY_INTENT.get(intent.name, TEMPLATE_GENERAL)


def build_prompt(text: str, intent: ChatIntent) -> str:
    return (
        f"{CHAT_SYSTEM_PROMPT}\n\n"
        f"---\n"
        f"INTENÇÃO DETECTADA: {intent.name} (confiança {intent.confidence:.2f})\n\n"
        f"MENSAGEM DO USUÁRIO:\n{text}\n\n"
        f"RESPOSTA DO CHATAGENT:"
    )


def post_format_response(text: str, max_chars: int = 1200) -> str:
    """Limpa saída LLM — remove blocos de raciocínio e normaliza espaços."""
    think_block = re.compile(
        r"<" + r"think" + r">.*?</" + r"think" + r">",
        re.DOTALL | re.IGNORECASE,
    )
    cleaned = text.strip()
    cleaned = think_block.sub("", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if len(cleaned) > max_chars:
        cleaned = cleaned[: max_chars - 3].rsplit(" ", 1)[0] + "..."
    return cleaned


def build_chat_extra(
    intent: ChatIntent,
    response_source: str,
    model: Optional[str] = None,
) -> dict:
    extra = {
        "domain": "chat",
        "mode": "conversational",
        "intent": intent.name,
        "confidence": intent.confidence,
        "response_source": response_source,
        "conversational": True,  # compatibilidade
    }
    if model:
        extra["model"] = model
        extra["llm_model"] = model  # compatibilidade
    return extra


def is_conversational_short(text: str) -> bool:
    """Saudação curta (inclui compostas) — resposta template sem LLM."""
    if is_instant_greeting(text):
        return True
    from core.router import route_by_rules

    if route_by_rules(text):
        return False
    normalized = _normalize(text)
    if len(normalized.split()) > 6:
        return False
    markers = ("oi", "bom dia", "boa tarde", "boa noite", "olá", "ola", "hey")
    return any(marker in normalized for marker in markers)


class ChatAgent(BaseAgent):
    """
    Agente conversacional — sem RAG/NBR.

    Pipeline SaaS:
      intent → system prompt fixo → LLM leve (8B) → post-formatter
    """

    def __init__(
        self,
        llm_client: Optional[OllamaClient] = None,
        use_llm: Optional[bool] = None,
    ):
        super().__init__(name="chat_agent", discipline="CHAT")
        self.use_llm = CHAT_USE_LLM if use_llm is None else use_llm
        self.llm_client = llm_client or OllamaClient(
            primary_model=OLLAMA_CHAT_MODEL,
            fallback_model=None,
            timeout=OLLAMA_CHAT_TIMEOUT,
        )
        self._last_model: Optional[str] = None

    def call_llm(self, text: str, intent: ChatIntent) -> str:
        prompt = build_prompt(text, intent)
        result, model_used = self.llm_client.generate(prompt, model=OLLAMA_CHAT_MODEL)
        self._last_model = model_used
        return post_format_response(result)

    def handle(self, text: str, context=None, **kwargs) -> dict:
        intent = detect_intent(text)
        model: Optional[str] = None

        if intent.name == "greeting" and intent.confidence == 1.0:
            result = pick_template_response(intent)
            source = "template"
        elif self.use_llm:
            try:
                result = self.call_llm(text, intent)
                source = "llm"
                model = self._last_model
            except Exception as exc:
                logger.warning("ChatAgent LLM falhou, usando template: %s", exc)
                result = pick_template_response(intent)
                source = "template_fallback"
        else:
            result = pick_template_response(intent)
            source = "template"

        extra = build_chat_extra(intent, source, model)
        return self.build_response(input_text=text, result=result, extra=extra)

    def build_stream_response(self, text: str, result: str, intent: ChatIntent, source: str, model: Optional[str]) -> dict:
        extra = build_chat_extra(intent, source, model)
        if source == "llm_stream":
            extra["response_source"] = "llm_stream"
        return self.build_response(input_text=text, result=result, extra=extra)

    def iter_tokens(self, text: str):
        """Stream de resposta conversacional (template ou LLM 8B)."""
        intent = detect_intent(text)

        if is_conversational_short(text):
            yield pick_template_response(intent)
            return

        if self.use_llm:
            try:
                prompt = build_prompt(text, intent)
                for token, model_used in self.llm_client.generate_stream(
                    prompt, model=OLLAMA_CHAT_MODEL
                ):
                    self._last_model = model_used
                    yield token
                return
            except Exception as exc:
                logger.warning("ChatAgent stream falhou, usando template: %s", exc)

        yield pick_template_response(intent)
