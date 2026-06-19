"""
Orquestrador multi-disciplinar do IA Server Santos.

Camada acima de router, dispatcher e RAG v2 — não os substitui.
"""

import re
from typing import Optional

from core.agent_registry import get_agent_name
from core.context_graph import ContextGraph
from core.dispatcher import AGENTS, dispatch
from memory.rag_engine import RAGEngine, get_rag_engine

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
]

KEYWORD_DISCIPLINES: dict[str, list[str]] = {
    "ARQUITETURA": [
        "arquitet", "layout", "fachada", "plant", "habitabilidade", "residencial",
        "comercial", "prédio", "edific",
    ],
    "ESTRUTURAL": [
        "estrutur", "viga", "pilar", "laje", "concreto", "aço", "fundação",
        "armadura", "protens",
    ],
    "HIDROSSANITÁRIO": [
        "hidrául", "hidraul", "hidrossanit", "esgoto", "água fria", "agua fria",
        "sanitário", "sanitario", "caixa d'água", "caixa dagua", "tubulação",
    ],
    "DRENAGEM": ["drenagem", "pluvial", "bocas de lobo", "galeria pluvial"],
    "ELÉTRICA": ["elétric", "eletric", "energia", "quadro elétrico", "iluminação"],
    "TELECOM": ["telecom", "dados", "cabeamento estruturado", "fibra"],
    "INCÊNDIO": ["incêndio", "incendio", "sprinkler", "hidrante", "pci", "escape"],
    "GEOTECNIA": ["geotéc", "geotec", "solo", "spt", "aterro", "estabilidade"],
    "TRANSPORTES": ["rodovi", "paviment", "tráfego", "trafego", "sinalização"],
    "INFRAESTRUTURA": ["infraestrutur", "obra civil", "terraplanagem"],
    "SANEAMENTO": ["saneamento", "eta", "ete", "coleta de esgoto"],
    "GEOPROCESSAMENTO": ["geoprocess", "shapefile", "gis", "coordenadas"],
    "TOPOGRAFIA": ["topograf", "levantamento", "altimétr", "altimetr"],
    "ORÇAMENTO": ["orçament", "orcament", "custo", "budget", "sinapi", "bdí"],
    "MEIO_AMBIENTE": ["ambient", "licenciamento", "eia", "rima", "conama"],
}

BUILDING_TRIGGERS = ["prédio", "predio", "edific", "residencial", "comercial", "condomínio"]
BUILDING_DEFAULTS = ["INCÊNDIO", "ORÇAMENTO"]


def _normalize_discipline(raw: str) -> Optional[str]:
    token = raw.strip().upper().replace("-", "_").replace(" ", "_")
    token = token.replace("HIDROSSANITARIO", "HIDROSSANITÁRIO")
    token = token.replace("ELETRICA", "ELÉTRICA")
    token = token.replace("INCENDIO", "INCÊNDIO")
    token = token.replace("ORCAMENTO", "ORÇAMENTO")
    return token if token in VALID_DISCIPLINES else None


def _parse_disciplines_from_llm(response: str) -> list[str]:
    found: list[str] = []
    for part in re.split(r"[,;\n|]+", response):
        discipline = _normalize_discipline(part)
        if discipline and discipline not in found:
            found.append(discipline)
    return found


def _decompose_by_keywords(text: str) -> list[str]:
    lowered = text.lower()
    found: list[str] = []

    for discipline, keywords in KEYWORD_DISCIPLINES.items():
        if any(kw in lowered for kw in keywords):
            found.append(discipline)

    if any(trigger in lowered for trigger in BUILDING_TRIGGERS):
        for discipline in BUILDING_DEFAULTS:
            if discipline not in found:
                found.append(discipline)

    return found


