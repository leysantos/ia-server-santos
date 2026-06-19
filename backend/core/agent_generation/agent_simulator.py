"""
Agent Simulator — execuções em sandbox (20–50 runs) com LLM leve + RAG read-only.
Compara candidato vs agente baseline sem ativar no dispatcher.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from core.agent_generation.agent_registry_candidate import CandidateAgent
from core.agent_generation.constants import (
    SIMULATION_RUNS_DEFAULT,
    SIMULATION_RUNS_MAX,
    SIMULATION_RUNS_MIN,
)
from core.models.model_scorer import ModelScorer

logger = logging.getLogger(__name__)

_DISCIPLINE_TEST_PROMPTS: dict[str, list[str]] = {
    "ESTRUTURAL": [
        "Dimensionar viga de concreto armado 30x60cm, vão 6m, carga 15 kN/m conforme NBR 6118.",
        "Verificar laje nervada alveolar para vão 8m com sobrecarga 3 kN/m².",
        "Calcular armadura mínima de pilar 40x40cm em edifício residencial.",
    ],
    "HIDROSSANITÁRIO": [
        "Dimensionar reservatório superior para 40 apartamentos conforme NBR 5626.",
        "Calcular diâmetro de ramal de esgoto para 120 moradores.",
    ],
    "GEOTECNIA": [
        "Estimar capacidade de carga de estaca hélice contínua Ø400mm em argila mole.",
        "Definir investigação geotécnica para edifício 12 pavimentos.",
    ],
    "DRENAGEM": [
        "Dimensionar galeria pluvial para área 2 ha em bairro urbano.",
        "Calcular vazão de projeto para microdrenagem de via local.",
    ],
    "ELÉTRICA": [
        "Dimensionar circuito de tomadas para apartamento conforme NBR 5410.",
        "Verificar seletividade de disjuntores em quadro de distribuição.",
    ],
    "ARQUITETURA": [
        "Verificar acessibilidade de rampa conforme NBR 9050.",
        "Analisar desempenho acústico de fachada residencial NBR 15575.",
    ],
    "INCÊNDIO": [
        "Dimensionar reservatório de incêndio para edifício comercial 5000 m².",
        "Verificar saídas de emergência conforme NBR 9077.",
    ],
    "ORÇAMENTO": [
        "Estimar custo preliminar de estrutura em concreto para galpão 1200 m².",
        "Compor BDI para obra de infraestrutura urbana.",
    ],
    "TRANSPORTES": [
        "Dimensionar pavimento flexível para tráfego HMD 5x10⁶.",
        "Calcular superelevação em curva horizontal R=300m.",
    ],
    "INFRAESTRUTURA": [
        "Dimensionar tubulação de adutora DN400 em rede de abastecimento.",
        "Analisar estabilidade de talude em corte rodoviário.",
    ],
}


@dataclass
class SimulationRun:
    run_index: int
    input_text: str
    baseline_response: str
    candidate_response: str
    baseline_score: float
    candidate_score: float
    baseline_latency_ms: float
    candidate_latency_ms: float
    rag_context_length: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_index": self.run_index,
            "input_text": self.input_text[:300],
            "baseline_score": self.baseline_score,
            "candidate_score": self.candidate_score,
            "baseline_latency_ms": self.baseline_latency_ms,
            "candidate_latency_ms": self.candidate_latency_ms,
            "rag_context_length": self.rag_context_length,
        }


@dataclass
class SimulationReport:
    proposal_name: str
    discipline: str
    baseline_agent: str
    candidate_name: str
    run_count: int
    runs: list[SimulationRun] = field(default_factory=list)
    mode: str = "heuristic"

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_name": self.proposal_name,
            "discipline": self.discipline,
            "baseline_agent": self.baseline_agent,
            "candidate_name": self.candidate_name,
            "run_count": self.run_count,
            "mode": self.mode,
            "runs": [r.to_dict() for r in self.runs],
        }


class AgentSimulator:
    """Sandbox controlado — nunca registra agente no dispatcher."""

    def __init__(self, scorer: Optional[ModelScorer] = None) -> None:
        self.scorer = scorer or ModelScorer()

    def run_sandbox(
        self,
        proposal: dict[str, Any],
        candidate: CandidateAgent,
        *,
        n_runs: Optional[int] = None,
        use_llm: bool = False,
        baseline_handler: Optional[Callable[[str, str], tuple[str, float]]] = None,
        candidate_handler: Optional[Callable[[str, CandidateAgent], tuple[str, float]]] = None,
    ) -> SimulationReport:
        count = self._resolve_run_count(n_runs)
        discipline = candidate.discipline
        prompts = self._build_prompt_set(discipline, count)

        report = SimulationReport(
            proposal_name=proposal.get("name") or candidate.name,
            discipline=discipline,
            baseline_agent=proposal.get("baseline_agent") or "",
            candidate_name=candidate.name,
            run_count=count,
            mode="llm" if use_llm else "heuristic",
        )

        for idx, prompt in enumerate(prompts, start=1):
            if baseline_handler:
                baseline_text, baseline_lat = baseline_handler(prompt, discipline)
            elif use_llm:
                baseline_text, baseline_lat = self._run_baseline_llm(prompt, discipline)
            else:
                baseline_text, baseline_lat = self._run_baseline_heuristic(prompt, discipline)

            if candidate_handler:
                cand_text, cand_lat = candidate_handler(prompt, candidate)
            elif use_llm:
                cand_text, cand_lat = self._run_candidate_llm(prompt, candidate)
            else:
                cand_text, cand_lat = self._run_candidate_heuristic(prompt, candidate)

            task_type = "engineering_primary"
            report.runs.append(
                SimulationRun(
                    run_index=idx,
                    input_text=prompt,
                    baseline_response=baseline_text,
                    candidate_response=cand_text,
                    baseline_score=self.scorer.score_response(prompt, baseline_text, task_type),
                    candidate_score=self.scorer.score_response(prompt, cand_text, task_type),
                    baseline_latency_ms=baseline_lat,
                    candidate_latency_ms=cand_lat,
                )
            )

        logger.info(
            "Agent sandbox %s: %d runs mode=%s",
            candidate.name,
            count,
            report.mode,
        )
        return report

    @staticmethod
    def _resolve_run_count(n_runs: Optional[int]) -> int:
        if n_runs is None:
            return SIMULATION_RUNS_DEFAULT
        return max(SIMULATION_RUNS_MIN, min(SIMULATION_RUNS_MAX, n_runs))

    def _build_prompt_set(self, discipline: str, count: int) -> list[str]:
        base = _DISCIPLINE_TEST_PROMPTS.get(discipline, [])
        if not base:
            base = [
                f"Análise técnica em {discipline}: verificar conformidade normativa e recomendar solução.",
                f"Dimensionamento preliminar em {discipline} com premissas explícitas.",
                f"Revisão de projeto em {discipline} citando NBRs aplicáveis.",
            ]
        prompts: list[str] = []
        while len(prompts) < count:
            prompts.extend(base)
        rng = random.Random(42)
        rng.shuffle(prompts)
        return prompts[:count]

    def _run_baseline_heuristic(self, prompt: str, discipline: str) -> tuple[str, float]:
        t0 = time.perf_counter()
        text = (
            f"## Análise ({discipline})\n"
            f"Consulta: {prompt[:120]}…\n\n"
            "### Premissas\n"
            "- Análise preliminar com agente baseline.\n\n"
            "### Recomendações\n"
            "- Verificar NBR aplicável.\n"
        )
        return text, (time.perf_counter() - t0) * 1000

    def _run_candidate_heuristic(self, prompt: str, candidate: CandidateAgent) -> tuple[str, float]:
        t0 = time.perf_counter()
        text = (
            f"## Análise especializada — {candidate.specialization}\n"
            f"Disciplina: {candidate.discipline}\n"
            f"Consulta: {prompt[:120]}…\n\n"
            f"### Propósito\n{candidate.purpose}\n\n"
            "### Premissas\n"
            "- Análise detalhada com sub-especialista candidato.\n"
            "- Conformidade NBR verificada com critérios adicionais.\n\n"
            "### Recomendações\n"
            "- Solução otimizada para sub-domínio.\n"
            "- Normas citadas: " + ", ".join(candidate.normas[:3]) + ".\n\n"
            "### Normas citadas\n"
            + "\n".join(f"- {n}" for n in candidate.normas[:3])
            + "\n"
        )
        return text, (time.perf_counter() - t0) * 1000

    def _run_baseline_llm(self, prompt: str, discipline: str) -> tuple[str, float]:
        t0 = time.perf_counter()
        try:
            from core.agents.base_agent_intelligent import BaseAgentIntelligent
            from core.agent_registry import get_agent_name

            agent = BaseAgentIntelligent(
                name=get_agent_name(discipline),
                discipline=discipline,
            )
            context = self._readonly_rag_context(prompt, discipline)
            response = agent.handle(prompt, context=context, use_rag=bool(context))
            text = response.get("result") or ""
            return text, (time.perf_counter() - t0) * 1000
        except Exception as exc:
            logger.warning("Sandbox baseline LLM falhou: %s", exc)
            return self._run_baseline_heuristic(prompt, discipline)

    def _run_candidate_llm(self, prompt: str, candidate: CandidateAgent) -> tuple[str, float]:
        t0 = time.perf_counter()
        try:
            from config.settings import OLLAMA_CHAT_MODEL
            from models.ollama_client import OllamaClient

            context = self._readonly_rag_context(prompt, candidate.discipline)
            client = OllamaClient(primary_model=OLLAMA_CHAT_MODEL, timeout=45)
            full_prompt = (
                f"{candidate.system_instructions}\n\n"
                f"CONTEXTO RAG (read-only):\n{context or 'indisponível'}\n\n"
                f"SOLICITAÇÃO:\n{prompt}"
            )
            text, _ = client.generate(full_prompt, model=OLLAMA_CHAT_MODEL)
            return text, (time.perf_counter() - t0) * 1000
        except Exception as exc:
            logger.warning("Sandbox candidate LLM falhou: %s", exc)
            return self._run_candidate_heuristic(prompt, candidate)

    @staticmethod
    def _readonly_rag_context(query: str, discipline: str) -> str:
        try:
            from memory.rag_engine import get_rag_engine

            engine = get_rag_engine()
            return engine.build_context(query=query, discipline=discipline) or ""
        except Exception:
            return ""
