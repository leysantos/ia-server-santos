"""
Model Selector — escolhe modelo LLM por sistema + complexidade.
"""

from __future__ import annotations

from config.settings import OLLAMA_CHAT_MODEL, OLLAMA_LLM_MODEL


class ModelSelector:
    MODEL_LIGHT = OLLAMA_CHAT_MODEL  # qwen3:8b
    MODEL_HEAVY = OLLAMA_LLM_MODEL   # qwen3:14b

    def select(self, system: str, complexity: str) -> str:
        from config import settings

        if settings.USE_MODEL_ROUTER:
            from core.models.model_router import get_model_router

            router = get_model_router()
            task = router.resolve_engineering_task(
                "",
                "ESTRUTURAL",
                complexity=complexity,
            )
            if system == "STEEL_STRUCTURE" and complexity == "HIGH":
                task = "engineering_primary"
            elif system in ("CONCRETE_ARMED", "TIMBER_STRUCTURE"):
                task = "engineering_fallback"
            return router.get_model(
                task,
                {"discipline": "ESTRUTURAL", "complexity": complexity, "module": "sie"},
            )

        if system == "STEEL_STRUCTURE" and complexity == "HIGH":
            return self.MODEL_HEAVY
        if system == "CONCRETE_ARMED":
            return self.MODEL_LIGHT
        if system == "TIMBER_STRUCTURE":
            return self.MODEL_LIGHT
        if system == "CONCRETE_PRESTRESSED" and complexity == "HIGH":
            return self.MODEL_HEAVY
        return self.MODEL_LIGHT