def _decompose_by_llm(text: str) -> list[str]:
    from config import settings

    prompt = f"""
Você é um engenheiro coordenador multidisciplinar.

Analise o problema e liste TODAS as disciplinas de engenharia necessárias.

Disciplinas válidas (use exatamente estes nomes):
{", ".join(VALID_DISCIPLINES)}

REGRAS:
- responda apenas com nomes de disciplinas separados por vírgula
- sem explicações
- inclua disciplinas implícitas (ex.: prédio → INCÊNDIO, ORÇAMENTO)
- mínimo 1 disciplina

EXEMPLOS:
"projeto de prédio residencial com estrutura e hidráulica" -> ESTRUTURAL, HIDROSSANITÁRIO, INCÊNDIO, ORÇAMENTO
"dimensionar viga de concreto" -> ESTRUTURAL
"rede de esgoto e drenagem pluvial" -> HIDROSSANITÁRIO, DRENAGEM, SANEAMENTO

PROBLEMA:
{text}
"""
    if settings.USE_MODEL_ROUTER or settings.USE_MODEL_EVALUATION:
        from core.models.model_router import routed_generate

        response, _model = routed_generate(
            prompt,
            "orchestration_synthesis",
            context={"text": text},
            module="orchestrator",
        )
        return _parse_disciplines_from_llm(response.strip().lower())

    from core.router import call_llm

    response = call_llm(prompt)
    return _parse_disciplines_from_llm(response)


def decompose_problem(text: str) -> list[str]:
    """Decompõe problema em disciplinas; filtra domínio via engineering orchestrator."""
    disciplines: list[str] = []

    try:
        disciplines = _decompose_by_llm(text)
    except Exception:
        disciplines = []

    if not disciplines:
        disciplines = _decompose_by_keywords(text)

    if not disciplines:
        disciplines = ["ESTRUTURAL"]

    from config import settings

    if settings.USE_ENGINEERING_ORCHESTRATOR:
        from core.orchestrator.engineering_orchestrator import filter_disciplines_by_domain

        disciplines = filter_disciplines_by_domain(text, disciplines)

    return disciplines


def execute_agents(
    route_result: dict,
    use_rag: bool = True,
    rag_engine: Optional[RAGEngine] = None,
    persist: bool = True,
    context_graph: Optional[ContextGraph] = None,
) -> list[dict]:
    """Executa agentes por disciplina com plano do orquestrador inteligente."""
    user_input = route_result.get("input", "")
    disciplines = route_result.get("disciplines")

    if not disciplines:
        disciplines = decompose_problem(user_input)

    engine = rag_engine or get_rag_engine()
    responses: list[dict] = []

    for discipline in disciplines:
        if discipline not in AGENTS:
            response = {
                "discipline": discipline,
                "agent": get_agent_name(discipline),
                "input": user_input,
                "result": f"Disciplina '{discipline}' não possui agente registrado.",
                "error": True,
            }
            if context_graph is not None:
                context_graph.add_result(discipline=discipline, data=response)
            responses.append(response)
            continue

        agent_route = {
            "input": user_input,
            "discipline": discipline,
            "agent": get_agent_name(discipline),
            "_conversation_id": route_result.get("_conversation_id"),
            "_orchestrator_log_id": route_result.get("_orchestrator_log_id"),
        }

        from config import settings

        if settings.USE_ENGINEERING_ORCHESTRATOR:
            from core.orchestrator.engineering_orchestrator import prepare_agent_execution

            agent_route = prepare_agent_execution(agent_route, user_input)

        if use_rag:
            engine = rag_engine or get_rag_engine()
            agent_route = engine.enrich_route_result(agent_route)
        else:
            agent_route["_use_rag"] = False

        response = dispatch(agent_route, persist=persist)

        if context_graph is not None:
            discipline_key = response.get("discipline", discipline)
            context_graph.add_result(
                discipline=discipline_key,
                data=response,
            )

        responses.append(response)

    return responses


