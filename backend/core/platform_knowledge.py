"""
Contexto oficial do IA Server Santos para meta-perguntas (avaliação da plataforma).

Fonte: docs/project_state.md (control plane).
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from config.settings import BASE_DIR

PROJECT_STATE_PATH = BASE_DIR.parent / "docs" / "project_state.md"

# Resposta completa de avaliação da plataforma (stream + POST /chat)
PLATFORM_EVAL_RESPONSE_MAX_CHARS = 8000

_PLATFORM_EVAL_PHRASES = (
    "avaliação do ia server",
    "avaliacao do ia server",
    "avaliar o ia server",
    "avaliar o sistema",
    "avaliar a plataforma",
    "avaliação do sistema",
    "avaliacao do sistema",
    "avaliação da plataforma",
    "avaliacao da plataforma",
    "pontos fortes e fracos",
    "pontos fortes e fracos",
    "pontos fracos e fortes",
    "estrutura do sistema",
    "arquitetura do sistema",
    "estrutura da plataforma",
    "arquitetura da plataforma",
    "análise do sistema",
    "analise do sistema",
    "análise da plataforma",
    "analise da plataforma",
    "review da plataforma",
    "prós e contras",
    "pros e contras",
    "swot",
    "como está o projeto",
    "estado do projeto",
    "estado do sistema",
)

_PLATFORM_EVAL_WITH_PRODUCT = (
    "avali",
    "estrutura",
    "arquitetura",
    "pontos fortes",
    "pontos fracos",
    "fortes e fracos",
    "fracos e fortes",
    "review",
    "swot",
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def is_platform_evaluation_query(text: str) -> bool:
    """Detecta pedido de avaliação/meta-análise da plataforma (não engenharia)."""
    lower = _normalize(text)
    if not lower:
        return False
    if any(phrase in lower for phrase in _PLATFORM_EVAL_PHRASES):
        return True
    if re.search(r"pontos?\s+forte", lower) and re.search(r"pontos?\s+frac", lower):
        return True
    if re.search(r"pontos?\s+forte", lower) and (
        "ia server" in lower or "plataforma" in lower or "santos" in lower
    ):
        return True
    if "mostre os pontos" in lower and (
        "ia server" in lower or "plataforma" in lower or "santos" in lower
    ):
        return True
    if "quais os pontos" in lower and (
        "ia server" in lower or "plataforma" in lower or "santos" in lower
    ):
        return True
    if "ia server santos" in lower and any(k in lower for k in _PLATFORM_EVAL_WITH_PRODUCT):
        return True
    if "ia server" in lower and "avali" in lower:
        return True
    return False


_FOLLOW_UP_MARKERS = (
    "pontos fracos",
    "pontos forte",
    "pontos fortes",
    "pontos fraco",
    "e os fracos",
    "e os fortes",
    "mostre os fracos",
    "mostre os fortes",
    "continua a avaliação",
    "continua a avaliacao",
    "detalhe os pontos",
    "liste os pontos",
)


def is_platform_follow_up(full_thread: str, user_message: str) -> bool:
    """Follow-up curto após avaliação da plataforma na mesma conversa."""
    if is_platform_evaluation_query(user_message):
        return False
    lower = _normalize(user_message)
    if not lower:
        return False
    has_marker = any(m in lower for m in _FOLLOW_UP_MARKERS) or re.search(
        r"pontos?\s+frac", lower
    )
    if not has_marker:
        return False
    full_lower = _normalize(full_thread)
    return any(
        hint in full_lower
        for hint in (
            "ia server santos",
            "ia server",
            "avaliação técnica",
            "avaliacao tecnica",
            "platform_evaluation",
            "pontos fortes",
            "pontos fracos",
            "project_state",
        )
    )


def resolve_platform_evaluation_intent(text: str) -> bool:
    """True se a mensagem (ou follow-up na thread) pede avaliação da plataforma."""
    user_text = text
    from core.conversation_context import extract_latest_user_message

    if "NOVA MENSAGEM DO USUÁRIO:" in text:
        user_text = extract_latest_user_message(text)
    if is_platform_evaluation_query(user_text):
        return True
    if user_text != text and is_platform_follow_up(text, user_text):
        return True
    return False


def _extract_section(content: str, start_marker: str, end_markers: tuple[str, ...]) -> str:
    start = content.find(start_marker)
    if start < 0:
        return ""
    start += len(start_marker)
    end = len(content)
    for marker in end_markers:
        pos = content.find(marker, start)
        if pos >= 0:
            end = min(end, pos)
    return content[start:end].strip()


@lru_cache(maxsize=1)
def load_project_state_text() -> str:
    path = PROJECT_STATE_PATH
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def build_platform_context(max_chars: int = 7000) -> str:
    """Recorta seções relevantes do control plane para o LLM."""
    raw = load_project_state_text()
    if not raw:
        return (
            "Documentação project_state.md indisponível. "
            "Monorepo: backend/ (FastAPI) + frontend/ (Next.js) + docs/ + infra/."
        )

    parts: list[str] = []

    handoff = _extract_section(
        raw,
        "# 📤 HANDOFF — RESUMO PARA GPT / NOVA SESSÃO",
        ("# 🔥 0.", "# 🟢 1."),
    )
    if handoff:
        parts.append("## HANDOFF (resumo operacional)\n" + handoff)

    arch = _extract_section(
        raw,
        "# 🧠 4. ARQUITETURA ATUAL",
        ("# ⚙️ 5.", "# ⚠️ 6."),
    )
    if arch:
        parts.append("## ARQUITETURA ATUAL\n" + arch[:2500])

    risks = _extract_section(
        raw,
        "# ⚠️ 6. RISCOS E ISSUES CONHECIDOS",
        ("# 📋 7.", "# 📌 8."),
    )
    if risks:
        parts.append("## RISCOS E ISSUES\n" + risks)

    combined = "\n\n".join(parts).strip()
    if len(combined) > max_chars:
        combined = combined[: max_chars - 3].rsplit("\n", 1)[0] + "..."
    return combined


def _parse_status_rows(section: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in section.splitlines():
        if not line.strip().startswith("|"):
            continue
        if "---" in line or "Área" in line or "Area" in line:
            continue
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) >= 2:
            rows.append((cells[0], cells[1]))
    return rows


def format_platform_evaluation_fallback() -> str:
    """Resposta determinística (sem LLM) a partir do project_state."""
    raw = load_project_state_text()
    handoff = _extract_section(
        raw,
        "# 📤 HANDOFF — RESUMO PARA GPT / NOVA SESSÃO",
        ("# 🔥 0.", "# 🟢 1."),
    )
    status_rows = _parse_status_rows(handoff)

    strengths = [
        name for name, status in status_rows if "🟢" in status or "conclu" in status.lower()
    ]
    partial = [
        name for name, status in status_rows if "🟡" in status or "evolu" in status.lower()
    ]
    gaps = [
        name for name, status in status_rows if "🔴" in status or "não" in status.lower() or "nao" in status.lower()
    ]

    risks = _extract_section(
        raw,
        "# ⚠️ 6. RISCOS E ISSUES CONHECIDOS",
        ("# 📋 7.",),
    )
    risk_lines = [
        line.strip()
        for line in risks.splitlines()
        if line.strip().startswith("| R-")
    ]

    lines = [
        "## Estrutura do sistema",
        "",
        "Monorepo **IA Server Santos**: `backend/` (FastAPI, agentes, RAG, orçamento) + "
        "`frontend/` (Next.js) + `docs/project_state.md` (control plane) + `infra/` (PostgreSQL).",
        "",
        "Pipeline principal: **Intent Layer** → roteamento por disciplina → agentes inteligentes "
        "(RAG FAISS + Ollama) · orquestrador multi-domínio · módulos de orçamento, vision PCI, "
        "workflow de entrega e console operacional.",
        "",
        "## Pontos fortes",
        "",
    ]
    for item in strengths[:12]:
        lines.append(f"- {item}")
    if not strengths:
        lines.append("- Stack local completa (Ollama + FAISS + PostgreSQL)")
        lines.append("- Multiagente por disciplina com RAG normativo (~14k chunks NBR)")

    lines.extend(["", "## Pontos fracos", ""])
    for item in gaps:
        lines.append(f"- {item}")
    for item in partial[:6]:
        lines.append(f"- {item} (em evolução / parcial)")
    for risk in risk_lines[:8]:
        cells = [c.strip() for c in risk.split("|") if c.strip()]
        if len(cells) >= 3:
            lines.append(f"- **{cells[0]}** ({cells[1]}): {cells[2]}")
    if not gaps and not partial and not risk_lines:
        lines.append("- Auth SaaS ainda não implementado")
        lines.append("- Latência elevada com modelos pesados em GPU 8 GB")

    lines.extend(
        [
            "",
            "## Resumo",
            "",
            "Plataforma **madura para uso local** em engenharia civil multiagente, com RAG normativo "
            "e orçamento operacionais. Principais gaps: **autenticação**, **UI de alguns módulos** "
            "(Copilot/AED) e **operacionalização** de features ainda opt-in (Model Evaluation, Evolution Loop).",
            "",
            "_Fonte: `docs/project_state.md` (control plane)._",
        ]
    )
    return "\n".join(lines)


PLATFORM_EVALUATION_PROMPT = """Você é o ChatAgent do IA Server Santos respondendo uma **avaliação técnica da plataforma**.

