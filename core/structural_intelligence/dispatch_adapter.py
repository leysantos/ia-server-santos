"""
Adaptador de dispatch SIE — integra SIE v1 ao agente ESTRUTURAL sem alterar BaseAgentIntelligent.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def try_sie_dispatch(
    agent: Any,
    text: str,
    *,
    context: Optional[str] = None,
    use_rag: Optional[bool] = None,
) -> Optional[dict]:
    """
    Tenta dispatch via SIE v1. Retorna None para fallback ao fluxo padrão do agente.
    """
    try:
        from core.structural_intelligence.structural_engine import StructuralIntelligenceEngine

        rag_enabled = agent.use_rag if use_rag is None else use_rag

        if context is not None:
            rag_context = context
        elif rag_enabled:
            rag_context = agent.retrieve_context(text)
        else:
            rag_context = ""

        engine = StructuralIntelligenceEngine()
        sie_ctx, prompt = engine.process(text, rag_context=rag_context)

        result, model_used = agent.llm_client.generate(prompt, model=sie_ctx.model)
        agent._last_model_used = model_used

        extra = agent.build_extra(sie_ctx.norms, rag_context or None)
        extra["intelligent"] = True
        extra["llm_model"] = model_used
        extra["sie"] = sie_ctx.to_dict()
        extra["response_source"] = "sie_v1"

        if rag_context:
            extra.setdefault("rag", {})
            extra["rag"]["active"] = True
            extra["rag"]["context_length"] = len(rag_context)

        return agent.build_response(input_text=text, result=result, extra=extra)

    except Exception as exc:
        logger.warning("SIE v1 fallback para fluxo padrão ESTRUTURAL: %s", exc)
        return None
