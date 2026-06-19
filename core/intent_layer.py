"""
Intent Layer v2 — decisão central antes do roteamento.

Classifica entrada em:
  - chat_only       → ChatAgent
  - engineering_only → router técnico + agente especializado
  - mixed           → ChatAgent + agente técnico (segmentos separados)

Base para Orchestrator v2 / planner interno.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from agents.chat import ChatIntent, detect_intent as detect_chat_intent
from core.agent_registry import get_agent_name
from core.router import (
    CHAT_AGENT_NAME,
    route_by_chat,
    route_by_rules,
    route_engineering_only,
)

IntentMode = str  # chat_only | engineering_only | mixed


def _agent_llm_model(agent) -> Optional[str]:
    """Modelo LLM em uso pelo agente (quando disponível)."""
    if agent is None:
        return None
    return getattr(agent, "_last_model_used", None) or getattr(agent, "_last_model", None)


def _token_payload(step, token: str, agent=None, **extra) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "token": token,
        "discipline": step.discipline,
        "agent": step.agent,
        "step": step.step,
    }
    model = _agent_llm_model(agent)
    if model:
        payload["llm_model"] = model
    payload.update(extra)
    return payload


# Prefixos conversacionais encadeáveis (ex.: "oi boa noite! preciso...")
_CONVERSATIONAL_PREFIXES = (
    "bom dia",
    "boa tarde",
    "boa noite",
    "tudo bem",
    "olá",
    "ola",
    "hello",
    "hey",
    "e aí",
    "eai",
    "oi",
    "hi",
)


@dataclass
class ExecutionStep:
    step: int
    domain: str  # chat | engineering
    discipline: str
    agent: str
    input: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IntentAnalysis:
    mode: IntentMode
    confidence: float
    input: str
    chat_intent: Optional[ChatIntent] = None
    technical_discipline: Optional[str] = None
    chat_segment: Optional[str] = None
    technical_segment: Optional[str] = None
    execution_plan: list[ExecutionStep] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "mode": self.mode,
            "confidence": self.confidence,
            "input": self.input,
            "technical_discipline": self.technical_discipline,
            "chat_segment": self.chat_segment,
            "technical_segment": self.technical_segment,
            "execution_plan": [s.to_dict() for s in self.execution_plan],
        }
        if self.chat_intent:
            payload["chat_intent"] = {
                "name": self.chat_intent.name,
                "confidence": self.chat_intent.confidence,
            }
        return payload


def try_split_mixed(text: str) -> Optional[tuple[str, str]]:
    """
    Separa saudações iniciais encadeadas + demanda técnica.
    Retorna (chat_segment, technical_segment) ou None.
    """
    remaining = text.strip()
    chat_parts: list[str] = []

    while remaining:
        matched = False
        for greeting in sorted(_CONVERSATIONAL_PREFIXES, key=len, reverse=True):
            pattern = re.compile(rf"^{re.escape(greeting)}[,!\s]*", re.IGNORECASE)
            match = pattern.match(remaining)
            if match:
                chat_parts.append(match.group(0).strip().rstrip(",!"))
                remaining = remaining[match.end() :].strip()
                matched = True
                break
        if not matched:
            break

    if not chat_parts or not remaining:
        return None

    discipline = route_by_rules(remaining)
    if not discipline:
        return None

    chat_segment = " ".join(part for part in chat_parts if part).strip()
    return chat_segment, remaining


def _build_mixed_plan(
    chat_segment: str,
    technical_segment: str,
    discipline: str,
) -> list[ExecutionStep]:
    return [
        ExecutionStep(
            step=1,
            domain="chat",
            discipline="CHAT",
            agent=CHAT_AGENT_NAME,
            input=chat_segment,
        ),
        ExecutionStep(
            step=2,
            domain="engineering",
            discipline=discipline,
            agent=get_agent_name(discipline),
            input=technical_segment,
        ),
    ]


def analyze_intent(text: str) -> IntentAnalysis:
    """
    Classifica intenção global da mensagem (determinístico + router técnico).
    """
    text = text.strip()
    if not text:
        chat_intent = detect_chat_intent("")
        return IntentAnalysis(
            mode="chat_only",
            confidence=0.5,
            input=text,
            chat_intent=chat_intent,
            execution_plan=[
                ExecutionStep(1, "chat", "CHAT", CHAT_AGENT_NAME, text),
            ],
        )

    mixed = try_split_mixed(text)
    if mixed:
        chat_segment, technical_segment = mixed
        discipline = route_by_rules(technical_segment)
        chat_intent = detect_chat_intent(chat_segment)
        return IntentAnalysis(
            mode="mixed",
            confidence=0.93,
            input=text,
            chat_intent=chat_intent,
            technical_discipline=discipline,
            chat_segment=chat_segment,
            technical_segment=technical_segment,
            execution_plan=_build_mixed_plan(
                chat_segment, technical_segment, discipline
            ),
        )

    discipline = route_by_rules(text)
    if discipline:
        return IntentAnalysis(
            mode="engineering_only",
            confidence=0.90,
            input=text,
            technical_discipline=discipline,
            execution_plan=[
                ExecutionStep(
                    step=1,
                    domain="engineering",
                    discipline=discipline,
                    agent=get_agent_name(discipline),
                    input=text,
                ),
            ],
        )

    if route_by_chat(text):
        chat_intent = detect_chat_intent(text)
        return IntentAnalysis(
            mode="chat_only",
            confidence=chat_intent.confidence,
            input=text,
            chat_intent=chat_intent,
            execution_plan=[
                ExecutionStep(1, "chat", "CHAT", CHAT_AGENT_NAME, text),
            ],
        )

    route_result = route_engineering_only(text)
    discipline = route_result.get("discipline", "GERAL")

    if discipline not in ("GERAL", "CHAT"):
        return IntentAnalysis(
            mode="engineering_only",
            confidence=0.75,
            input=text,
            technical_discipline=discipline,
            execution_plan=[
                ExecutionStep(
                    step=1,
                    domain="engineering",
                    discipline=discipline,
                    agent=route_result.get("agent", get_agent_name(discipline)),
                    input=text,
                ),
            ],
        )

    chat_intent = detect_chat_intent(text)
    return IntentAnalysis(
        mode="chat_only",
        confidence=min(chat_intent.confidence, 0.85),
        input=text,
        chat_intent=chat_intent,
        execution_plan=[
            ExecutionStep(1, "chat", "CHAT", CHAT_AGENT_NAME, text),
        ],
    )


def merge_segment_results(
    segments: list[dict[str, Any]],
    mode: IntentMode,
) -> str:
    """Combina respostas de múltiplos passos em texto único."""
    if len(segments) == 1:
        return segments[0].get("result") or segments[0].get("response", "")

    parts: list[str] = []
    for seg in segments:
        discipline = seg.get("discipline", "AGENTE")
        label = "ChatAgent" if discipline == "CHAT" else discipline
        body = seg.get("result") or seg.get("response", "")
        parts.append(f"### {label}\n\n{body}")

    header = (
        "**Resposta combinada** (conversacional + técnica):\n\n"
        if mode == "mixed"
        else ""
    )
    return header + "\n\n---\n\n".join(parts)


def _dispatch_step(
    step: ExecutionStep,
    use_rag: bool,
    persist: bool,
    conversation_id: Optional[str],
) -> dict[str, Any]:
    from core.dispatcher import dispatch
    from memory.rag_engine import get_rag_engine

    route_result = {
        "input": step.input,
        "discipline": step.discipline,
        "agent": step.agent,
        "_conversation_id": conversation_id,
    }

    if step.domain == "chat":
        route_result["_use_rag"] = False
    elif use_rag:
        engine = get_rag_engine()
        route_result = engine.enrich_route_result(route_result)
    else:
        route_result["_use_rag"] = False

    return dispatch(route_result, persist=persist)


def execute_intent(
    analysis: IntentAnalysis,
    use_rag: bool = True,
    persist: bool = True,
    conversation_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Executa o plano da Intent Layer e retorna payload unificado.
    """
    segment_responses: list[dict[str, Any]] = []

    for step in analysis.execution_plan:
        segment_responses.append(
            _dispatch_step(step, use_rag, persist, conversation_id)
        )

    primary = segment_responses[-1]
    merged_result = merge_segment_results(segment_responses, analysis.mode)

    output: dict[str, Any] = {
        **primary,
        "input": analysis.input,
        "result": merged_result,
        "intent": analysis.to_dict(),
        "segments": segment_responses,
        "route": {
            "discipline": primary.get("discipline"),
            "agent": primary.get("agent"),
            "mode": analysis.mode,
        },
    }
    return output


