import json
import logging
from collections.abc import Iterator
from typing import Optional

import requests

from config.settings import (
    OLLAMA_BASE_URL,
    OLLAMA_CONNECT_TIMEOUT,
    OLLAMA_LLM_FALLBACK_MODEL,
    OLLAMA_LLM_MODEL,
)

logger = logging.getLogger(__name__)

_PREFERRED_MODEL_SUBSTRINGS = (
    "gemma4",
    "deepseek-r1",
    "qwen2.5-coder",
    "qwen2.5",
    "mistral",
    "gemma3",
    "deepseek-coder",
    "phi3",
)


class OllamaClient:
    """
    Cliente LLM via Ollama com fallback de modelo e timeout de conexão curto.
    """

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        primary_model: str = OLLAMA_LLM_MODEL,
        fallback_model: str = OLLAMA_LLM_FALLBACK_MODEL,
        timeout: int = 60,
        connect_timeout: int = OLLAMA_CONNECT_TIMEOUT,
    ):
        self.base_url = base_url.rstrip("/")
        self.read_timeout = timeout
        self.connect_timeout = connect_timeout
        self.primary_model, self.fallback_model = self._resolve_installed_models(
            primary_model, fallback_model
        )

    def _timeouts(self) -> tuple[int, int]:
        return (self.connect_timeout, self.read_timeout)

    def _stream_timeouts(self) -> tuple[int, int]:
        """Timeout entre chunks no SSE — modelos reasoning podem pausar longamente."""
        idle = max(int(self.read_timeout), 600)
        return (self.connect_timeout, idle)

    def ping(self) -> bool:
        """Verifica se o Ollama responde (timeout curto — não bloqueia minutos)."""
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=(self.connect_timeout, 5),
            )
            response.raise_for_status()
            return True
        except Exception as exc:
            logger.warning("Ollama ping falhou (%s): %s", self.base_url, exc)
            return False

    def list_models(self) -> list[str]:
        """Lista modelos instalados no Ollama."""
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=(self.connect_timeout, 10),
            )
            response.raise_for_status()
            data = response.json()
            return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except Exception as exc:
            logger.warning("Ollama list_models falhou: %s", exc)
            return []

    def _resolve_installed_models(
        self, primary: str, fallback: str
    ) -> tuple[str, str]:
        installed = self.list_models()
        if not installed:
            logger.info("Ollama sem modelos listados — usando config: %s / %s", primary, fallback)
            return primary, fallback or primary

        def pick(preferred: str) -> str | None:
            if not preferred:
                return None
            if preferred in installed:
                return preferred
            base = preferred.split(":")[0]
            for name in installed:
                if name.split(":")[0] == base:
                    return name
            for name in installed:
                if base in name.lower():
                    return name
            return None

        resolved_primary = pick(primary) or pick(fallback)
        if not resolved_primary:
            for hint in _PREFERRED_MODEL_SUBSTRINGS:
                for name in installed:
                    if hint in name.lower():
                        resolved_primary = name
                        break
                if resolved_primary:
                    break
        resolved_primary = resolved_primary or installed[0]

        resolved_fallback = pick(fallback) if fallback else None
        if not resolved_fallback or resolved_fallback == resolved_primary:
            resolved_fallback = next((m for m in installed if m != resolved_primary), resolved_primary)

        if resolved_primary != primary or resolved_fallback != fallback:
            logger.info(
                "Ollama modelos resolvidos: %s → %s, fallback %s → %s",
                primary,
                resolved_primary,
                fallback,
                resolved_fallback,
            )
        return resolved_primary, resolved_fallback

    def _models_to_try(
        self,
        model: Optional[str],
        fallback_models: Optional[list[str]],
    ) -> list[str]:
        models_to_try: list[str] = []
        if model:
            models_to_try.append(model)
        if fallback_models:
            for fb in fallback_models:
                if fb and fb not in models_to_try:
                    models_to_try.append(fb)
        if not models_to_try:
            models_to_try = [self.primary_model, self.fallback_model]
        elif self.fallback_model and self.fallback_model not in models_to_try:
            models_to_try.append(self.fallback_model)

        resolved: list[str] = []
        installed = self.list_models()
        for m in models_to_try:
            if not m:
                continue
            if not installed or m in installed:
                if m not in resolved:
                    resolved.append(m)
                continue
            base = m.split(":")[0]
            match = next((n for n in installed if n.split(":")[0] == base), None)
            if match and match not in resolved:
                resolved.append(match)
        if not resolved:
            resolved = [self.primary_model, self.fallback_model]
        return [m for m in resolved if m]

    def _generate_with_model(
        self,
        prompt: str,
        model: str,
        *,
        format_json: bool = False,
        options: dict | None = None,
    ) -> str:
        body: dict = {"model": model, "prompt": prompt, "stream": False}
        if format_json:
            body["format"] = "json"
        if options:
            body["options"] = options
        response = requests.post(
            f"{self.base_url}/api/generate",
            json=body,
            timeout=self._timeouts(),
        )
        response.raise_for_status()
        return response.json()["response"].strip()

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        fallback_models: Optional[list[str]] = None,
        format_json: bool = False,
        options: Optional[dict] = None,
    ) -> tuple[str, str]:
        """
        Gera resposta LLM. Retorna (texto, modelo_utilizado).
        Tenta modelo primário; em falha, usa fallback(s).
        """
        if not self.ping():
            raise ConnectionError(
                f"Ollama indisponível em {self.base_url} — verifique se o serviço está rodando (ollama serve)"
            )

        models_to_try = self._models_to_try(model, fallback_models)
        last_error: Optional[Exception] = None
        for current_model in models_to_try:
            try:
                logger.info("Ollama generate model=%s json=%s", current_model, format_json)
                text = self._generate_with_model(
                    prompt, current_model, format_json=format_json, options=options
                )
                return text, current_model
            except Exception as exc:
                last_error = exc
                logger.warning("Falha Ollama model=%s: %s", current_model, exc)

        raise RuntimeError(
            f"Falha ao gerar resposta LLM (modelos: {models_to_try}): {last_error}"
        )

    def generate_stream(
        self,
        prompt: str,
        model: Optional[str] = None,
        fallback_models: Optional[list[str]] = None,
        format_json: bool = False,
        options: Optional[dict] = None,
    ) -> Iterator[tuple[str, str]]:
        """
        Stream de tokens Ollama. Yields (token, model_name).
        """
        if not self.ping():
            raise ConnectionError(
                f"Ollama indisponível em {self.base_url} — verifique se o serviço está rodando (ollama serve)"
            )

        models_to_try = self._models_to_try(model, fallback_models)
        last_error: Optional[Exception] = None

        for current_model in models_to_try:
            try:
                logger.info("Ollama stream model=%s json=%s", current_model, format_json)
                body: dict = {"model": current_model, "prompt": prompt, "stream": True}
                if format_json:
                    body["format"] = "json"
                if options:
                    body["options"] = options
                with requests.post(
                    f"{self.base_url}/api/generate",
                    json=body,
                    timeout=self._stream_timeouts(),
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
