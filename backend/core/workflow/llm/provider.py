"""Interface LLM desacoplada para agentes do workflow."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, prompt: str, *, system: str | None = None, **kwargs: Any) -> str:
        ...


class OllamaProvider(LLMProvider):
    def __init__(self, model: str | None = None) -> None:
        from config.settings import get_settings

        settings = get_settings()
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = model or settings.ollama_chat_model

    def complete(self, prompt: str, *, system: str | None = None, **kwargs: Any) -> str:
        import httpx

        from config.settings import get_settings

        settings = get_settings()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {"model": self.model, "messages": messages, "stream": False}
        payload.update(kwargs)
        with httpx.Client(timeout=settings.ollama_chat_timeout) as client:
            resp = client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return str(data.get("message", {}).get("content", ""))


class OpenAIProvider(LLMProvider):
    def complete(self, prompt: str, *, system: str | None = None, **kwargs: Any) -> str:
        raise NotImplementedError("OpenAIProvider — configurar API key externa")


class DeepSeekProvider(LLMProvider):
    def complete(self, prompt: str, *, system: str | None = None, **kwargs: Any) -> str:
        raise NotImplementedError("DeepSeekProvider — configurar API key externa")


class GeminiProvider(LLMProvider):
    def complete(self, prompt: str, *, system: str | None = None, **kwargs: Any) -> str:
        raise NotImplementedError("GeminiProvider — configurar API key externa")


def get_default_llm() -> LLMProvider:
    return OllamaProvider()
