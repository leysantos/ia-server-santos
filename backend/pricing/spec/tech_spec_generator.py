"""Geração de conteúdo técnico por serviço — estrutura no código, texto pela IA."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from pricing.budget.budget_session import BudgetSession
from pricing.models.budget_item import BudgetItem
from pricing.spec.tech_spec_stream_utils import generate_stream_guarded
from pricing.spec.tech_spec_wbs import sanitize_llm_chunk, truncate_at_extra_service

_FIELD_LABELS = (
    "Descrição",
    "Materiais",
    "Método executivo",
    "Critério de medição",
    "Base de Preços",
    "Normas aplicáveis",
)

_LLM_OPTIONS = {
    "num_predict": 2048,
    "temperature": 0.35,
    "repeat_penalty": 1.25,
    "repeat_last_n": 64,
}


@dataclass
class ServiceSpecFields:
    descricao: str
    materiais: str
    metodo_executivo: str
    criterio_medicao: str
    base_precos: str
    normas: str


def default_etapa_intro(etapa: BudgetItem, service_count: int) -> str:
    return (
        f"A presente etapa compreende **{etapa.name}**, englobando **{service_count}** "
        "serviço(s) do orçamento. Seguem as especificações técnicas de cada item, "
        "com materiais, métodos executivos, critérios de medição e referências normativas."
    )


def count_services_in_etapa(roots: list[BudgetItem], etapa_code: str) -> int:
    from pricing.spec.tech_spec_wbs import iter_ordered_services

    return sum(1 for etapa, _sub, _svc in iter_ordered_services(roots) if etapa.code == etapa_code)


def service_to_dict(
    svc: BudgetItem,
    etapa: BudgetItem,
    sub: BudgetItem | None,
) -> dict[str, Any]:
    mem = svc.calculation_note or ""
    for child in svc.children:
        if child.calculation_note or child.name:
            if child.metadata.get("is_memory_row") or child.row_type == "MEMORIA":
                mem = child.calculation_note or child.name or mem
    row: dict[str, Any] = {
        "codigo_wbs": svc.code,
        "descricao": svc.name,
        "quantidade": svc.quantity,
        "unidade": svc.unit or "un",
        "etapa": f"{etapa.code} — {etapa.name}",
    }
    if sub:
        row["sub_etapa"] = f"{sub.code} — {sub.name}"
    if svc.source_code:
        row["base_preco"] = (svc.source_base or "SINAPI").strip()
        row["codigo_composicao"] = str(svc.source_code)
    if mem:
        row["memoria_calculo"] = mem[:500]
    return row


def obra_summary(session: BudgetSession) -> str:
    proj = session.project
    return (
        f"Obra: {proj.projeto or session.title}\n"
        f"Local: {proj.local or '—'}\n"
        f"Objeto: {proj.objeto or '—'}"
    )


def build_service_prompt(
    session: BudgetSession,
    svc: BudgetItem,
    etapa: BudgetItem,
    sub: BudgetItem | None,
    user_instructions: str,
) -> str:
    data = service_to_dict(svc, etapa, sub)
    instructions = user_instructions.strip() or (
        "Detalhar cada campo com linguagem técnica de engenharia civil brasileira."
    )
    return (
        "Você é engenheiro civil redator de especificações técnicas para obras públicas e privadas.\n\n"
        f"INSTRUÇÕES DO USUÁRIO:\n{instructions}\n\n"
        f"CONTEXTO DA OBRA:\n{obra_summary(session)}\n\n"
        f"DADOS DO SERVIÇO (JSON):\n{json.dumps(data, ensure_ascii=False, indent=2)}\n\n"
        "Redija SOMENTE os seis campos abaixo, neste formato Markdown exato "
        "(sem cabeçalhos, sem código WBS, sem ```):\n\n"
        "**Descrição:** parágrafo(s) técnicos — escopo, premissas e interfaces\n"
        "**Materiais:** especificação de insumos, materiais e equipamentos\n"
        "**Método executivo:** sequência de execução, EPI/EPC e controle de qualidade\n"
        f"**Critério de medição:** unidade {data['unidade']}, fórmula e aceitação\n"
        "**Base de Preços:** cite base e código quando existirem no JSON\n"
        "**Normas aplicáveis:** NBRs/NRs específicas DESTE serviço (não repita listas genéricas)\n"
    )


def parse_service_fields(text: str) -> ServiceSpecFields | None:
    """Extrai os seis campos do texto da IA."""
    cleaned = sanitize_llm_chunk(text)
    if not cleaned:
        return None

    values: dict[str, str] = {}
    for label in _FIELD_LABELS:
        pat = rf"\*\*{re.escape(label)}:\*\*\s*(.*?)(?=\n\*\*|\Z)"
        m = re.search(pat, cleaned, re.I | re.S)
        if m:
            val = m.group(1).strip()
            if val:
                values[label] = re.sub(r"\n{3,}", "\n\n", val)

    if len(values) < 3:
        return None

    return ServiceSpecFields(
        descricao=values.get("Descrição", ""),
        materiais=values.get("Materiais", ""),
        metodo_executivo=values.get("Método executivo", ""),
        criterio_medicao=values.get("Critério de medição", ""),
        base_precos=values.get("Base de Preços", ""),
        normas=values.get("Normas aplicáveis", ""),
    )


def default_fields_for_service(svc: BudgetItem) -> ServiceSpecFields:
    """Fallback determinístico quando a IA falha ou retorna conteúdo inválido."""
    unit = svc.unit or "un"
    qty = svc.quantity
    name = svc.name
    lower = name.lower()

    if any(k in lower for k in ("mão de obra", "encarregado", "engenheiro", "vigia", "almoxarife", "auxiliar")):
        materiais = "Não aplicável — serviço de mão de obra conforme composição de preços."
        metodo = (
            "Mobilização do profissional qualificado; cumprimento das atribuições da função; "
            "registro em diário de obra; EPI conforme NR-06; integração com equipe e fiscalização."
        )
    elif "concreto" in lower:
        materiais = "Concreto usinado conforme traço e fck do projeto; agregados, cimento e aditivos previstos."
        metodo = "Preparo da superfície; lançamento e adensamento; cura úmida; controle de slump e moldagem de CP."
    elif "locação" in lower or "container" in lower:
        materiais = "Equipamento/container conforme composição e memorial descritivo."
        metodo = "Transporte, posicionamento, nivelamento, fixação quando necessário e retirada ao término."
    elif "escavação" in lower or "vala" in lower:
        materiais = "Sem fornecimento permanente; ferramentas e EPI conforme NR-18."
        metodo = "Demarcação, escavação conforme projeto, proteção de taludes e descarte de material."
    else:
        materiais = "Materiais e insumos conforme composição de preço unitário e memorial descritivo."
        metodo = (
            "Executar conforme projeto, sequência operacional da obra, "
            "controle tecnológico e requisitos de segurança (EPI/EPC)."
        )

    base = "Conforme bases de preços do orçamento."
    if svc.source_code:
        base_label = (svc.source_base or "SINAPI").strip()
        base = f"{base_label} — código {svc.source_code}"

    return ServiceSpecFields(
        descricao=f"{name}. Quantidade contratada: {qty:g} {unit}.",
        materiais=materiais,
        metodo_executivo=metodo,
        criterio_medicao=(
            f"Medição por **{unit}**, conforme quantidade executada e aceita na fiscalização "
            f"({qty:g} {unit} orçados)."
        ),
        base_precos=base,
        normas=_suggest_norms(name),
    )


def _suggest_norms(name: str) -> str:
    lower = name.lower()
    norms = ["NR-18 (segurança na construção civil)"]
    if any(k in lower for k in ("concreto", "lastro", "formas")):
        norms.extend(["NBR 6118", "NBR 12655"])
    if "escavação" in lower or "vala" in lower:
        norms.append("NBR 8681")
    if "armadura" in lower or "aço" in lower:
        norms.extend(["NBR 6118", "NBR 7480"])
    if "termoplást" in lower or "sinalização" in lower:
        norms.append("NBR 14636")
    if any(k in lower for k in ("mão de obra", "encarregado", "engenheiro", "vigia")):
        norms.extend(["NR-01", "NR-06"])
    if len(norms) == 1:
        norms.append("Normas ABNT aplicáveis ao serviço")
    return "; ".join(dict.fromkeys(norms))


_MAX_SERVICE_ATTEMPTS = 3
_MIN_DESCRICAO_CHARS = 40

_RETRY_SUFFIX = (
    "\n\nATENÇÃO: resposta anterior incompleta ou genérica. "
    "Preencha OBRIGATORIAMENTE os seis campos com conteúdo técnico detalhado "
    "(mínimo 2 frases em Descrição e Método executivo). "
    "Não omita nenhum campo."
)


def is_fields_complete(fields: ServiceSpecFields | None) -> bool:
    """True quando todos os seis campos têm conteúdo utilizável."""
    if not fields:
        return False
    parts = (
        fields.descricao,
        fields.materiais,
        fields.metodo_executivo,
        fields.criterio_medicao,
        fields.base_precos,
        fields.normas,
    )
    if not all(p and p.strip() for p in parts):
        return False
    return len(fields.descricao.strip()) >= _MIN_DESCRICAO_CHARS


def build_service_retry_prompt(base_prompt: str, attempt: int) -> str:
    if attempt <= 1:
        return base_prompt
    return base_prompt + _RETRY_SUFFIX


def merge_fields(parsed: ServiceSpecFields | None, fallback: ServiceSpecFields) -> ServiceSpecFields:
    if not parsed:
        return fallback
    return ServiceSpecFields(
        descricao=parsed.descricao or fallback.descricao,
        materiais=parsed.materiais or fallback.materiais,
        metodo_executivo=parsed.metodo_executivo or fallback.metodo_executivo,
        criterio_medicao=parsed.criterio_medicao or fallback.criterio_medicao,
        base_precos=parsed.base_precos or fallback.base_precos,
        normas=parsed.normas or fallback.normas,
    )


def render_service_markdown(svc: BudgetItem, fields: ServiceSpecFields) -> str:
    """Monta bloco Markdown com estrutura fixa — IA só preenche o conteúdo."""
    return "\n".join(
        [
            f"#### SUB-ETAPA {svc.code} — {svc.name}",
            "",
            f"**Código WBS:** {svc.code}",
            f"**Descrição:** {fields.descricao}",
            f"**Materiais:** {fields.materiais}",
            f"**Método executivo:** {fields.metodo_executivo}",
            f"**Critério de medição:** {fields.criterio_medicao}",
            f"**Base de Preços:** {fields.base_precos}",
            f"**Normas aplicáveis:** {fields.normas}",
        ]
    )


def stream_service_content(
    client: Any,
    prompt: str,
    service_code: str,
    *,
    model: str,
    fallback_models: list[str] | None,
) -> Iterator[tuple[str, dict[str, Any]]]:
    """
    Stream de geração de um serviço.
    Yields: ('token', {token}), ('guard', {...}), ('complete', {text, model})
    """
    accumulated = ""
    for event_type, payload in generate_stream_guarded(
        client,
        prompt,
        model=model,
        fallback_models=fallback_models,
        options=_LLM_OPTIONS,
        max_chars=6_000,
        max_token_events=3_000,
        yield_all_tokens=True,
    ):
        if event_type == "token":
            accumulated += payload["token"]
            yield "token", payload
        elif event_type == "guard":
            yield "guard", payload
        elif event_type == "complete":
            text = truncate_at_extra_service(
                sanitize_llm_chunk(payload.get("text") or accumulated),
                service_code,
            )
            yield "complete", {"text": text, "model": payload.get("model")}