REGRAS:
- Use SOMENTE o CONTEXTO OFICIAL abaixo (project_state.md). Não invente módulos ou status.
- Estruture em markdown com exatamente estas seções:
  ## Estrutura do sistema
  ## Pontos fortes
  ## Pontos fracos
  ## Resumo
- Seja **honesto e balanceado** — liste fraquezas reais (auth, latência, flags off, VRAM, etc.).
- NUNCA diga "não se preocupe com pontos fracos" nem evite a seção de fraquezas.
- Tom: técnico, direto, português brasileiro. Listas com bullets.
- 400–900 palavras no total.

CONTEXTO OFICIAL:
{context}

PERGUNTA DO USUÁRIO:
{text}

AVALIAÇÃO TÉCNICA:"""


def build_platform_evaluation_prompt(user_text: str) -> str:
    return PLATFORM_EVALUATION_PROMPT.format(
        context=build_platform_context(),
        text=user_text.strip(),
    )


def platform_evaluation_stream_recovery(partial: str) -> str:
    """
    Completa seções faltantes quando o stream LLM interrompe (timeout, VRAM, etc.).
    Usa fallback determinístico só para trechos ausentes ou incompletos.
    """
    visible = partial.strip()
    if not visible:
        return ""

    lower = visible.lower()
    fallback = format_platform_evaluation_fallback()
    parts: list[str] = []

    if "pontos fracos" not in lower:
        weak = _extract_section(fallback, "## Pontos fracos", ("## Resumo",))
        if weak:
            parts.append("\n\n## Pontos fracos\n\n" + weak)
    elif not re.search(r"##\s*resumo\b", lower, re.IGNORECASE):
        weak = _extract_section(fallback, "## Pontos fracos", ("## Resumo",))
        tail = visible.rsplit("pontos fracos", 1)[-1].strip()
        if weak and len(tail) < 120:
            parts.append("\n\n" + weak)

    if not re.search(r"##\s*resumo\b", lower, re.IGNORECASE):
        summary = _extract_section(fallback, "## Resumo", ("_Fonte",))
        if summary:
            parts.append("\n\n## Resumo\n\n" + summary)

    if parts:
        parts.append("\n\n---\n\n_Resposta completada a partir do control plane após interrupção do stream LLM._")
    return "".join(parts)
