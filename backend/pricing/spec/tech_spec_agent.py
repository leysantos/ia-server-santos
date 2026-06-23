"""Orquestração da Especificação Técnica — estrutura determinística, conteúdo por serviço via IA."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from pricing.budget.budget_calculator import BudgetCalculator
from pricing.budget.budget_session import BudgetSession
from pricing.spec.tech_spec_editor import resolve_spec_formatting
from pricing.spec.tech_spec_generator import (
    build_service_prompt,
    build_service_retry_prompt,
    count_services_in_etapa,
    default_etapa_intro,
    default_fields_for_service,
    is_fields_complete,
    merge_fields,
    parse_service_fields,
    render_service_markdown,
    stream_service_content,
)
from pricing.spec.tech_spec_models import TechSpecDocument, markdown_to_html, render_document_html
from pricing.spec.tech_spec_wbs import (
    assemble_spec_markdown,
    assemble_spec_markdown_partial,
    build_budget_context,
    collect_wbs_inventory,
    fallback_spec_markdown,
    find_missing_service_codes,
    iter_etapas,
    iter_spec_chunks,
)

__all__ = ["compose_tech_spec_stream", "build_budget_context", "collect_wbs_inventory"]

logger = logging.getLogger(__name__)

_DEFAULT_USER_PROMPT = (
    "Gerar especificação técnica completa da obra com base no orçamento, "
    "detalhando cada serviço (materiais, método executivo, medição e normas), "
    "organizado por etapa e sub-etapa."
)

_PREVIEW_EVERY_TOKENS = 4
_MAX_SERVICE_ATTEMPTS = 3


def compose_tech_spec_stream(
    session: BudgetSession,
    user_prompt: str = "",
    *,
    use_llm: bool = True,
    llm_client: Any | None = None,
) -> Iterator[tuple[str, dict[str, Any]]]:
    """
    Gera especificação técnica com eventos SSE: log | token | preview | done.

    Arquitetura:
    - Seções 1–5 e 7–11: montagem determinística (WBS/orçamento)
    - Seção 6: um serviço por chamada IA; estrutura Markdown fixa no código
    - Preview atualizado após cada serviço (e durante o stream do serviço atual)
    """
    prompt_text = (user_prompt or _DEFAULT_USER_PROMPT).strip()
    inv = collect_wbs_inventory(session.roots)
    calc = BudgetCalculator()
    row_count = sum(len(calc.flatten_rows(r)) for r in session.roots)
    formatting, format_logs = resolve_spec_formatting(session, prompt_text)

    yield "log", {
        "message": (
            f"Orçamento analisado — {row_count} linhas, "
            f"{inv.etapa_count} etapa(s), {inv.subetapa_count} sub-etapa(s), "
            f"{inv.servico_count} serviço(s)."
        ),
        "phase": "context",
    }
    for msg in format_logs:
        yield "log", {"message": msg, "phase": "format"}

    chunks = list(iter_spec_chunks(session.roots))
    if not chunks:
        yield "log", {"message": "Nenhum serviço encontrado no orçamento.", "phase": "error"}
        accumulated = fallback_spec_markdown(session)
        yield "preview", _preview_payload(accumulated, formatting)
        doc = _final_document(session, accumulated, formatting, None)
        yield "done", {"tech_spec": doc.to_dict(), "llm_model": None, "summary": "Esboço vazio.", "mode": "generate"}
        return

    service_blocks: dict[str, str] = {}
    etapa_intros: dict[str, str] = {}
    model_used: str | None = None
    total = len(chunks)

    # Preview inicial com cabeçalho (seções 1–5)
    yield "preview", _preview_payload(
        assemble_spec_markdown_partial(session, service_blocks, etapa_intros=etapa_intros),
        formatting,
        streaming_live=True,
    )

    if not use_llm:
        yield "log", {"message": "Gerando esboço heurístico (sem IA)…", "phase": "fallback"}
        accumulated = fallback_spec_markdown(session)
        yield "preview", _preview_payload(accumulated, formatting, streaming_live=False)
        doc = _final_document(session, accumulated, formatting, None)
        yield "done", {
            "tech_spec": doc.to_dict(),
            "llm_model": None,
            "summary": f"Esboço gerado ({len(accumulated)} caracteres).",
            "mode": "generate",
        }
        return

    try:
        client, model, fallback_models = _resolve_llm_client(llm_client)

        yield "log", {
            "message": (
                f"Geração serviço a serviço ({total} chamada(s) IA) — "
                f"modelo {model}."
            ),
            "phase": "llm",
        }

        accumulated, model_used = yield from _compose_by_service(
            session,
            client,
            model,
            fallback_models,
            prompt_text,
            formatting,
            chunks,
            service_blocks,
            etapa_intros,
        )

        missing = find_missing_service_codes(session.roots, accumulated)
        if missing:
            yield "log", {
                "message": (
                    f"Atenção: {len(missing)} serviço(s) sem cobertura "
                    f"({', '.join(missing[:8])}{'…' if len(missing) > 8 else ''})."
                ),
                "phase": "coverage",
            }

        yield "log", {"message": "Especificação técnica concluída.", "phase": "done"}

    except ConnectionError as exc:
        logger.warning("Ollama indisponível: %s", exc)
        yield "log", {
            "message": f"IA indisponível ({exc}) — gerando esboço heurístico.",
            "phase": "fallback",
        }
        accumulated = fallback_spec_markdown(session)
        yield "preview", _preview_payload(accumulated, formatting, streaming_live=False)
        model_used = None
    except Exception as exc:
        logger.exception("Falha na geração da especificação técnica")
        yield "log", {
            "message": f"Erro na geração ({exc}) — usando esboço parcial ou heurístico.",
            "phase": "fallback",
        }
        if service_blocks:
            accumulated = assemble_spec_markdown(session, service_blocks, etapa_intros)
        else:
            accumulated = fallback_spec_markdown(session)
        yield "preview", _preview_payload(accumulated, formatting, streaming_live=False)
        model_used = None

    doc = _final_document(session, accumulated.strip(), formatting, model_used)
    yield "done", {
        "tech_spec": doc.to_dict(),
        "llm_model": model_used,
        "summary": f"Especificação gerada ({len(accumulated)} caracteres).",
        "mode": "generate",
    }


def _resolve_llm_client(llm_client: Any | None) -> tuple[Any, str, list[str]]:
    if llm_client is not None:
        return llm_client, "injected", []

    from config.settings import get_settings
    from core.llm_override import get_llm_model_override
    from models.ollama_client import OllamaClient

    settings = get_settings()
    client = OllamaClient(timeout=settings.ollama_budget_timeout)
    model = get_llm_model_override() or settings.ollama_budget_model
    fallback = [settings.ollama_llm_fallback_model]
    return client, model, fallback


def _compose_by_service(
    session: BudgetSession,
    client: Any,
    model: str,
    fallback_models: list[str],
    user_prompt: str,
    formatting: dict[str, Any],
    chunks: list,
    service_blocks: dict[str, str],
    etapa_intros: dict[str, str],
) -> Iterator[tuple[str, dict[str, Any]]]:
    model_used = model
    total = len(chunks)
    seen_etapas: set[str] = set()

    for chunk in chunks:
        svc = chunk.services[0]
        etapa_code = chunk.etapa_code

        if chunk.include_etapa_heading and etapa_code not in seen_etapas:
            seen_etapas.add(etapa_code)
            etapa_item = next(e for e in iter_etapas(session.roots) if e.code == etapa_code)
            etapa_intros[etapa_code] = default_etapa_intro(
                etapa_item,
                count_services_in_etapa(session.roots, etapa_code),
            )

        etapa_item = next(e for e in iter_etapas(session.roots) if e.code == etapa_code)

        yield "log", {
            "message": f"[{chunk.part_index}/{total}] {svc.code} — {svc.name[:70]}",
            "phase": "llm",
        }

        prompt = build_service_prompt(session, svc, etapa_item, chunk.subetapa, user_prompt)

        parsed, final_text, svc_model = yield from _generate_service_with_retry(
            client,
            session,
            svc,
            prompt,
            model,
            fallback_models,
            service_blocks,
            etapa_intros,
            formatting,
            chunk.part_index,
            total,
        )

        if parsed and is_fields_complete(parsed):
            fields = parsed
        elif parsed:
            fields = merge_fields(parsed, default_fields_for_service(svc))
            yield "log", {
                "message": (
                    f"Serviço {svc.code}: campos parciais após {_MAX_SERVICE_ATTEMPTS} tentativa(s) "
                    "— completado com fallback."
                ),
                "phase": "coverage",
            }
        else:
            fields = default_fields_for_service(svc)
            yield "log", {
                "message": (
                    f"Serviço {svc.code}: conteúdo padrão aplicado "
                    f"(sem resposta válida após {_MAX_SERVICE_ATTEMPTS} tentativa(s))."
                ),
                "phase": "coverage",
            }

        block = render_service_markdown(svc, fields)
        service_blocks[svc.code] = block
        model_used = svc_model

        accumulated = assemble_spec_markdown_partial(
            session,
            service_blocks,
            etapa_intros=etapa_intros,
            include_closing=(chunk.part_index == total),
        )
        yield "preview", _preview_payload(
            accumulated,
            formatting,
            progress_current=chunk.part_index,
            progress_total=total,
            streaming_live=False,
        )

    return assemble_spec_markdown(session, service_blocks, etapa_intros), model_used


def _model_for_attempt(model: str, fallback_models: list[str], attempt: int) -> str:
    """Tenta modelo principal; na 3ª tentativa usa fallback se existir."""
    if attempt >= 3 and fallback_models:
        return fallback_models[0]
    return model


def _generate_service_with_retry(
    client: Any,
    session: BudgetSession,
    svc,
    base_prompt: str,
    model: str,
    fallback_models: list[str],
    service_blocks: dict[str, str],
    etapa_intros: dict[str, str],
    formatting: dict[str, Any],
    part_index: int,
    part_total: int,
) -> Iterator[tuple[str, dict[str, Any]]]:
    parsed = None
    final_text = ""
    svc_model = model

    for attempt in range(1, _MAX_SERVICE_ATTEMPTS + 1):
        if attempt > 1:
            yield "log", {
                "message": (
                    f"Serviço {svc.code}: resposta incompleta — "
                    f"retentativa {attempt}/{_MAX_SERVICE_ATTEMPTS}…"
                ),
                "phase": "llm",
            }

        use_model = _model_for_attempt(model, fallback_models, attempt)
        prompt = build_service_retry_prompt(base_prompt, attempt)
        partial_text = ""
        token_count = 0
        attempt_text = ""

        try:
            for event_type, payload in stream_service_content(
                client,
                prompt,
                svc.code,
                model=use_model,
                fallback_models=fallback_models if use_model == model else None,
            ):
                if event_type == "token":
                    partial_text += payload["token"]
                    token_count += 1
                    yield "token", {"token": payload["token"]}
                    if token_count % _PREVIEW_EVERY_TOKENS == 0:
                        yield from _emit_service_preview(
                            session,
                            service_blocks,
                            etapa_intros,
                            svc,
                            partial_text,
                            formatting,
                            part_index,
                            part_total,
                        )
                elif event_type == "guard":
                    yield "log", payload
                elif event_type == "complete":
                    attempt_text = payload.get("text") or partial_text
                    svc_model = payload.get("model") or use_model
        except Exception as exc:
            logger.warning(
                "Serviço %s tentativa %s: falha IA (%s)",
                svc.code,
                attempt,
                exc,
            )
            if attempt == _MAX_SERVICE_ATTEMPTS:
                yield "log", {
                    "message": f"Serviço {svc.code}: IA falhou após todas as tentativas.",
                    "phase": "fallback",
                }
            continue

        final_text = attempt_text
        parsed = parse_service_fields(final_text)
        if is_fields_complete(parsed):
            if attempt > 1:
                yield "log", {
                    "message": f"Serviço {svc.code}: especificação obtida na tentativa {attempt}.",
                    "phase": "done",
                }
            break

    return parsed, final_text, svc_model


def _emit_service_preview(
    session: BudgetSession,
    service_blocks: dict[str, str],
    etapa_intros: dict[str, str],
    svc,
    partial_text: str,
    formatting: dict[str, Any],
    part_index: int,
    part_total: int,
) -> Iterator[tuple[str, dict[str, Any]]]:
    blocks = dict(service_blocks)
    fields = merge_fields(parse_service_fields(partial_text), default_fields_for_service(svc))
    blocks[svc.code] = render_service_markdown(svc, fields)
    markdown = assemble_spec_markdown_partial(
        session,
        blocks,
        etapa_intros=etapa_intros,
        include_closing=False,
    )
    yield "preview", _preview_payload(
        markdown,
        formatting,
        progress_current=part_index,
        progress_total=part_total,
        streaming_live=True,
    )


def _final_document(
    session: BudgetSession,
    markdown: str,
    formatting: dict[str, Any],
    model_used: str | None,
) -> TechSpecDocument:
    title = f"Especificação Técnica — {session.project.projeto or session.title}"
    doc = TechSpecDocument(
        title=title,
        markdown=markdown,
        html_content=markdown_to_html(markdown),
        formatting=formatting,
        llm_model=model_used,
    )
    doc.touch()
    return doc


def _preview_payload(
    markdown: str,
    formatting: dict[str, Any],
    *,
    progress_current: int | None = None,
    progress_total: int | None = None,
    streaming_live: bool = False,
) -> dict[str, Any]:
    doc = TechSpecDocument(markdown=markdown, formatting=formatting)
    payload: dict[str, Any] = {
        "markdown": markdown,
        "html_content": render_document_html(doc),
        "formatting": formatting,
        "streaming_live": streaming_live,
    }
    if progress_current is not None and progress_total is not None:
        payload["progress"] = {"current": progress_current, "total": progress_total}
    return payload
