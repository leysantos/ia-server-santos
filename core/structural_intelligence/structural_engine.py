"""
Structural Intelligence Engine — orquestrador principal do SIE v1.
"""

from __future__ import annotations

import logging
from typing import Optional

from core.structural_intelligence.model_selector import ModelSelector
from core.structural_intelligence.norms_selector import NormSelector
from core.structural_intelligence.prompt_builder import PromptBuilder
from core.structural_intelligence.structural_classifier import StructuralClassifier
from core.structural_intelligence.structural_context import StructuralContext

logger = logging.getLogger(__name__)


class StructuralIntelligenceEngine:
    """Pipeline: classificar → normas → modelo → prompt."""

    def __init__(
        self,
        classifier: Optional[StructuralClassifier] = None,
        norms_selector: Optional[NormSelector] = None,
        model_selector: Optional[ModelSelector] = None,
        prompt_builder: Optional[PromptBuilder] = None,
    ):
        self.classifier = classifier or StructuralClassifier()
        self.norms_selector = norms_selector or NormSelector()
        self.model_selector = model_selector or ModelSelector()
        self.prompt_builder = prompt_builder or PromptBuilder()

    def process(
        self,
        text: str,
        *,
        rag_context: str = "",
    ) -> tuple[StructuralContext, str]:
        """
        Executa pipeline SIE completo.

        Retorna (StructuralContext, prompt final pronto para LLM).
        Raises Exception em falha — caller deve fazer fallback.
        """
        classification = self.classifier.classify(text)
        system = classification["system"]
        norms = self.norms_selector.get_norms(system)
        complexity = classification["complexity"]
        model = self.model_selector.select(system, complexity)

        ctx = StructuralContext(
            system=system,
            subsystem=classification.get("subsystem"),
            norms=norms,
            model=model,
            complexity=complexity,
            confidence=classification["confidence"],
            span_estimate=classification.get("span_estimate"),
            metadata={"classifier": classification},
        )

        prompt = self.prompt_builder.build(
            ctx.to_dict(),
            text,
            rag_context=rag_context or None,
        )

        logger.info(
            "sie system=%s complexity=%s model=%s confidence=%.2f",
            ctx.system,
            ctx.complexity,
            ctx.model,
            ctx.confidence,
        )

        return ctx, prompt
