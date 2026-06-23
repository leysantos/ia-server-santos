"""Montagem do contexto WBS para especificação técnica — percorre etapas/sub-etapas/serviços."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterator

from pricing.budget.budget_session import BudgetSession
from pricing.budget.ppd_layout import ROW_TYPE_ETAPA, ROW_TYPE_SERVICO, ROW_TYPE_SUB_ETAPA
from pricing.models.budget_item import BudgetItem


def _is_memory_item(item: BudgetItem) -> bool:
    return bool(item.metadata.get("is_memory_row")) or item.row_type == "MEMORIA"


def _fmt_money(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@dataclass
class WbsInventory:
    etapas: list[str] = field(default_factory=list)
    subetapas: list[str] = field(default_factory=list)
    servicos: list[str] = field(default_factory=list)

    @property
    def etapa_count(self) -> int:
        return len(self.etapas)

    @property
    def subetapa_count(self) -> int:
        return len(self.subetapas)

    @property
    def servico_count(self) -> int:
        return len(self.servicos)


def collect_wbs_inventory(roots: list[BudgetItem]) -> WbsInventory:
    inv = WbsInventory()

    for etapa in iter_etapas(roots):
        inv.etapas.append(etapa.code)
        for child in etapa.children:
            if child.row_type == ROW_TYPE_SUB_ETAPA and not _is_memory_item(child):
                inv.subetapas.append(child.code)
    for _, _, svc in iter_ordered_services(roots):
        inv.servicos.append(svc.code)

    return inv


def _format_service_line(item: BudgetItem, indent: int) -> str:
    prefix = "  " * indent
    qty = item.quantity
    unit = item.unit or ""
    total = float(item.total_price or item.total_price_semd or 0)
    line = (
        f"{prefix}- [{item.code}] {item.name} | "
        f"Qtd: {qty:g} {unit} | Total: {_fmt_money(total)}"
    )
    if item.source_code:
        line += f" | Base: {item.source_base or ''} {item.source_code}".strip()
    if item.calculation_note:
        line += f" | Memória: {item.calculation_note[:200]}"
    return line


def _append_group_children(lines: list[str], container: BudgetItem, indent: int, inv: WbsInventory) -> None:
    for child in container.children:
        if _is_memory_item(child):
            continue
        if child.row_type == ROW_TYPE_SUB_ETAPA:
            lines.append(f"{'  ' * indent}### SUB-ETAPA {child.code} — {child.name}")
            _append_group_children(lines, child, indent + 1, inv)
        elif child.row_type == ROW_TYPE_SERVICO:
            lines.append(_format_service_line(child, indent + 1))
            for mem in child.children:
                if _is_memory_item(mem) and (mem.calculation_note or mem.name):
                    lines.append(
                        f"{'  ' * (indent + 2)}Memória de cálculo: {mem.calculation_note or mem.name}"
                    )
        elif child.children:
            _append_group_children(lines, child, indent, inv)


def build_wbs_context_lines(roots: list[BudgetItem]) -> tuple[list[str], WbsInventory]:
    lines: list[str] = []
    inv = collect_wbs_inventory(roots)

    for etapa in roots:
        if etapa.row_type != ROW_TYPE_ETAPA or _is_memory_item(etapa):
            continue
        lines.append(f"\n## ETAPA {etapa.code} — {etapa.name}")
        _append_group_children(lines, etapa, indent=0, inv=inv)

    return lines, inv


def inventory_prompt_block(inv: WbsInventory) -> list[str]:
    lines = [
        "",
        "=== INVENTÁRIO WBS (COBRIR TODOS NA SEÇÃO 6) ===",
        f"Total: {inv.etapa_count} etapa(s), {inv.subetapa_count} sub-etapa(s), {inv.servico_count} serviço(s).",
    ]
    if inv.etapas:
        lines.append(f"Etapas obrigatórias: {', '.join(inv.etapas)}")
    if inv.subetapas:
        lines.append(f"Sub-etapas obrigatórias: {', '.join(inv.subetapas)}")
    lines.append(
        "Na seção 6, use ### ETAPA X — nome para cada etapa e #### SUB-ETAPA X.Y — nome "
        "para cada sub-etapa, detalhando todos os serviços listados abaixo de cada grupo."
    )
    return lines


def build_budget_context(session: BudgetSession) -> str:
    proj = session.project
    wbs_lines, inv = build_wbs_context_lines(session.roots)

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
        *wbs_lines,
        *inventory_prompt_block(inv),
    ]

    if session.schedule and session.schedule.tasks:
        lines.extend(["", "=== CRONOGRAMA ==="])
        lines.append(f"Início: {session.schedule.project_start or '-'}")
        lines.append(f"Término: {session.schedule.project_end or '-'}")
        for task in session.schedule.leaf_tasks():
            start = task.manual_start or task.early_start or task.late_start or "?"
            finish = task.early_finish or task.late_finish or "?"
            lines.append(
                f"  - {task.budget_code or task.task_id}: {task.name} | "
                f"{task.duration_days} dias | {start} → {finish}"
            )

    if session.calculation_memory:
        lines.extend(["", "=== MEMÓRIA DE CÁLCULO (trechos) ==="])
        for entry in session.calculation_memory[:40]:
            label = entry.get("label") or entry.get("code") or entry.get("name") or "?"
            detail = entry.get("formula") or entry.get("note") or ""
            lines.append(f"  - {label}: {detail}")

    return "\n".join(lines)


def iter_etapas(roots: list[BudgetItem]) -> list[BudgetItem]:
    etapas = [
        etapa
        for etapa in roots
        if etapa.row_type == ROW_TYPE_ETAPA and not _is_memory_item(etapa)
    ]
    return sorted(etapas, key=lambda e: _wbs_sort_key(e.code))


def _wbs_sort_key(code: str) -> tuple:
    parts: list[tuple[int, object]] = []
    for segment in (code or "0").split("."):
        segment = segment.strip()
        if segment.isdigit():
            parts.append((0, int(segment)))
        else:
            parts.append((1, segment))
    return tuple(parts) if parts else ((0, 0),)


def _collect_services_under(container: BudgetItem) -> list[BudgetItem]:
    """Lista serviços (folhas) sob um grupo, na ordem do orçamento."""
    found: list[BudgetItem] = []

    def walk(node: BudgetItem) -> None:
        for child in node.children:
            if _is_memory_item(child):
                continue
            if child.row_type == ROW_TYPE_SERVICO:
                found.append(child)
            elif child.children:
                walk(child)

    walk(container)
    return found


def iter_ordered_services(roots: list[BudgetItem]) -> Iterator[tuple[BudgetItem, BudgetItem | None, BudgetItem]]:
    """
    Percorre serviços na ordem do orçamento.
    Yields (etapa, sub_etapa_ou_none, serviço).
    """
    for etapa in iter_etapas(roots):
        subetapas = [
            c
            for c in etapa.children
            if c.row_type == ROW_TYPE_SUB_ETAPA and not _is_memory_item(c)
        ]
        if subetapas:
            for sub in subetapas:
                for svc in _collect_services_under(sub):
                    yield etapa, sub, svc
            continue
        for svc in _collect_services_under(etapa):
            yield etapa, None, svc


@dataclass
class SpecGenerationChunk:
    """Um bloco WBS para geração isolada (evita loop e estouro de contexto)."""

    etapa_code: str
    etapa_name: str
    label: str
    context: str
    service_codes: list[str] = field(default_factory=list)
    services: list[BudgetItem] = field(default_factory=list)
    subetapa: BudgetItem | None = None
    subetapa_code: str | None = None
    subetapa_name: str | None = None
    part_index: int = 1
    part_total: int = 1
    include_etapa_heading: bool = False


def iter_spec_chunks(
    roots: list[BudgetItem],
    *,
    max_services_per_chunk: int = 1,
) -> Iterator[SpecGenerationChunk]:
    """
    Um bloco por serviço (padrão) para garantir cobertura e ordem do orçamento.
    """
    seen_etapas: set[str] = set()
    ordered = list(iter_ordered_services(roots))
    total = len(ordered)
    if total == 0:
        return

    for idx, (etapa, sub, svc) in enumerate(ordered, start=1):
        include_etapa = etapa.code not in seen_etapas
        if include_etapa:
            seen_etapas.add(etapa.code)

        if sub:
            title = f"SUB-ETAPA {sub.code} — {sub.name}"
            ctx_lines = [
                f"## ETAPA {etapa.code} — {etapa.name}",
                f"### {title}",
                _format_service_line(svc, indent=1),
            ]
        else:
            title = f"SUB-ETAPA {svc.code} — {svc.name}"
            ctx_lines = [
                f"## ETAPA {etapa.code} — {etapa.name}",
                _format_service_line(svc, indent=0),
            ]

        yield SpecGenerationChunk(
            etapa_code=etapa.code,
            etapa_name=etapa.name,
            label=f"serviço {svc.code} ({idx}/{total}) — {svc.name[:60]}",
            context="\n".join(ctx_lines),
            service_codes=[svc.code],
            services=[svc],
            subetapa=sub,
            subetapa_code=sub.code if sub else None,
            subetapa_name=sub.name if sub else None,
            part_index=idx,
            part_total=total,
            include_etapa_heading=include_etapa,
        )


def _batch_list(items: list[BudgetItem], size: int) -> list[list[BudgetItem]]:
    if size < 1:
        return [items]
    return [items[i : i + size] for i in range(0, len(items), size)]


def truncate_at_extra_service(text: str, service_code: str) -> str:
    """Corta se o modelo repetir outro serviço ou seção (anti-loop por item)."""
    if not text:
        return ""
    pattern = rf"\n####\s+SUB-ETAPA\s+(?!{re.escape(service_code)}\b)"
    m = re.search(pattern, text, re.I)
    if m:
        return text[: m.start()].strip()
    for marker in ("\n### ETAPA", "\n## 7.", "\n## 6.", "\n```"):
        idx = text.find(marker)
        if idx > 80:
            return text[:idx].strip()
    return text.strip()


def sanitize_llm_chunk(text: str) -> str:
    """Remove cercas de código, separadores e prefácios comuns do modelo."""
    t = (text or "").strip()
    t = re.sub(r"```(?:markdown|md)?\s*", "", t, flags=re.I)
    t = re.sub(r"```\s*", "", t)
    t = re.sub(r"^\s*---+\s*\n", "", t)
    t = re.sub(r"\n---+\s*\n", "\n", t)
    t = re.sub(
        r"^(?:#+\s*)?(?:ETAPA|SUB-ETAPA)\s+\d[^\n]*\n+(?=\*\*Código WBS)",
        "",
        t,
        count=1,
        flags=re.I | re.M,
    )
    return t.strip()


def format_service_spec_block(svc: BudgetItem, *, subetapa: BudgetItem | None = None) -> str:
    """Bloco determinístico de especificação para um serviço (fallback ordenado)."""
    _ = subetapa
    lines = [
        f"#### SUB-ETAPA {svc.code} — {svc.name}",
        "",
        f"**Código WBS:** {svc.code}",
        f"**Descrição:** {svc.name}.",
        f"**Quantidade:** {svc.quantity:g} {svc.unit or 'un'}",
    ]
    if svc.source_code:
        base = (svc.source_base or "SINAPI").strip()
        lines.append(f"**Base de Preços:** {base} {svc.source_code}")
    if svc.calculation_note:
        lines.append(f"**Memória de cálculo:** {svc.calculation_note[:300]}")
    lines.extend(
        [
            "**Materiais:** Conforme composição de preço unitário e especificação do fabricante.",
            "**Método executivo:** Executar conforme projeto, memória de cálculo e boas práticas de engenharia.",
            "**Critério de medição:** Medição pela unidade contratada ({unit}) executada e aceita.".format(
                unit=svc.unit or "un"
            ),
            "**Normas aplicáveis:** Conforme referências do orçamento e normas técnicas vigentes.",
        ]
    )
    return "\n".join(lines)


def normalize_service_block(
    svc: BudgetItem,
    llm_text: str,
    roots: list[BudgetItem],
    *,
    subetapa: BudgetItem | None = None,
) -> str:
    """Garante bloco válido para um serviço — usa IA sanitizada ou fallback."""
    cleaned = sanitize_llm_chunk(llm_text)
    if cleaned and _is_service_mentioned(svc.code, roots, cleaned):
        heading = f"#### SUB-ETAPA {svc.code} — {svc.name}"
        if not re.search(rf"\*\*Código WBS:\*\*\s*{re.escape(svc.code)}", cleaned, re.I):
            cleaned = f"{heading}\n\n{cleaned}"
        return cleaned.strip()
    return format_service_spec_block(svc, subetapa=subetapa)


def build_section_six_ordered(
    roots: list[BudgetItem],
    service_blocks: dict[str, str],
    etapa_intros: dict[str, str] | None = None,
) -> str:
    """Monta a seção 6 na ordem exata do orçamento."""
    lines: list[str] = []
    last_etapa: str | None = None
    intros = etapa_intros or {}

    for etapa, sub, svc in iter_ordered_services(roots):
        _ = sub
        if etapa.code != last_etapa:
            lines.append(f"\n### ETAPA {etapa.code} — {etapa.name}\n")
            intro = intros.get(etapa.code)
            if intro:
                lines.append(intro)
                lines.append("")
            last_etapa = etapa.code

        block = service_blocks.get(svc.code) or format_service_spec_block(svc, subetapa=sub)
        lines.append(block.strip())
        lines.append("")

    return "\n".join(lines).strip()


def assemble_spec_from_etapas(
    session: BudgetSession,
    etapa_sections: dict[str, str],
    *,
    current_etapa_code: str | None = None,
    current_partial: str = "",
    include_closing: bool = True,
) -> str:
    """Documento completo a partir de trechos Markdown por etapa (ordem do orçamento)."""
    header = build_obra_and_bases_markdown(session)
    parts: list[str] = []
    for etapa in iter_etapas(session.roots):
        if etapa.code in etapa_sections:
            parts.append(sanitize_llm_chunk(etapa_sections[etapa.code]))
        elif etapa.code == current_etapa_code:
            if current_partial.strip():
                parts.append(sanitize_llm_chunk(current_partial))
            else:
                parts.append(
                    f"### ETAPA {etapa.code} — {etapa.name}\n\n*Redigindo especificação desta etapa…*"
                )
        elif include_closing:
            parts.append(_fallback_etapa_markdown(session, etapa))
    section_six = "\n\n".join(p for p in parts if p.strip())
    if include_closing:
        closing = build_closing_markdown(session)
        return f"{header.rstrip()}\n\n{section_six}\n{closing}"
    return f"{header.rstrip()}\n\n{section_six}"


def _fallback_etapa_markdown(session: BudgetSession, etapa: BudgetItem) -> str:
    """Fallback por etapa quando a IA falha — ainda lista todos os serviços."""
    lines = [f"### ETAPA {etapa.code} — {etapa.name}", ""]
    for _etapa, sub, svc in iter_ordered_services(session.roots):
        if _etapa.code != etapa.code:
            continue
        lines.append(format_service_spec_block(svc, subetapa=sub).strip())
        lines.append("")
    return "\n".join(lines).strip()


def truncate_at_next_etapa(text: str, etapa_code: str) -> str:
    """Remove conteúdo se o modelo começar outra etapa."""
    if not text:
        return ""
    pattern = rf"\n###\s+ETAPA\s+(?!{re.escape(etapa_code)}\b)"
    m = re.search(pattern, text, re.I)
    if m:
        return text[: m.start()].strip()
    for marker in ("\n## 7.", "\n## 7 ", "\n## 6.", "\n```"):
        idx = text.find(marker)
        if idx > 120:
            return text[:idx].strip()
    return text.strip()


def assemble_spec_markdown(
    session: BudgetSession,
    service_blocks: dict[str, str],
    etapa_intros: dict[str, str] | None = None,
) -> str:
    """Documento completo: capa + seção 6 ordenada + fechamento."""
    header = build_obra_and_bases_markdown(session)
    section_six = build_section_six_ordered(session.roots, service_blocks, etapa_intros)
    closing = build_closing_markdown(session)
    return f"{header.rstrip()}\n\n{section_six}\n{closing}"


def assemble_spec_markdown_partial(
    session: BudgetSession,
    service_blocks: dict[str, str],
    *,
    etapa_intros: dict[str, str] | None = None,
    include_closing: bool = False,
) -> str:
    """Preview incremental durante a geração serviço a serviço."""
    header = build_obra_and_bases_markdown(session)
    section_six = build_section_six_ordered(session.roots, service_blocks, etapa_intros)
    if include_closing:
        return f"{header.rstrip()}\n\n{section_six}\n{build_closing_markdown(session)}"
    return f"{header.rstrip()}\n\n{section_six}"


def is_service_covered(code: str, roots: list[BudgetItem], markdown: str) -> bool:
    return _is_service_mentioned(code, roots, markdown)


def find_missing_service_codes(roots: list[BudgetItem], markdown: str) -> list[str]:
    """Serviços do WBS sem menção plausível no markdown gerado."""
    inv = collect_wbs_inventory(roots)
    section_six = _extract_section_six(markdown)
    search_text = section_six if section_six else markdown
    return [code for code in inv.servicos if not _is_service_mentioned(code, roots, search_text)]


def _extract_section_six(markdown: str) -> str:
    """Trecho da seção 6 até o início da seção 7 (evita falsos positivos no rodapé)."""
    m = re.search(
        r"##\s*6\.\s*ESPECIFICAÇÕES POR ETAPA(.*?)(?=##\s*7\.|\Z)",
        markdown,
        re.I | re.S,
    )
    return m.group(1) if m else ""


def _service_by_code(roots: list[BudgetItem], code: str) -> BudgetItem | None:
    for etapa in iter_etapas(roots):
        for svc in _collect_services_under(etapa):
            if svc.code == code:
                return svc
    return None


def _normalize_lookup(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").upper().strip())


def _is_service_mentioned(code: str, roots: list[BudgetItem], markdown: str) -> bool:
    svc = _service_by_code(roots, code)
    if re.search(rf"\[{re.escape(code)}\]", markdown):
        return True
    if re.search(
        rf"(?:^|[\s#*(\[]){re.escape(code)}(?:\s*[—\-–.:)]|\s|$)",
        markdown,
        re.M,
    ):
        return True
    if svc:
        name = _normalize_lookup(svc.name)
        if len(name) >= 12 and name in _normalize_lookup(markdown):
            return True
        if svc.source_code and re.search(rf"\b{re.escape(str(svc.source_code))}\b", markdown):
            return True
    return False


def append_missing_services_fallback(
    session: BudgetSession,
    markdown: str,
    missing_codes: list[str],
) -> str:
    """Insere serviços faltantes na seção 6 (antes do fechamento), não após a seção 11."""
    if not missing_codes:
        return markdown

    code_set = set(missing_codes)
    bullets: list[str] = []
    for etapa in iter_etapas(session.roots):
        for svc in _collect_services_under(etapa):
            if svc.code not in code_set:
                continue
            bullets.append(
                f"- **{svc.code}** — {svc.name} ({svc.quantity:g} {svc.unit or 'un'}): "
                "executar conforme orçamento, memória de cálculo e normas aplicáveis; "
                "medição pela unidade contratada."
            )
    if not bullets:
        return markdown

    block = "\n".join(
        ["", "#### Serviços pendentes de detalhamento", "", *bullets, ""]
    )

    marker = re.search(r"##\s*7\.\s*MATERIAIS", markdown, re.I)
    if marker:
        idx = marker.start()
        return markdown[:idx].rstrip() + block + "\n\n" + markdown[idx:]

    return markdown.rstrip() + block


def build_single_etapa_context(etapa: BudgetItem) -> str:
    lines = [f"## ETAPA {etapa.code} — {etapa.name}"]
    inv = WbsInventory()
    _append_group_children(lines, etapa, indent=0, inv=inv)
    return "\n".join(lines)


def build_obra_and_bases_markdown(session: BudgetSession) -> str:
    proj = session.project
    obra = proj.projeto or session.title or "—"
    lines = [
        "# ESPECIFICAÇÃO TÉCNICA",
        "",
        f"**Título do orçamento:** {session.title}",
        "",
        "## 1. OBJETO DA ESPECIFICAÇÃO",
        "",
        f"Especificação técnica dos serviços da obra **{obra}**, conforme orçamento "
        f"de referência, para orientar execução, fiscalização e medição.",
        "",
        "## 2. FINALIDADE",
        "",
        "Definir materiais, métodos executivos, critérios de aceitação e medição "
        "alinhados ao orçamento e às normas técnicas aplicáveis.",
        "",
        "## 3. DADOS DA OBRA",
        "",
        f"- **Obra / Projeto:** {obra}",
        f"- **Objeto:** {proj.objeto or '—'}",
        f"- **Local:** {proj.local or '—'}",
        f"- **Empresa / Contratante:** {proj.empresa or '—'}",
        f"- **Responsável técnico:** {proj.responsavel_tecnico or '—'}",
        f"- **Código do orçamento:** {proj.orcamento or '—'}",
        f"- **Tipo de obra (BDI):** {proj.obra_type or 'RF'}",
        f"- **Valor global (ComD):** {_fmt_money(session.grand_total_comd)}",
        f"- **Valor global (SemD):** {_fmt_money(session.grand_total_semd)}",
        "",
        "## 4. BASES DE PREÇOS UTILIZADAS",
        "",
    ]
    bases = list(proj.price_bases or [])
    if bases:
        for base in bases:
            if not base.get("enabled", True):
                continue
            label = base.get("label") or base.get("source", "").upper()
            uf = base.get("uf") or "—"
            ref = base.get("reference") or "—"
            lines.append(f"- **{label}** — UF {uf} — período/referência: `{ref}`")
    else:
        lines.append(f"- {proj.base_preco or 'Conforme orçamento'}")
    lines.extend(
        [
            "",
            "## 5. DESCRIÇÃO GERAL DOS SERVIÇOS",
            "",
            "Os serviços estão organizados por etapas e sub-etapas (WBS), "
            "detalhados na seção 6.",
            "",
            "## 6. ESPECIFICAÇÕES POR ETAPA",
            "",
        ]
    )
    return "\n".join(lines)


def build_closing_markdown(session: BudgetSession) -> str:
    lines = [
        "",
        "## 7. MATERIAIS",
        "",
        "Utilizar materiais conforme especificado em cada serviço e normas de referência.",
        "",
        "## 8. MÉTODOS EXECUTIVOS",
        "",
        "Executar conforme detalhamento por serviço na seção 6 e boas práticas de engenharia.",
        "",
    ]
    if session.schedule and session.schedule.tasks:
        lines.extend(
            [
                "## 9. CRONOGRAMA DE EXECUÇÃO",
                "",
                f"- Início previsto: {session.schedule.project_start or '—'}",
                f"- Término previsto: {session.schedule.project_end or '—'}",
                "",
            ]
        )
    lines.extend(
        [
            "## 10. MEDIÇÃO, FISCALIZAÇÃO E RECEBIMENTO",
            "",
            "Medir cada serviço conforme unidade e quantidade do orçamento. "
            "Fiscalização conforme contrato e normas aplicáveis.",
            "",
            "## 11. CONSIDERAÇÕES FINAIS",
            "",
            "Documento gerado a partir do orçamento vigente. "
            "Alterações de escopo devem refletir aditivo contratual e revisão orçamentária.",
            "",
        ]
    )
    return "\n".join(lines)


def fallback_spec_markdown(session: BudgetSession) -> str:
    inv = collect_wbs_inventory(session.roots)
    blocks: dict[str, str] = {}
    etapa_intros: dict[str, str] = {}
    from pricing.spec.tech_spec_generator import default_etapa_intro

    for etapa in iter_etapas(session.roots):
        count = sum(1 for e, _s, _v in iter_ordered_services(session.roots) if e.code == etapa.code)
        etapa_intros[etapa.code] = default_etapa_intro(etapa, count)
    for _etapa, sub, svc in iter_ordered_services(session.roots):
        blocks[svc.code] = format_service_spec_block(svc, subetapa=sub)

    body = assemble_spec_markdown(session, blocks, etapa_intros)
    return f"{body}\n\n_Gerado automaticamente ({inv.etapa_count} etapas, {inv.servico_count} serviços)._"


def _append_fallback_group(parts: list[str], container: BudgetItem) -> None:
    for child in container.children:
        if _is_memory_item(child):
            continue
        if child.row_type == ROW_TYPE_SUB_ETAPA:
            parts.append(f"\n#### SUB-ETAPA {child.code} — {child.name}\n")
            parts.append(
                "Executar os serviços desta sub-etapa conforme orçamento, normas técnicas "
                "aplicáveis e memória de cálculo.\n"
            )
            _append_fallback_group(parts, child)
        elif child.row_type == ROW_TYPE_SERVICO:
            parts.append(
                f"- **{child.code}** — {child.name} ({child.quantity:g} {child.unit or 'un'})\n"
            )
        elif child.children:
            _append_fallback_group(parts, child)
