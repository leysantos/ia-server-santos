import json
import logging
from collections.abc import Iterator
from typing import Optional

import requests

from config.settings import (
    OLLAMA_BASE_URL,
    OLLAMA_LLM_FALLBACK_MODEL,
    OLLAMA_LLM_MODEL,
)

logger = logging.getLogger(__name__)


class OllamaClient:
    """
    Cliente LLM via Ollama com fallback de modelo.
    """

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        primary_model: str = OLLAMA_LLM_MODEL,
        fallback_model: str = OLLAMA_LLM_FALLBACK_MODEL,
        timeout: int = 120,
    ):
        self.base_url = base_url.rstrip("/")
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.timeout = timeout

    def _generate_with_model(self, prompt: str, model: str) -> str:
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()["response"].strip()

    def generate(self, prompt: str, model: Optional[str] = None) -> tuple[str, str]:
        """
        Gera resposta LLM. Retorna (texto, modelo_utilizado).
        Tenta modelo primário; em falha, usa fallback.
        """
        models_to_try = [model] if model else [self.primary_model, self.fallback_model]

        last_error: Optional[Exception] = None
        for current_model in models_to_try:
            if not current_model:
                continue
            try:
                logger.info("Ollama generate model=%s", current_model)
                text = self._generate_with_model(prompt, current_model)
                return text, current_model
            except Exception as exc:
                last_error = exc
                logger.warning("Falha Ollama model=%s: %s", current_model, exc)

        raise RuntimeError(
            f"Falha ao gerar resposta LLM (modelos: {models_to_try}): {last_error}"
        )

    def generate_stream(
        self, prompt: str, model: Optional[str] = None
    ) -> Iterator[tuple[str, str]]:
        """
        Stream de tokens Ollama. Yields (token, model_name).
        """
        models_to_try = [model] if model else [self.primary_model, self.fallback_model]
        last_error: Optional[Exception] = None

        for current_model in models_to_try:
            if not current_model:
                continue
            try:
                logger.info("Ollama stream model=%s", current_model)
                with requests.post(
                    f"{self.base_url}/api/generate",
                    json={"model": current_model, "prompt": prompt, "stream": True},
                    timeout=self.timeout,
                    stream=True,
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines(decode_unicode=True):
                        if not line:
                            continue
                        payload = json.loads(line)
                        token = payload.get("response", "")
                        if token:
                            yield token, current_model
                        if payload.get("done"):
                            return
                return
            except Exception as exc:
                last_error = exc
                logger.warning("Falha Ollama stream model=%s: %s", current_model, exc)

        raise RuntimeError(
            f"Falha ao gerar stream LLM (modelos: {models_to_try}): {last_error}"
        )
