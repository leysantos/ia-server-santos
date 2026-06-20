"""Agente IA — gera Especificação Técnica a partir do orçamento completo."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from pricing.budget.budget_calculator import BudgetCalculator
from pricing.budget.budget_session import BudgetSession
from pricing.spec.tech_spec_models import TechSpecDocument, markdown_to_html, render_document_html

logger = logging.getLogger(__name__)

_DEFAULT_USER_PROMPT = (
    "Gerar especificação técnica completa da obra com base no orçamento, "
    "detalhando materiais, métodos executivos, critérios de medição e "
    "referências normativas por etapa."
)

_SECTIONS_HINT = """
Estruture o documento em Markdown com estas seções (use ## para títulos):
1. OBJETO DA ESPECIFICAÇÃO
2. FINALIDADE
3. LOCALIZAÇÃO E CARACTERIZAÇÃO DA OBRA
4. REFERÊNCIAS NORMATIVAS
5. DESCRIÇÃO GERAL DOS SERVIÇOS
6. ESPECIFICAÇÕES POR ETAPA (uma subseção ### por etapa do orçamento)
7. MATERIAIS
8. MÉTODOS EXECUTIVOS
9. CRONOGRAMA DE EXECUÇÃO (se houver dados)
10. MEDIÇÃO, FISCALIZAÇÃO E RECEBIMENTO
11. CONSIDERAÇÕES FINAIS

Regras:
- Linguagem técnica em português brasileiro, adequada a licitações/obras públicas.
- Cite códigos WBS do orçamento ao descrever cada etapa.
- Não invente serviços que não existam no orçamento.
- Use listas com marcadores quando apropriado.
- Seja objetivo e completo.
"""


def _fmt_money(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _task_start(task: Any) -> str | None:
    return task.manual_start or task.early_start or task.late_start


def _task_finish(task: Any) -> str | None:
    return task.early_finish or task.late_finish


def build_budget_context(session: BudgetSession) -> str:
    calc = BudgetCalculator()
    rows: list[dict[str, Any]] = []
    for root in session.roots:
        rows.extend(calc.flatten_rows(root))

    proj = session.project
    lines = [
        f"Título do orçamento: {session.title}",
        f"Projeto/Obra: {proj.projeto or session.title}",
        f"Objeto: {proj.objeto or '-'}",
        f"Local: {proj.local or '-'}",
        f"Empresa/Contratante: {proj.empresa or '-'}",
        f"Responsável técnico: {proj.responsavel_tecnico or '-'}",
        f"Base de preços: {proj.base_preco or '-'}",
        f"Tipo de obra (BDI): {proj.obra_type or 'RF'}",
        f"Total ComD: {_fmt_money(session.grand_total_comd)}",
        f"Total SemD: {_fmt_money(session.grand_total_semd)}",
        f"Total adotado (menor): {_fmt_money(session.grand_total)}",
        "",
        "=== ESTRUTURA DO ORÇAMENTO (WBS) ===",
    ]

    etapas = [r for r in rows if r.get("level") == 1]
    for etapa in etapas:
        code = etapa.get("code", "")
        lines.append(f"\n## ETAPA {code} — {etapa.get('name', '')}")
        subetapas = [r for r in rows if r.get("parent_code") == code and r.get("level") == 2]
        for sub in subetapas:
            sc = sub.get("code", "")
            lines.append(f"  Sub-etapa {sc}: {sub.get('name', '')}")
            services = [
                r
                for r in rows
                if r.get("parent_code") == sc
                and r.get("row_type") in ("service", "composition", "")
                and float(r.get("quantity") or 0) > 0
            ]
            for svc in services[:40]:
                qty = svc.get("quantity", 0)
                unit = svc.get("unit", "")
                total = svc.get("total_price") or svc.get("total_price_semd") or 0
                note = svc.get("calculation_note") or ""
                line = (
                    f"    - [{svc.get('code')}] {svc.get('name')} | "
                    f"Qtd: {qty} {unit} | Total: {_fmt_money(float(total))}"
                )
                if note:
                    line += f" | Memória: {note[:120]}"
                lines.append(line)

    if session.schedule and session.schedule.tasks:
        lines.extend(["", "=== CRONOGRAMA ==="])
        lines.append(f"Início: {session.schedule.project_start or '-'}")
        lines.append(f"Término: {session.schedule.project_end or '-'}")
        for task in session.schedule.leaf_tasks()[:30]:
            start = _task_start(task) or "?"
            finish = _task_finish(task) or "?"
            lines.append(
                f"  - {task.budget_code or task.task_id}: {task.name} | "
                f"{task.duration_days} dias | {start} → {finish}"
            )

    if session.calculation_memory:
        lines.extend(["", "=== MEMÓRIA DE CÁLCULO (trechos) ==="])
        for entry in session.calculation_memory[:15]:
            lines.append(f"  - {entry.get('label') or entry.get('code')}: {entry.get('formula') or entry.get('note') or ''}")

    return "\n".join(lines)


def _fallback_markdown(session: BudgetSession, context: str) -> str:
    proj = session.project
    title = proj.projeto or session.title
    parts = [
        f"# ESPECIFICAÇÃO TÉCNICA\n",
        f"**Obra:** {title}\n",
        f"**Local:** {proj.local or 'A definir'}\n",
        f"**Valor global de referência:** {_fmt_money(session.grand_total)}\n",
        "\n## 1. OBJETO DA ESPECIFICAÇÃO\n",
        f"Especificação técnica dos serviços constantes do orçamento **{session.title}**, "
        f"para orientar a execução, fiscalização e medição dos serviços.\n",
        "\n## 2. FINALIDADE\n",
        "Definir materiais, métodos executivos e critérios de aceitação alinhados ao orçamento.\n",
        "\n## 5. DESCRIÇÃO GERAL DOS SERVIÇOS\n",
        "Os serviços estão organizados conforme WBS do orçamento:\n",
    ]
    calc = BudgetCalculator()
    rows: list[dict[str, Any]] = []
    for root in session.roots:
        rows.extend(calc.flatten_rows(root))
    for etapa in [r for r in rows if r.get("level") == 1]:
        parts.append(f"\n### Etapa {etapa.get('code')} — {etapa.get('name')}\n")
        parts.append(
            "Executar os serviços descritos no orçamento observando normas técnicas "
            "aplicáveis e boas práticas de engenharia.\n"
        )
    parts.append("\n## 11. CONSIDERAÇÕES FINAIS\n")
    parts.append("Documento gerado automaticamente a partir do orçamento (modo heurístico).\n")
    return "".join(parts)


def compose_tech_spec_stream(
    session: BudgetSession,
    user_prompt: str = "",
    *,
    use_llm: bool = True,
    llm_client: Any | None = None,
) -> Iterator[tuple[str, dict[str, Any]]]:
    """
    Gera especificação técnica com eventos para SSE:
    log | token | preview | done | error
    """
    prompt_text = (user_prompt or _DEFAULT_USER_PROMPT).strip()
    context = build_budget_context(session)
    calc = BudgetCalculator()
    row_count = sum(len(calc.flatten_rows(r)) for r in session.roots)

    yield "log", {"message": f"Orçamento analisado — {row_count} linhas na planilha.", "phase": "context"}
    yield "log", {"message": "Montando contexto do projeto e WBS…", "phase": "context"}

    accumulated = ""
    model_used: str | None = None

    if use_llm:
        try:
            from config.settings import get_settings
            from core.llm_override import get_llm_model_override
            from models.ollama_client import OllamaClient

            settings = get_settings()
            client = llm_client or OllamaClient(timeout=settings.ollama_budget_timeout)
            model = get_llm_model_override() or settings.ollama_budget_model
            full_prompt = (
                "Você é engenheiro civil redator de especificações técnicas para obras.\n\n"
                f"INSTRUÇÕES DO USUÁRIO:\n{prompt_text}\n\n"
                f"{_SECTIONS_HINT}\n\n"
                f"DADOS DO ORÇAMENTO:\n{context}\n\n"
                "Responda APENAS com o documento em Markdown, sem prefácio."
            )

            yield "log", {
                "message": f"Enviando orçamento ao modelo ({model})…",
                "phase": "llm",
            }

            for token, used in client.generate_stream(
                full_prompt,
                model=model,
                fallback_models=[settings.ollama_llm_fallback_model],
            ):
                model_used = used
                accumulated += token
                yield "token", {"token": token}
                if len(accumulated) % 80 < len(token):
                    partial_doc = TechSpecDocument(markdown=accumulated)
                    yield "preview", {
                        "markdown": accumulated,
                        "html_content": render_document_html(partial_doc),
                    }

            if not accumulated.strip():
                raise ValueError("Modelo retornou resposta vazia")

            yield "log", {"message": "Especificação gerada pelo modelo.", "phase": "done"}
        except Exception as exc:
            logger.warning("TechSpec LLM falhou, usando fallback: %s", exc)
            yield "log", {
                "message": f"IA indisponível ({exc}) — gerando esboço heurístico.",
                "phase": "fallback",
            }
            accumulated = _fallback_markdown(session, context)
            for chunk in _chunk_text(accumulated, 40):
                yield "token", {"token": chunk}
            yield "preview", {
                "markdown": accumulated,
                "html_content": render_document_html(
                    TechSpecDocument(markdown=accumulated)
                ),
            }
    else:
        yield "log", {"message": "Gerando esboço heurístico (sem IA)…", "phase": "fallback"}
        accumulated = _fallback_markdown(session, context)
        for chunk in _chunk_text(accumulated, 40):
            yield "token", {"token": chunk}
        yield "preview", {
            "markdown": accumulated,
            "html_content": render_document_html(TechSpecDocument(markdown=accumulated)),
        }

    title = f"Especificação Técnica — {session.project.projeto or session.title}"
    doc = TechSpecDocument(
        title=title,
        markdown=accumulated.strip(),
        html_content=markdown_to_html(accumulated.strip()),
        llm_model=model_used,
    )
    doc.touch()

    yield "done", {
        "tech_spec": doc.to_dict(),
        "llm_model": model_used,
        "summary": f"Especificação gerada ({len(accumulated)} caracteres).",
        "mode": "generate",
    }


def _chunk_text(text: str, size: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]
