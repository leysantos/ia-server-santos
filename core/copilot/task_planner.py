"""
Task Planner — converte intenção em plano estruturado de execução multi-etapa.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from core.agent_registry import get_agent_name
from core.copilot.intent_analyzer import IntentResult, CopilotIntent

# Keywords adicionais por disciplina (planner próprio — não usa Router v2)
DISCIPLINE_KEYWORDS: dict[str, list[str]] = {
    "ARQUITETURA": ["arquitet", "layout", "fachada", "plant", "habitabilidade"],
    "ESTRUTURAL": ["estrutur", "viga", "pilar", "laje", "concreto", "fundação"],
    "HIDROSSANITÁRIO": ["hidrául", "hidraul", "esgoto", "água", "sanitário"],
    "DRENAGEM": ["drenagem", "pluvial", "bocas de lobo"],
    "ELÉTRICA": ["elétric", "eletric", "energia", "iluminação"],
    "TELECOM": ["telecom", "dados", "fibra"],
    "INCÊNDIO": ["incêndio", "incendio", "sprinkler", "pci"],
    "GEOTECNIA": ["geotéc", "geotec", "solo", "spt"],
    "ORÇAMENTO": ["orçament", "orcament", "custo", "sinapi"],
    "MEIO_AMBIENTE": ["ambient", "licenciamento", "conama"],
}

# Ordem de execução preferencial em projetos multidisciplinares
DISCIPLINE_ORDER: list[str] = [
    "ARQUITETURA",
    "GEOTECNIA",
    "ESTRUTURAL",
    "HIDROSSANITÁRIO",
    "DRENAGEM",
    "ELÉTRICA",
    "TELECOM",
    "INCÊNDIO",
    "SANEAMENTO",
    "ORÇAMENTO",
    "MEIO_AMBIENTE",
    "GERAL",
]

INTENT_PLAN_TEMPLATES: dict[CopilotIntent, list[str]] = {
    "structural": ["ESTRUTURAL"],
    "hydraulic": ["HIDROSSANITÁRIO", "DRENAGEM"],
    "electrical": ["ELÉTRICA"],
    "cost": ["ORÇAMENTO"],
    "general": ["GERAL"],
    "multi_discipline": [],
}


@dataclass
class PlanStep:
    step_id: str
    order: int
    discipline: str
    agent: str
    description: str
    depends_on: list[str] = field(default_factory=list)
    use_context: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "order": self.order,
            "discipline": self.discipline,
            "agent": self.agent,
            "description": self.description,
            "depends_on": self.depends_on,
            "use_context": self.use_context,
        }


@dataclass
class ExecutionPlan:
    intent: str
    steps: list[PlanStep]
    disciplines: list[str]

    def to_dict(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self.steps]


def _disciplines_from_text(text: str) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for discipline, keywords in DISCIPLINE_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            found.append(discipline)
    return found


def _resolve_disciplines(text: str, intent_result: IntentResult) -> list[str]:
    if intent_result.intent == "multi_discipline":
        from_text = _disciplines_from_text(text)
        combined = list(dict.fromkeys(intent_result.disciplines_hint + from_text))
        return _sort_disciplines(combined)

    template = INTENT_PLAN_TEMPLATES.get(intent_result.intent, ["GERAL"])
    return template


def _sort_disciplines(disciplines: list[str]) -> list[str]:
    order_map = {d: i for i, d in enumerate(DISCIPLINE_ORDER)}

    def sort_key(d: str) -> tuple[int, str]:
        return (order_map.get(d, 999), d)

    return sorted(disciplines, key=sort_key)


def _step_description(discipline: str, text: str) -> str:
    descriptions = {
        "ARQUITETURA": "Análise arquitetônica e requisitos de projeto",
        "ESTRUTURAL": "Dimensionamento e verificação estrutural",
        "HIDROSSANITÁRIO": "Dimensionamento hidrossanitário",
        "DRENAGEM": "Análise de drenagem pluvial",
        "ELÉTRICA": "Projeto e dimensionamento elétrico",
        "TELECOM": "Infraestrutura de telecomunicações",
        "INCÊNDIO": "Segurança contra incêndio e PCI",
        "GEOTECNIA": "Investigação e caracterização geotécnica",
        "ORÇAMENTO": "Estimativa de custos e orçamentação",
        "MEIO_AMBIENTE": "Aspectos ambientais e licenciamento",
        "GERAL": "Análise técnica geral de engenharia",
    }
    base = descriptions.get(discipline, f"Análise técnica — {discipline}")
    snippet = text[:80] + ("..." if len(text) > 80 else "")
    return f"{base}: {snippet}"


def build_plan(text: str, intent_result: IntentResult) -> ExecutionPlan:
    """Gera plano de execução com etapas ordenadas e dependências."""
    disciplines = _resolve_disciplines(text, intent_result)
    steps: list[PlanStep] = []
    prior_disciplines: list[str] = []

    for idx, discipline in enumerate(disciplines, start=1):
        depends_on = prior_disciplines.copy() if idx > 1 else []
        step = PlanStep(
            step_id=f"step_{idx}",
            order=idx,
            discipline=discipline,
            agent=get_agent_name(discipline),
            description=_step_description(discipline, text),
            depends_on=depends_on,
            use_context=idx > 1,
        )
        steps.append(step)
        prior_disciplines.append(discipline)

    return ExecutionPlan(
        intent=intent_result.intent,
        steps=steps,
        disciplines=disciplines,
    )
