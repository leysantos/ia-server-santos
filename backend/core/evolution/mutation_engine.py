"""
Mutation Engine — gera propostas de evolução (MODEL, PROMPT, AGENT, RAG).
Nunca auto-modifica código — apenas registra evolution_mutations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from core.evolution.performance_analyzer import PerformanceInsight
from core.evolution.signal_collector import EvolutionSignal


@dataclass
class MutationProposal:
    mutation_type: str  # MODEL | PROMPT | AGENT | RAG
    mutation_key: str
    current_value: Optional[str]
    proposed_value: str
    context_key: str
    rationale: str
    risk_score: float = 0.3
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mutation_type": self.mutation_type,
            "mutation_key": self.mutation_key,
            "current_value": self.current_value,
            "proposed_value": self.proposed_value,
            "context_key": self.context_key,
            "rationale": self.rationale,
            "risk_score": self.risk_score,
            "payload": self.payload,
        }


class MutationEngine:
    """Gera mutações candidatas a partir de insights de performance."""

    MODEL_ALTERNATIVES = {
        "qwen3:14b": "gemma3:12b",
        "qwen3:8b": "mistral:7b",
        "mistral:7b": "phi3:mini",
    }

    def propose(
        self,
        signal: EvolutionSignal,
        insight: PerformanceInsight,
    ) -> list[MutationProposal]:
        proposals: list[MutationProposal] = []

        for opp in insight.opportunities:
            if opp.startswith("model_switch:"):
                parts = opp.split(":", 1)[1]
                current, proposed = parts.split("->", 1)
                proposals.append(
                    MutationProposal(
                        mutation_type="MODEL",
                        mutation_key=f"model:{signal.task_type or signal.source}:{signal.discipline or 'GERAL'}",
                        current_value=current,
                        proposed_value=proposed,
                        context_key=insight.context_key,
                        rationale=f"Melhor win_rate histórico para {insight.context_key}",
                        risk_score=0.25,
                        payload={"task_type": signal.task_type, "discipline": signal.discipline},
                    )
                )
            elif opp.startswith("prompt_upgrade:"):
                parts = opp.split(":", 1)[1]
                current, proposed = parts.split("->", 1)
                proposals.append(
                    MutationProposal(
                        mutation_type="PROMPT",
                        mutation_key=f"prompt:{signal.discipline or 'GERAL'}",
                        current_value=current,
                        proposed_value=proposed,
                        context_key=insight.context_key,
                        rationale="Prompt alternativo com melhor performance histórica",
                        risk_score=0.35,
                    )
                )
            elif opp == "rag_empty_index_or_query":
                proposals.append(
                    MutationProposal(
                        mutation_type="RAG",
                        mutation_key="rag:index_population",
                        current_value="empty",
                        proposed_value="index_nbrs_recommended",
                        context_key=insight.context_key,
                        rationale="RAG retornou contexto vazio — indexar NBRs",
                        risk_score=0.1,
                    )
                )
            elif opp == "quality_degradation_review":
                alt = self.MODEL_ALTERNATIVES.get(signal.model_used or "", "")
                if alt and signal.model_used:
                    proposals.append(
                        MutationProposal(
                            mutation_type="MODEL",
                            mutation_key=f"model:degradation:{signal.discipline or 'GERAL'}",
                            current_value=signal.model_used,
                            proposed_value=alt,
                            context_key=insight.context_key,
                            rationale="Degradação detectada — testar modelo alternativo",
                            risk_score=0.4,
                            payload={"trigger": "degradation"},
                        )
                    )

        if insight.best_model and signal.model_used and insight.best_model != signal.model_used:
            key = f"model:auto:{signal.task_type or signal.source}"
            if not any(p.mutation_key == key for p in proposals):
                proposals.append(
                    MutationProposal(
                        mutation_type="MODEL",
                        mutation_key=key,
                        current_value=signal.model_used,
                        proposed_value=insight.best_model,
                        context_key=insight.context_key,
                        rationale=f"best_performer win_rate={insight.win_rate:.2f}",
                        risk_score=0.2,
                        payload={"win_rate": insight.win_rate, "sample_count": insight.sample_count, "task_type": signal.task_type, "discipline": signal.discipline},
                    )
                )

        # RAG: boost normas citadas com sucesso
        for chunk in signal.rag_chunks_used:
            if chunk.upper().startswith("NBR") or "6118" in chunk:
                proposals.append(
                    MutationProposal(
                        mutation_type="RAG",
                        mutation_key=f"rag:boost:{chunk}",
                        current_value="1.0",
                        proposed_value="1.15",
                        context_key=insight.context_key,
                        rationale=f"Chunk/norma {chunk} usada em execução bem-sucedida",
                        risk_score=0.15,
                        payload={"nbr_or_chunk": chunk, "boost_delta": 0.15},
                    )
                )

        # AGENT: apenas proposta auditável — nunca auto-modifica código
        if signal.agent_name and insight.degradation_detected:
            proposals.append(
                MutationProposal(
                    mutation_type="AGENT",
                    mutation_key=f"agent:review:{signal.agent_name}",
                    current_value=signal.agent_version or "current",
                    proposed_value="review_pipeline_config",
                    context_key=insight.context_key,
                    rationale="Degradação detectada — revisão manual de agente recomendada",
                    risk_score=0.9,
                    payload={"agent_name": signal.agent_name, "auto_apply": False},
                )
            )

        return proposals