def _stream_step_events(
    step: ExecutionStep,
    use_rag: bool,
    persist: bool,
    conversation_id: Optional[str],
):
    """Gera eventos token + segment_done para um passo do plano."""
    from agents.chat import ChatAgent, detect_intent
    from core.dispatcher import AGENTS, _agent_error_response
    from core.database.service import save_agent_run
    from memory.rag_engine import get_rag_engine

    agent = AGENTS.get(step.discipline)
    route_result: dict[str, Any] = {
        "input": step.input,
        "discipline": step.discipline,
        "agent": step.agent,
        "_conversation_id": conversation_id,
    }

    rag_context = ""
    use_rag_step = False
    if step.domain == "chat":
        route_result["_use_rag"] = False
    elif use_rag:
        engine = get_rag_engine()
        route_result = engine.enrich_route_result(route_result)
        rag_context = route_result.get("context") or ""
        use_rag_step = True
    else:
        route_result["_use_rag"] = False

    tokens: list[str] = []
    try:
        if agent and hasattr(agent, "iter_tokens"):
            if isinstance(agent, ChatAgent):
                for token in agent.iter_tokens(step.input):
                    tokens.append(token)
                    yield ("token", _token_payload(step, token, agent=agent))
                full_text = post_format_chat_stream("".join(tokens))
                intent = detect_intent(step.input)
                source = "llm_stream" if agent._last_model else "template"
                response = agent.build_stream_response(
                    step.input, full_text, intent, source, agent._last_model
                )
            else:
                context = route_result.get("context")
                for token in agent.iter_tokens(
                    step.input,
                    context=context,
                    use_rag=use_rag_step,
                ):
                    tokens.append(token)
                    yield ("token", _token_payload(step, token, agent=agent))
                full_text = "".join(tokens)
                response = agent.build_stream_response(
                    step.input, full_text, rag_context
                )
        else:
            response = _dispatch_step(step, use_rag, persist=False, conversation_id=conversation_id)
            full_text = response.get("result") or response.get("response") or ""
            model = (response.get("extra") or {}).get("llm_model")
            extra = {"llm_model": model} if model else {}
            yield ("token", _token_payload(step, full_text, agent=agent, **extra))

        if persist:
            save_agent_run(route_result=route_result, response=response)

        yield ("segment_done", response)

    except Exception as exc:
        response = _agent_error_response(step.discipline, step.input, exc)
        yield (
            "token",
            _token_payload(step, response.get("result", ""), agent=agent, error=True),
        )
        if persist:
            save_agent_run(route_result=route_result, response=response)
        yield ("segment_done", response)


