"""
Rollout Manager — aplica mutações com shadow test e safe rollout.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from config import settings
from core.evolution.mutation_engine import MutationProposal

logger = logging.getLogger(__name__)

WIN_RATE_THRESHOLD = 0.05


class RolloutManager:
    """
    Promove mutações apenas se win_rate > baseline + threshold.
    Nunca aplica mutações AGENT de código automaticamente.
    """

    def process(self, proposals: list[MutationProposal]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for proposal in proposals:
            result = self._process_one(proposal)
            results.append(result)
        return results

    def _process_one(self, proposal: MutationProposal) -> dict[str, Any]:
        status = "proposed"
        applied = False
        shadow_passed = None

        if proposal.mutation_type == "AGENT":
            # Nunca auto-aplicar agentes
            return self._record(proposal, status="proposed_manual_review", applied=False)

        if not settings.USE_EVOLUTION_LOOP:
            return self._record(proposal, status="skipped_flag_off", applied=False)

        if settings.USE_SAFE_ROLLOUT:
            shadow_passed = self._shadow_test(proposal)
            if not shadow_passed:
                return self._record(
                    proposal,
                    status="shadow_rejected",
                    applied=False,
                    shadow_passed=False,
                )

        if proposal.mutation_type == "MODEL":
            applied = self._apply_model_mutation(proposal)
            status = "applied" if applied else "apply_failed"
        elif proposal.mutation_type == "PROMPT":
            applied = self._apply_prompt_mutation(proposal)
            status = "applied" if applied else "proposed"
        elif proposal.mutation_type == "RAG":
            applied = self._apply_rag_mutation(proposal)
            status = "applied" if applied else "proposed"
        else:
            status = "unsupported"

        return self._record(
            proposal,
            status=status,
            applied=applied,
            shadow_passed=shadow_passed,
        )

    def _shadow_test(self, proposal: MutationProposal) -> bool:
        """Compara win_rate proposto vs baseline via model_performance_profile."""
        if proposal.mutation_type == "AGENT":
            return False

        payload = proposal.payload or {}
        proposed_wr = float(payload.get("win_rate") or 0.0)
        sample = int(payload.get("sample_count") or 0)
        if sample < 5:
            logger.info("Rollout shadow: amostra insuficiente (%d) mutation=%s", sample, proposal.mutation_key)
            return False

        baseline = self._baseline_win_rate(proposal)
        passed = proposed_wr >= baseline + WIN_RATE_THRESHOLD
        logger.info(
            "Rollout shadow mutation=%s proposed_wr=%.3f baseline=%.3f passed=%s",
            proposal.mutation_key,
            proposed_wr,
            baseline,
            passed,
        )
        return passed

    def _baseline_win_rate(self, proposal: MutationProposal) -> float:
        task_type = (proposal.payload or {}).get("task_type")
        discipline = (proposal.payload or {}).get("discipline") or "GERAL"
        if not task_type:
            return 0.5
        try:
            from core.models.model_performance_service import list_performance_profiles

            rows = list_performance_profiles(task_type=task_type, limit=20)
            current = proposal.current_value
            for row in rows:
                if row.get("discipline") == discipline and row.get("model_name") == current:
                    return float(row.get("win_rate") or 0.5)
        except Exception:
            pass
        return 0.5

    def _apply_model_mutation(self, proposal: MutationProposal) -> bool:
        try:
            payload = proposal.payload or {}
            task_type = payload.get("task_type")
            if not task_type and proposal.context_key:
                parts = proposal.context_key.split(":")
                if len(parts) >= 2:
                    task_type = parts[1]
            if not task_type:
                return False
            from core.models.model_router import get_model_router

            get_model_router().apply_learned_model(task_type, proposal.proposed_value)
            return True
        except Exception as exc:
            logger.warning("Rollout MODEL falhou: %s", exc)
            return False

    def _apply_prompt_mutation(self, proposal: MutationProposal) -> bool:
        # Registra proposta — Learning v2 continua responsável por prompts versionados
        logger.info(
            "Rollout PROMPT proposta discipline=%s %s -> %s",
            proposal.mutation_key,
            proposal.current_value,
            proposal.proposed_value,
        )
        return False

    def _apply_rag_mutation(self, proposal: MutationProposal) -> bool:
        try:
            from core.evolution.rag_evolution import get_rag_evolution_store

            store = get_rag_evolution_store()
            payload = proposal.payload or {}
            if "nbr_or_chunk" in payload:
                store.apply_boost(payload["nbr_or_chunk"], float(payload.get("boost_delta", 0.1)))
                return True
        except Exception as exc:
            logger.warning("Rollout RAG falhou: %s", exc)
        return False

    def _record(
        self,
        proposal: MutationProposal,
        *,
        status: str,
        applied: bool,
        shadow_passed: Optional[bool] = None,
    ) -> dict[str, Any]:
        entry = {
            **proposal.to_dict(),
            "status": status,
            "applied": applied,
            "shadow_passed": shadow_passed,
        }
        try:
            from core.evolution.audit import save_evolution_mutation

            saved = save_evolution_mutation(entry)
            if saved:
                entry["mutation_id"] = saved.get("id")
        except Exception as exc:
            logger.debug("Rollout persist ignorado: %s", exc)
        return entry