def synthesize_results(results: list[dict], context: Optional[str] = None) -> dict:
    """Agrega respostas individuais em relatório técnico unificado."""
    if context:
        context_section = f"\n## CONTEXTO GLOBAL DO PROJETO\n{context}\n"
    else:
        context_section = ""

    by_discipline: dict[str, dict] = {}
    sections: list[str] = []
    normas: set[str] = set()
    rag_active = False

    for item in results:
        discipline = item.get("discipline", "DESCONHECIDA")
        by_discipline[discipline] = item

        result_text = item.get("result") or item.get("response", "")
        agent_name = item.get("agent", "agente")
        sections.append(f"## {discipline}\nAgente: {agent_name}\n\n{result_text}")

        extra = item.get("extra", {})
        for norma in extra.get("normas_base", []):
            normas.add(norma)
        if extra.get("rag", {}).get("active"):
            rag_active = True

    technical_summary = (
        f"Análise multidisciplinar concluída com {len(results)} especialidade(s).\n"
        f"Disciplinas: {', '.join(by_discipline.keys())}."
    )
    if normas:
        technical_summary += f"\nNormas de referência: {', '.join(sorted(normas))}."
    if rag_active:
        technical_summary += "\nContexto normativo RAG aplicado em uma ou mais disciplinas."

    discipline_report = "\n\n".join(sections)

    conclusion = (
        "Conclusão geral: o IA Server Santos processou o problema de forma "
        "coordenada entre as disciplinas identificadas. "
        "Recomenda-se validação técnica detalhada por especialista responsável "
        "em cada área antes de uso em projeto executivo."
    )

    final_report = (
        f"# Relatório Técnico Multidisciplinar\n\n"
        f"## Resumo\n{technical_summary}\n\n"
        f"## Análises por Disciplina\n\n{discipline_report}\n\n"
        f"## Conclusão Geral\n{conclusion}"
    )
    final_report = context_section + final_report

    return {
        "technical_summary": technical_summary,
        "by_discipline": by_discipline,
        "discipline_sections": discipline_report,
        "general_conclusion": conclusion,
        "final_report": final_report,
        "global_context": context or "",
    }


def process_multi_domain_request(
    text: str,
    use_rag: bool = True,
    rag_engine: Optional[RAGEngine] = None,
    persist: bool = True,
) -> dict:
    """Pipeline principal: decompose → execute agents → synthesize."""
    from core.database.service import save_conversation, save_orchestrator_log

    disciplines = decompose_problem(text)

    conversation = None
    conversation_id = None
    if persist:
        conversation = save_conversation(input_text=text, mode="multi")
        if conversation:
            conversation_id = conversation.get("id")

    route_result = {
        "input": text,
        "disciplines": disciplines,
        "_conversation_id": conversation_id,
    }

    graph = ContextGraph()

    agent_results = execute_agents(
        route_result,
        use_rag=use_rag,
        rag_engine=rag_engine,
        persist=persist,
        context_graph=graph,
    )

    global_context = graph.build_global_context()
    synthesis = synthesize_results(agent_results, context=global_context)

    results_by_discipline = {
        item.get("discipline", f"item_{index}"): item
        for index, item in enumerate(agent_results)
    }

    orchestrator_log = None
    if persist:
        orchestrator_log = save_orchestrator_log(
            input_text=text,
            disciplines=disciplines,
            final_report=synthesis["final_report"],
            synthesis={
                "technical_summary": synthesis["technical_summary"],
                "general_conclusion": synthesis["general_conclusion"],
            },
            use_rag=use_rag,
            agent_count=len(agent_results),
            conversation_id=conversation_id,
        )

    output = {
        "input": text,
        "disciplines": disciplines,
        "results": results_by_discipline,
        "final_report": synthesis["final_report"],
        "synthesis": {
            "technical_summary": synthesis["technical_summary"],
            "general_conclusion": synthesis["general_conclusion"],
            "global_context": synthesis.get("global_context", ""),
        },
        "context_graph": graph.to_dict(),
    }

    if conversation_id:
        output["conversation_id"] = conversation_id
    if orchestrator_log:
        output["orchestrator_log_id"] = orchestrator_log.get("id")

    try:
        from core.learning.feedback_service import record_orchestrator_summary

        record_orchestrator_summary(
            input_text=text,
            response_text=synthesis["final_report"],
            conversation_id=conversation_id,
        )
    except Exception:
        pass

    try:
        from core.evolution.evolution_engine import emit_evolution_signal

        emit_evolution_signal(
            {
                "source": "orchestrator",
                "module": "orchestrator",
                "input_text": text,
                "task_type": "orchestration_synthesis",
                "discipline": disciplines[0] if disciplines else "GERAL",
                "output_text": synthesis["final_report"],
                "success": len(agent_results) > 0,
                "extra": {"disciplines": disciplines, "agent_count": len(agent_results)},
            }
        )
    except Exception:
        pass

    return output