def post_format_chat_stream(text: str) -> str:
    from agents.chat import post_format_response
    return post_format_response(text)


def iter_intent_events(
    text: str,
    use_rag: bool = True,
    persist: bool = True,
    conversation_id: Optional[str] = None,
):
    """
    Generator de eventos para SSE: status | intent | token | segment_done | done.
    """
    yield ("status", {"message": "Analisando intenção...", "phase": "intent"})
    analysis = analyze_intent(text)
    yield ("intent", analysis.to_dict())
    yield (
        "status",
        {
            "message": f"Plano: {analysis.mode} ({len(analysis.execution_plan)} passo(s))",
            "phase": "plan",
            "mode": analysis.mode,
        },
    )

    segment_responses: list[dict[str, Any]] = []

    for step in analysis.execution_plan:
        label = "ChatAgent" if step.domain == "chat" else step.discipline
        yield (
            "status",
            {
                "message": f"Modelo respondendo: {label} ({step.agent})...",
                "phase": "agent_start",
                "step": step.to_dict(),
            },
        )

        if analysis.mode == "mixed" and step.step > 1:
            header = f"\n\n---\n\n### {step.discipline}\n\n"
            yield (
                "token",
                {
                    "token": header,
                    "discipline": step.discipline,
                    "agent": step.agent,
                    "step": step.step,
                    "meta": True,
                },
            )

        for event in _stream_step_events(step, use_rag, persist, conversation_id):
            if event[0] == "segment_done":
                segment_responses.append(event[1])
            yield event

    primary = segment_responses[-1] if segment_responses else {}
    merged_result = merge_segment_results(segment_responses, analysis.mode)

    yield (
        "done",
        {
            **primary,
            "input": analysis.input,
            "result": merged_result,
            "intent": analysis.to_dict(),
            "segments": segment_responses,
            "route": {
                "discipline": primary.get("discipline"),
                "agent": primary.get("agent"),
                "mode": analysis.mode,
            },
            "conversation_id": conversation_id,
        },
    )
