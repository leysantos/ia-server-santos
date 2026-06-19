from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from core.stream_events import format_sse
from pricing.budget.composition_index import get_composition_index
from pricing.budget.budget_engine_v2 import BudgetEngineV2
from pricing.orchestrator.budget_knowledge import fetch_budget_generation_context
from pricing.orchestrator.intent_parser import IntentParser
from pricing.orchestrator.wbs_planner import EngineeringWbsPlanner
from pricing.quantity.quantity_engine import QuantityEngine


class BudgetOrchestrator:
    """
    Pipeline completo de orçamento automático:
    texto → RAG modelos → LLM WBS (engenheiro) → quantitativos → preços → planilha PPD
    """

    def __init__(
        self,
        intent_parser: IntentParser | None = None,
        quantity_engine: QuantityEngine | None = None,
        budget_engine: BudgetEngineV2 | None = None,
        llm_client: Any | None = None,
    ) -> None:
        self.intent_parser = intent_parser or IntentParser(llm_client=llm_client)
        self.wbs_planner = EngineeringWbsPlanner(llm_client=llm_client)
        self.quantity_engine = quantity_engine or QuantityEngine()
        if budget_engine is not None:
            self.budget_engine = budget_engine
        else:
            from pricing.budget.budget_builder import BudgetBuilder
            from pricing.core.base_service_resolver import BaseServiceResolver

            resolver = BaseServiceResolver(llm_client=llm_client)
            self.budget_engine = BudgetEngineV2(
                builder=BudgetBuilder(resolver=resolver),
            )
        self._llm = llm_client

    def run(
        self,
        text: str,
        source_priority: list[str] | None = None,
        use_llm: bool = True,
        obra_type: str | None = None,
    ) -> dict[str, Any]:
        result = None
        for event_type, data in self.run_events(
            text,
            source_priority=source_priority,
            use_llm=use_llm,
            obra_type=obra_type,
        ):
            if event_type == "done":
                result = data
        if result is None:
            raise RuntimeError("Pipeline não produziu resultado")
        return result

    def run_events(
        self,
        text: str,
        source_priority: list[str] | None = None,
        use_llm: bool = True,
        obra_type: str | None = None,
        existing_session_id: str | None = None,
    ) -> Iterator[tuple[str, dict[str, Any]]]:
        intent: dict[str, Any] | None = None

        knowledge_context, knowledge_refs = fetch_budget_generation_context(text)
        if knowledge_refs:
            yield (
                "step",
                {
                    "step": "knowledge_rag",
                    "models": knowledge_refs,
                    "message": f"{len(knowledge_refs)} modelo(s) de orçamento consultado(s)",
                },
            )
        elif knowledge_context:
            yield (
                "step",
                {
                    "step": "knowledge_rag",
                    "models": [],
                    "message": "Modelos de orçamento carregados do catálogo",
                },
            )

        wbs_step = "wbs_planner" if use_llm else "intent_parser"
        planner_events = (
            self.wbs_planner.plan_events(text, knowledge_context=knowledge_context)
            if use_llm
            else self.intent_parser.parse_events(text, use_llm=False, knowledge_context=knowledge_context)
        )

        for event_type, data in planner_events:
            if event_type in ("status", "token"):
                yield event_type, {**data, "step": wbs_step}
            elif event_type == "intent":
                intent = data
                etapas = intent.get("etapas") or []
                yield (
                    "step",
                    {
                        "step": wbs_step,
                        "intent": intent,
                        "parser": intent.get("parser"),
                        "structure_source": intent.get("structure_source"),
                        "etapas_count": len(etapas),
                        "services_count": sum(len(e.get("services") or []) for e in etapas),
                    },
                )

        if intent is None:
            intent = self.intent_parser._parse_fallback(text)
            yield ("step", {"step": wbs_step, "intent": intent, "parser": "regex_fallback"})

        if obra_type:
            intent["obra_type"] = obra_type

        intent["_input_text"] = text

        yield ("status", {"message": "Calculando quantitativos…", "phase": "quantity_engine", "step": "quantity_engine"})
        enriched = self.quantity_engine.enrich(intent)
        for mem in enriched.get("quantity_memory") or []:
            yield ("step", {"step": "quantity_engine", "memory": mem})
        yield ("step", {"step": "quantity_engine", "computed": enriched.get("computed_quantities")})

        yield ("status", {"message": "Resolvendo preços: busca na base + escolha pela IA (até 30 candidatos/linha)…", "phase": "pricing_engine", "step": "pricing_engine"})
        from pricing.core.base_service_resolver import BaseServiceResolver

        resolver = BaseServiceResolver(llm_client=self._llm)
        loaded_bases = resolver.loaded_sources()
        effective_priority = [s for s in (source_priority or []) if s in loaded_bases] or loaded_bases
        if hasattr(self.budget_engine, "builder"):
            self.budget_engine.builder.use_llm_resolve = use_llm
            if self._llm and hasattr(self.budget_engine.builder, "resolver"):
                self.budget_engine.builder.resolver.llm = self._llm

        rebuild_info = resolver.ensure_faiss_index()
        faiss_status = get_composition_index().status()
        yield (
            "step",
            {
                "step": "pricing_engine",
                "faiss_index": faiss_status,
                "faiss_rebuild": rebuild_info,
                "loaded_bases": loaded_bases,
            },
        )

        pricing_resolves: list[dict[str, Any]] = []

        def on_pricing_event(ev: dict[str, Any]) -> None:
            pricing_resolves.append(ev)

        session = self.budget_engine.generate_session(
            enriched,
            source_priority=effective_priority or None,
            title=enriched.get("title"),
            session_id=existing_session_id,
            on_pricing_event=on_pricing_event,
        )

        for ev in pricing_resolves:
            yield ("pricing_resolve", {**ev, "step": "pricing_engine"})

        priced = sum(1 for r in session.to_dict()["rows"] if r.get("unit_price", 0) > 0)
        unresolved = sum(
            1 for ev in pricing_resolves if not ev.get("resolved")
        )
        yield (
            "step",
            {
                "step": "pricing_engine",
                "items_priced": priced,
                "total_rows": len(session.to_dict()["rows"]),
                "unresolved": unresolved,
                "resolve_events": len(pricing_resolves),
            },
        )

        yield ("status", {"message": "Montando planilha PPD…", "phase": "budget_engine_v2", "step": "budget_engine_v2"})
        payload = session.to_dict()
        pipeline_steps = (
            ["knowledge_rag", "wbs_planner", "quantity_engine", "pricing_engine", "budget_engine_v2"]
            if use_llm
            else ["knowledge_rag", "intent_parser", "quantity_engine", "pricing_engine", "budget_engine_v2"]
        )
        payload["pipeline"] = {
            "steps": pipeline_steps,
            "intent": intent,
            "quantity_memory": enriched.get("quantity_memory", []),
            "parser": intent.get("parser", "unknown"),
            "structure_source": intent.get("structure_source"),
            "llm_model": intent.get("llm_model"),
            "llm_used": use_llm and intent.get("parser") in ("llm_wbs", "llm"),
            "budget_smart_routing": True,
            "knowledge_models": knowledge_refs,
            "faiss_index": faiss_status,
            "pricing_resolves": pricing_resolves,
        }
        payload["input_text"] = text

        yield ("done", payload)

    def run_events_sse(
        self,
        text: str,
        source_priority: list[str] | None = None,
        use_llm: bool = True,
        obra_type: str | None = None,
        existing_session_id: str | None = None,
    ) -> Iterator[str]:
        for event_type, data in self.run_events(
            text,
            source_priority=source_priority,
            use_llm=use_llm,
            obra_type=obra_type,
            existing_session_id=existing_session_id,
        ):
            yield format_sse(event_type, data)
