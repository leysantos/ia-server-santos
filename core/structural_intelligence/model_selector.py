"""
Model Selector — escolhe modelo LLM por sistema + complexidade.
"""

from __future__ import annotations

from config.settings import OLLAMA_CHAT_MODEL, OLLAMA_LLM_MODEL


class ModelSelector:
    MODEL_LIGHT = OLLAMA_CHAT_MODEL  # qwen3:8b
    MODEL_HEAVY = OLLAMA_LLM_MODEL   # qwen3:14b

    def select(self, system: str, complexity: str) -> str:
        if system == "STEEL_STRUCTURE" and complexity == "HIGH":
            return self.MODEL_HEAVY
        if system == "CONCRETE_ARMED":
            return self.MODEL_LIGHT
        if system == "TIMBER_STRUCTURE":
            return self.MODEL_LIGHT
        if system == "CONCRETE_PRESTRESSED" and complexity == "HIGH":
            return self.MODEL_HEAVY
        return self.MODEL_LIGHT
