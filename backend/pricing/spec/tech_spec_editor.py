"""Edição da Especificação Técnica via prompt (formatação + IA)."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from pricing.spec.tech_spec_models import TechSpecDocument, markdown_to_html, render_document_html

logger = logging.getLogger(__name__)

_EDIT_HINT = """
Você está EDITANDO um documento existente de Especificação Técnica.
- Retorne o documento COMPLETO atualizado em Markdown (corpo do texto, sem cabeçalho de logo).
- Preserve o conteúdo existente salvo se o usuário pedir remoção ou substituição explícita.
- Para pedidos de título, seções ou parágrafos novos, integre de forma coerente.
- Não inclua comentários meta — apenas o Markdown do corpo.
- Logo e numeração de páginas são tratados pelo sistema; foque no conteúdo textual.
"""


@dataclass
class FormatEditResult:
    formatting: dict[str, Any]
    logs: list[str] = field(default_factory=list)
    body_changed: bool = False
    new_markdown: str | None = None


def apply_format_edits_from_prompt(
    doc: TechSpecDocument,
    prompt: str,
) -> FormatEditResult:
    """Interpreta pedidos de formatação (título, logo, numeração) no prompt."""
    lower = prompt.lower()
    fmt = dict(doc.formatting or {})
    logs: list[str] = []
    body_changed = False
    new_markdown = doc.markdown

    if _wants_page_numbers(lower):
        fmt["page_numbers"] = True
        logs.append("Numeração de páginas ativada no rodapé do preview e export Word.")

    logo_label = _extract_logo_label(prompt)
    if logo_label is not None:
        fmt["logo_text"] = logo_label
        logs.append(f"Placeholder de logo adicionado: «{logo_label}».")

    title = _extract_title_request(prompt)
    if title:
        fmt["document_title"] = title
        logs.append(f"Título do documento definido: «{title}».")
        if not re.search(rf"^#\s+{re.escape(title)}", new_markdown or "", re.M | re.I):
            prefix = f"# {title}\n\n"
            if not (new_markdown or "").lstrip().startswith("#"):
                new_markdown = prefix + (new_markdown or "")
                body_changed = True
                logs.append("Título inserido no início do corpo do documento.")

    return FormatEditResult(
        formatting=fmt,
        logs=logs,
        body_changed=body_changed,
        new_markdown=new_markdown if body_changed else None,
    )


def _wants_page_numbers(text: str) -> bool:
    return bool(
        re.search(r"numera(c|ç)[aã]o", text)
        and re.search(r"p[aá]gina", text)
        or re.search(r"n[uú]mero\s+d[aeo]\s+p[aá]gina", text)
        or "page number" in text
    )


def _extract_logo_label(prompt: str) -> str | None:
    if "logo" not in prompt.lower():
        return None
    patterns = [
        r"logo\s*(?:\(\s*([^)]+)\s*\)|\[\s*([^\]]+)\]|:\s*([^\n.]+)|\s+([A-Za-z0-9À-ú\s]{2,40}))",
        r"(?:adicione|inclua|insira)\s+(?:a\s+)?logo\s+(?:da?\s+)?(.+?)(?:\.|$|\n)",
    ]
    for pat in patterns:
        m = re.search(pat, prompt, re.I)
        if m:
            label = next((g.strip() for g in m.groups() if g and g.strip()), "")
            if label and len(label) < 80:
                return label.strip(" .\"'")
    return "Logo da empresa"


def _extract_title_request(prompt: str) -> str | None:
    patterns = [
        r"(?:adicione|inclua|insira|coloque)\s+(?:o\s+)?t[ií]tulo\s+[«\"']?([^«\"'\n.]+)[«\"']?",
        r"t[ií]tulo\s*(?:\(\s*([^)]+)\s*\)|:\s*([^\n.]+)|[«\"']([^«\"']+)[«\"'])",
    ]
    for pat in patterns:
        m = re.search(pat, prompt, re.I)
        if m:
            title = next((g.strip() for g in m.groups() if g and g.strip()), "")
            if title and len(title) < 200:
                return title.strip(" .\"'")
    return None


def _is_format_only_prompt(prompt: str) -> bool:
    """Heurística: pedido só de layout (sem reescrita de conteúdo)."""
    lower = prompt.lower()
    has_format = (
        _wants_page_numbers(lower)
        or "logo" in lower
        or bool(_extract_title_request(prompt))
    )
    content_verbs = (
        "reescrev",
        "altere a seção",
        "modifique o parágrafo",
        "detalhe",
        "expanda",
        "corrija",
        "citar nbr",
        "adicionar seção",
        "remova",
    )
    has_content = any(v in lower for v in content_verbs)
    return has_format and not has_content


def edit_tech_spec_stream(
    current: TechSpecDocument,
    user_prompt: str,
    *,
    budget_context: str = "",
    use_llm: bool = True,
    llm_client: Any | None = None,
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Edita documento existente — formatação instantânea + stream LLM do corpo."""
    prompt_text = user_prompt.strip()
    if not prompt_text:
        yield "error", {"message": "Informe o que deseja alterar no prompt.", "phase": "error"}
        return

    working = TechSpecDocument.from_dict(current.to_dict()) or current
    fmt_result = apply_format_edits_from_prompt(working, prompt_text)
    working.formatting = fmt_result.formatting

    for msg in fmt_result.logs:
        yield "log", {"message": msg, "phase": "format"}

    if fmt_result.new_markdown is not None:
        working.markdown = fmt_result.new_markdown
        working.html_content = markdown_to_html(working.markdown)

    yield "preview", {
        "markdown": working.markdown,
        "html_content": render_document_html(working),
        "formatting": working.formatting,
        "partial": True,
    }

    if _is_format_only_prompt(prompt_text):
        working.touch()
        yield "log", {"message": "Formatação aplicada (sem reescrita IA do corpo).", "phase": "done"}
        yield "done", {
            "tech_spec": working.to_dict(),
            "summary": "Documento atualizado — formatação aplicada.",
            "mode": "edit",
        }
        return

    accumulated = working.markdown or ""
    model_used: str | None = working.llm_model

    if use_llm:
        try:
            from config.settings import get_settings
            from core.llm_override import get_llm_model_override
            from models.ollama_client import OllamaClient

            settings = get_settings()
            client = llm_client or OllamaClient(timeout=settings.ollama_budget_timeout)
            model = get_llm_model_override() or settings.ollama_budget_model

            yield "log", {
                "message": f"IA editando documento ({model})…",
                "phase": "llm",
            }

            full_prompt = (
                f"{_EDIT_HINT}\n\n"
                f"PEDIDO DO USUÁRIO:\n{prompt_text}\n\n"
                f"DOCUMENTO ATUAL (Markdown — corpo):\n{working.markdown or '(vazio)'}\n\n"
            )
            if budget_context:
                full_prompt += f"CONTEXTO DO ORÇAMENTO (referência):\n{budget_context[:6000]}\n\n"
            full_prompt += "Retorne o documento COMPLETO atualizado em Markdown:"

            accumulated = ""
            for token, used in client.generate_stream(
                full_prompt,
                model=model,
                fallback_models=[settings.ollama_llm_fallback_model],
            ):
                model_used = used
                accumulated += token
                yield "token", {"token": token}
                if len(accumulated) % 60 < len(token):
                    body_html = markdown_to_html(accumulated)
                    working.markdown = accumulated
                    working.html_content = body_html
                    yield "preview", {
                        "markdown": accumulated,
                        "html_content": render_document_html(working),
                        "formatting": working.formatting,
                        "partial": True,
                    }

            if not accumulated.strip():
                raise ValueError("Modelo retornou resposta vazia na edição")

            working.markdown = accumulated.strip()
            working.html_content = markdown_to_html(working.markdown)
            working.llm_model = model_used
            yield "log", {"message": "Edição IA concluída.", "phase": "done"}
        except Exception as exc:
            logger.warning("TechSpec edit LLM falhou: %s", exc)
            yield "log", {
                "message": f"IA indisponível ({exc}) — mantidas alterações de formatação.",
                "phase": "fallback",
            }
            if not fmt_result.logs:
                yield "error", {"message": str(exc), "phase": "error"}
                return

    working.touch()
    yield "preview", {
        "markdown": working.markdown,
        "html_content": render_document_html(working),
        "formatting": working.formatting,
        "partial": False,
    }
    yield "done", {
        "tech_spec": working.to_dict(),
        "llm_model": model_used,
        "summary": f"Documento editado ({len(working.markdown)} caracteres).",
        "mode": "edit",
    }
