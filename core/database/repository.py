"""
Repository — acesso direto ao PostgreSQL (SQLAlchemy ORM).
"""

import uuid
from typing import Any, Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from core.database.models import (
    AedRun,
    AgentFeedback,
    AgentRun,
    Conversation,
    CopilotEvaluationRecord,
    ModelEvaluation,
    ModelPerformanceProfile,
    OrchestratorLog,
    SystemFailure,
    SystemPatch,
)


class DatabaseRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- conversations ---

    def create_conversation(
        self,
        input_text: str,
        mode: str = "single",
    ) -> Conversation:
        conversation = Conversation(input_text=input_text, mode=mode)
        self.db.add(conversation)
        self.db.flush()
        return conversation

    def get_conversation(self, conversation_id: uuid.UUID) -> Optional[Conversation]:
        return self.db.get(Conversation, conversation_id)

    # --- orchestrator_logs ---

    def create_orchestrator_log(
        self,
        input_text: str,
        disciplines: list[str],
        final_report: str,
        synthesis: dict,
        use_rag: bool,
        agent_count: int,
        conversation_id: Optional[uuid.UUID] = None,
    ) -> OrchestratorLog:
        log = OrchestratorLog(
            conversation_id=conversation_id,
            input_text=input_text,
            disciplines=disciplines,
            final_report=final_report,
            synthesis=synthesis,
            use_rag=use_rag,
            agent_count=agent_count,
        )
        self.db.add(log)
        self.db.flush()
        return log

    def get_orchestrator_log(self, log_id: uuid.UUID) -> Optional[OrchestratorLog]:
        return self.db.get(OrchestratorLog, log_id)

    # --- agent_runs ---

    def create_agent_run(
        self,
        input_text: str,
        discipline: Optional[str],
        agent_name: Optional[str],
        result_text: Optional[str],
        had_context: bool,
        extra: Optional[dict],
        response_payload: Optional[dict],
        conversation_id: Optional[uuid.UUID] = None,
        orchestrator_log_id: Optional[uuid.UUID] = None,
    ) -> AgentRun:
        run = AgentRun(
            conversation_id=conversation_id,
            orchestrator_log_id=orchestrator_log_id,
            agent_name=agent_name,
            discipline=discipline,
            input_text=input_text,
            result_text=result_text,
            had_context=had_context,
            extra=extra,
            response_payload=response_payload,
        )
        self.db.add(run)
        self.db.flush()
        return run

    def list_agent_runs(
        self,
        conversation_id: Optional[uuid.UUID] = None,
        limit: int = 50,
    ) -> list[AgentRun]:
        stmt = select(AgentRun).order_by(desc(AgentRun.created_at)).limit(limit)
        if conversation_id:
            stmt = stmt.where(AgentRun.conversation_id == conversation_id)
        return list(self.db.scalars(stmt).all())

    # --- agent_feedback (Learning Loop v1) ---

    def create_agent_feedback(
        self,
        agent_name: str,
        input_text: str,
        response_text: Optional[str] = None,
        discipline: Optional[str] = None,
        conversation_id: Optional[uuid.UUID] = None,
        rating: Optional[int] = None,
        feedback_text: Optional[str] = None,
        corrected_answer: Optional[str] = None,
    ) -> AgentFeedback:
        row = AgentFeedback(
            conversation_id=conversation_id,
            agent_name=agent_name,
            discipline=discipline,
            input_text=input_text,
            response_text=response_text,
            rating=rating,
            feedback_text=feedback_text,
            corrected_answer=corrected_answer,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def get_latest_feedback(
        self,
        conversation_id: uuid.UUID,
        agent_name: str,
    ) -> Optional[AgentFeedback]:
        stmt = (
            select(AgentFeedback)
            .where(
                AgentFeedback.conversation_id == conversation_id,
                AgentFeedback.agent_name == agent_name,
            )
            .order_by(desc(AgentFeedback.created_at))
            .limit(1)
        )
        return self.db.scalars(stmt).first()

    def list_feedback_by_agent(
        self,
        agent_name: str,
        limit: int = 50,
    ) -> list[AgentFeedback]:
        stmt = (
            select(AgentFeedback)
            .where(AgentFeedback.agent_name == agent_name)
            .order_by(desc(AgentFeedback.created_at))
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def list_low_quality_responses(
        self,
        threshold: int = 3,
        limit: int = 50,
    ) -> list[AgentFeedback]:
        stmt = (
            select(AgentFeedback)
            .where(
                AgentFeedback.rating.is_not(None),
                AgentFeedback.rating <= threshold,
            )
            .order_by(desc(AgentFeedback.created_at))
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def list_all_feedback(
        self,
        limit: int = 500,
        discipline: Optional[str] = None,
        agent_name: Optional[str] = None,
    ) -> list[AgentFeedback]:
        stmt = select(AgentFeedback).order_by(desc(AgentFeedback.created_at)).limit(limit)
        if discipline:
            stmt = stmt.where(AgentFeedback.discipline == discipline)
        if agent_name:
            stmt = stmt.where(AgentFeedback.agent_name == agent_name)
        return list(self.db.scalars(stmt).all())

    def list_feedback_by_discipline(
        self,
        discipline: str,
        limit: int = 200,
    ) -> list[AgentFeedback]:
        stmt = (
            select(AgentFeedback)
            .where(AgentFeedback.discipline == discipline)
            .order_by(desc(AgentFeedback.created_at))
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    @staticmethod
    def serialize_agent_feedback(row: AgentFeedback) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "conversation_id": str(row.conversation_id) if row.conversation_id else None,
            "agent_name": row.agent_name,
            "discipline": row.discipline,
            "input_text": row.input_text,
            "response_text": row.response_text,
            "rating": row.rating,
            "feedback_text": row.feedback_text,
            "corrected_answer": row.corrected_answer,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    # --- copilot_evaluations (Evaluation Loop v2) ---

    def create_copilot_evaluation(
        self,
        input_text: str,
        intent_accuracy: float,
        plan_quality: float,
        execution_completeness: float,
        response_quality: float,
        final_score: float,
        intent: Optional[str] = None,
        conversation_id: Optional[uuid.UUID] = None,
        issues: Optional[list] = None,
        scores_detail: Optional[list] = None,
    ) -> CopilotEvaluationRecord:
        row = CopilotEvaluationRecord(
            conversation_id=conversation_id,
            input_text=input_text,
            intent=intent,
            intent_accuracy=intent_accuracy,
            plan_quality=plan_quality,
            execution_completeness=execution_completeness,
            response_quality=response_quality,
            final_score=final_score,
            issues=issues,
            scores_detail=scores_detail,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def list_copilot_evaluations(
        self,
        limit: int = 50,
        min_final_score: Optional[float] = None,
    ) -> list[CopilotEvaluationRecord]:
        stmt = (
            select(CopilotEvaluationRecord)
            .order_by(desc(CopilotEvaluationRecord.created_at))
            .limit(limit)
        )
        if min_final_score is not None:
            stmt = stmt.where(CopilotEvaluationRecord.final_score >= min_final_score)
        return list(self.db.scalars(stmt).all())

    @staticmethod
    def serialize_copilot_evaluation(row: CopilotEvaluationRecord) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "conversation_id": str(row.conversation_id) if row.conversation_id else None,
            "input_text": row.input_text,
            "intent": row.intent,
            "intent_accuracy": row.intent_accuracy,
            "plan_quality": row.plan_quality,
            "execution_completeness": row.execution_completeness,
            "response_quality": row.response_quality,
            "final_score": row.final_score,
            "issues": row.issues,
            "scores_detail": row.scores_detail,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    # --- system_failures / system_patches (Self-Improving Loop v1) ---

    def create_system_failure(
        self,
        input_text: str,
        failure_type: str,
        route_decision: Optional[dict] = None,
        agent_used: Optional[str] = None,
        evaluation_scores: Optional[dict] = None,
        suggested_fix: Optional[str] = None,
        conversation_id: Optional[uuid.UUID] = None,
    ) -> SystemFailure:
        row = SystemFailure(
            conversation_id=conversation_id,
            input_text=input_text,
            failure_type=failure_type,
            route_decision=route_decision,
            agent_used=agent_used,
            evaluation_scores=evaluation_scores,
            suggested_fix=suggested_fix,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def list_system_failures(
        self,
        limit: int = 100,
        failure_type: Optional[str] = None,
    ) -> list[SystemFailure]:
        stmt = (
            select(SystemFailure)
            .order_by(desc(SystemFailure.created_at))
            .limit(limit)
        )
        if failure_type:
            stmt = stmt.where(SystemFailure.failure_type == failure_type)
        return list(self.db.scalars(stmt).all())

    @staticmethod
    def serialize_system_failure(row: SystemFailure) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "conversation_id": str(row.conversation_id) if row.conversation_id else None,
            "input_text": row.input_text,
            "route_decision": row.route_decision,
            "agent_used": row.agent_used,
            "evaluation_scores": row.evaluation_scores,
            "failure_type": row.failure_type,
            "suggested_fix": row.suggested_fix,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    def create_system_patch(
        self,
        patch_key: str,
        patch_version: int,
        patch_type: str,
        content: dict,
        status: str = "proposed",
        risk_score: float = 0.0,
        impact_score: float = 0.0,
        source_finding: Optional[str] = None,
    ) -> SystemPatch:
        row = SystemPatch(
            patch_key=patch_key,
            patch_version=patch_version,
            patch_type=patch_type,
            status=status,
            content=content,
            risk_score=risk_score,
            impact_score=impact_score,
            source_finding=source_finding,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def list_system_patches(
        self,
        limit: int = 50,
        status: Optional[str] = None,
    ) -> list[SystemPatch]:
        stmt = (
            select(SystemPatch)
            .order_by(desc(SystemPatch.created_at))
            .limit(limit)
        )
        if status:
            stmt = stmt.where(SystemPatch.status == status)
        return list(self.db.scalars(stmt).all())

    @staticmethod
    def serialize_system_patch(row: SystemPatch) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "patch_key": row.patch_key,
            "patch_version": row.patch_version,
            "patch_type": row.patch_type,
            "status": row.status,
            "content": row.content,
            "risk_score": row.risk_score,
            "impact_score": row.impact_score,
            "source_finding": row.source_finding,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    # --- aed_runs (AED v1) ---

    def create_aed_run(
        self,
        input_text: str,
        understanding: Optional[dict] = None,
        designs: Optional[list] = None,
        simulations: Optional[list] = None,
        comparison: Optional[dict] = None,
        selection: Optional[dict] = None,
        report: Optional[dict] = None,
        conversation_id: Optional[uuid.UUID] = None,
    ) -> AedRun:
        row = AedRun(
            conversation_id=conversation_id,
            input_text=input_text,
            understanding=understanding,
            designs=designs,
            simulations=simulations,
            comparison=comparison,
            selection=selection,
            report=report,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def list_aed_runs(self, limit: int = 50) -> list[AedRun]:
        stmt = (
            select(AedRun)
            .order_by(desc(AedRun.created_at))
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    @staticmethod
    def serialize_aed_run(row: AedRun) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "conversation_id": str(row.conversation_id) if row.conversation_id else None,
            "input_text": row.input_text,
            "understanding": row.understanding,
            "designs": row.designs,
            "simulations": row.simulations,
            "comparison": row.comparison,
            "selection": row.selection,
            "report": row.report,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    # --- model_evaluations (Model Evaluation Loop v1) ---

    def create_model_evaluation(
        self,
        *,
        input_text: str,
        task_type: str,
        discipline: str,
        primary_model: str,
        fallback_model: Optional[str],
        winner_model: str,
        primary_score: float,
        fallback_score: Optional[float],
        primary_latency_ms: float,
        fallback_latency_ms: Optional[float],
        decision_reason: Optional[str],
        primary_response: Optional[str] = None,
        fallback_response: Optional[str] = None,
    ) -> ModelEvaluation:
        row = ModelEvaluation(
            input_text=input_text,
            task_type=task_type,
            discipline=discipline,
            primary_model=primary_model,
            fallback_model=fallback_model,
            winner_model=winner_model,
            primary_score=primary_score,
            fallback_score=fallback_score,
            primary_latency_ms=primary_latency_ms,
            fallback_latency_ms=fallback_latency_ms,
            decision_reason=decision_reason,
            primary_response=primary_response,
            fallback_response=fallback_response,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def count_model_evaluations(self, task_type: str, discipline: str) -> int:
        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(ModelEvaluation)
            .where(
                ModelEvaluation.task_type == task_type,
                ModelEvaluation.discipline == discipline,
            )
        )
        return int(self.db.scalar(stmt) or 0)

    def list_model_evaluations(
        self,
        task_type: Optional[str] = None,
        discipline: Optional[str] = None,
        limit: int = 100,
    ) -> list[ModelEvaluation]:
        stmt = select(ModelEvaluation).order_by(desc(ModelEvaluation.created_at)).limit(limit)
        if task_type:
            stmt = stmt.where(ModelEvaluation.task_type == task_type)
        if discipline:
            stmt = stmt.where(ModelEvaluation.discipline == discipline)
        return list(self.db.scalars(stmt).all())

    def rebuild_performance_profiles(self, task_type: str, discipline: str) -> None:
        """Recalcula perfis de performance a partir de model_evaluations."""
        from sqlalchemy import delete

        evals = self.list_model_evaluations(task_type=task_type, discipline=discipline, limit=5000)
        stats: dict[str, dict[str, float]] = {}

        for ev in evals:
            for model, score, latency, is_winner in (
                (ev.primary_model, ev.primary_score, ev.primary_latency_ms, ev.winner_model == ev.primary_model),
                (ev.fallback_model, ev.fallback_score, ev.fallback_latency_ms, ev.winner_model == ev.fallback_model),
            ):
                if not model or score is None:
                    continue
                bucket = stats.setdefault(
                    model,
                    {"wins": 0.0, "total": 0.0, "score_sum": 0.0, "latency_sum": 0.0},
                )
                bucket["total"] += 1
                bucket["score_sum"] += score
                bucket["latency_sum"] += latency or 0.0
                if is_winner:
                    bucket["wins"] += 1

        self.db.execute(
            delete(ModelPerformanceProfile).where(
                ModelPerformanceProfile.task_type == task_type,
                ModelPerformanceProfile.discipline == discipline,
            )
        )

        for model_name, bucket in stats.items():
            total = int(bucket["total"])
            wins = int(bucket["wins"])
            profile = ModelPerformanceProfile(
                task_type=task_type,
                discipline=discipline,
                model_name=model_name,
                win_count=wins,
                total_evaluations=total,
                win_rate=round(wins / total, 4) if total else 0.0,
                avg_score=round(bucket["score_sum"] / total, 4) if total else 0.0,
                avg_latency_ms=round(bucket["latency_sum"] / total, 2) if total else 0.0,
            )
            self.db.add(profile)
        self.db.flush()

    def get_best_performance_profile(
        self,
        task_type: str,
        discipline: str,
    ) -> Optional[ModelPerformanceProfile]:
        stmt = (
            select(ModelPerformanceProfile)
            .where(
                ModelPerformanceProfile.task_type == task_type,
                ModelPerformanceProfile.discipline == discipline,
            )
            .order_by(
                desc(ModelPerformanceProfile.win_rate),
                desc(ModelPerformanceProfile.avg_score),
                desc(ModelPerformanceProfile.total_evaluations),
            )
            .limit(1)
        )
        return self.db.scalars(stmt).first()

    def list_model_performance_profiles(
        self,
        task_type: Optional[str] = None,
        limit: int = 50,
    ) -> list[ModelPerformanceProfile]:
        stmt = (
            select(ModelPerformanceProfile)
            .order_by(
                desc(ModelPerformanceProfile.win_rate),
                desc(ModelPerformanceProfile.total_evaluations),
            )
            .limit(limit)
        )
        if task_type:
            stmt = stmt.where(ModelPerformanceProfile.task_type == task_type)
        return list(self.db.scalars(stmt).all())

    @staticmethod
    def serialize_model_evaluation(row: ModelEvaluation) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "input_text": row.input_text[:200],
            "task_type": row.task_type,
            "discipline": row.discipline,
            "primary_model": row.primary_model,
            "fallback_model": row.fallback_model,
            "winner_model": row.winner_model,
            "primary_score": row.primary_score,
            "fallback_score": row.fallback_score,
            "primary_latency_ms": row.primary_latency_ms,
            "fallback_latency_ms": row.fallback_latency_ms,
            "decision_reason": row.decision_reason,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    @staticmethod
    def serialize_model_performance_profile(row: ModelPerformanceProfile) -> dict[str, Any]:
        return {
            "task_type": row.task_type,
            "discipline": row.discipline,
            "model_name": row.model_name,
            "win_count": row.win_count,
            "total_evaluations": row.total_evaluations,
            "win_rate": row.win_rate,
            "avg_score": row.avg_score,
            "avg_latency_ms": row.avg_latency_ms,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    # --- history ---

    def get_history(
        self,
        limit: int = 50,
        conversation_id: Optional[uuid.UUID] = None,
    ) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .order_by(desc(Conversation.created_at))
            .limit(limit)
        )
        if conversation_id:
            stmt = stmt.where(Conversation.id == conversation_id)
        return list(self.db.scalars(stmt).all())

    @staticmethod
    def serialize_conversation(conversation: Conversation) -> dict[str, Any]:
        return {
            "id": str(conversation.id),
            "input_text": conversation.input_text,
            "mode": conversation.mode,
            "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
            "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
            "orchestrator_logs": [
                DatabaseRepository.serialize_orchestrator_log(log)
                for log in conversation.orchestrator_logs
            ],
            "agent_runs": [
                DatabaseRepository.serialize_agent_run(run)
                for run in conversation.agent_runs
            ],
        }

    @staticmethod
    def serialize_orchestrator_log(log: OrchestratorLog) -> dict[str, Any]:
        return {
            "id": str(log.id),
            "conversation_id": str(log.conversation_id) if log.conversation_id else None,
            "input_text": log.input_text,
            "disciplines": log.disciplines,
            "final_report": log.final_report,
            "synthesis": log.synthesis,
            "use_rag": log.use_rag,
            "agent_count": log.agent_count,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }

    @staticmethod
    def serialize_agent_run(run: AgentRun) -> dict[str, Any]:
        return {
            "id": str(run.id),
            "conversation_id": str(run.conversation_id) if run.conversation_id else None,
            "orchestrator_log_id": str(run.orchestrator_log_id) if run.orchestrator_log_id else None,
            "agent_name": run.agent_name,
            "discipline": run.discipline,
            "input_text": run.input_text,
            "result_text": run.result_text,
            "had_context": run.had_context,
            "extra": run.extra,
            "response_payload": run.response_payload,
            "created_at": run.created_at.isoformat() if run.created_at else None,
        }
