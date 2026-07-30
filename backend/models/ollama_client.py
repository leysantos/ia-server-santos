import json
import logging
import threading
import time
from collections.abc import Iterator
from typing import Optional

import requests

from config.settings import (
    OLLAMA_BASE_URL,
    OLLAMA_CONNECT_TIMEOUT,
    OLLAMA_LLM_FALLBACK_MODEL,
    OLLAMA_LLM_MODEL,
)
from core.runtime.ollama_defaults import merge_llm_options, ollama_keep_alive

logger = logging.getLogger(__name__)

_PREFERRED_MODEL_SUBSTRINGS = (
    "qwen3:14",
    "gemma4",
    "deepseek-r1",
    "qwen2.5-coder",
    "qwen2.5",
    "mistral",
    "gemma3",
    "deepseek-coder",
    "phi3",
    "qwen3:8",
)

_models_cache: list[str] = []
_models_cache_at: float = 0.0
_models_cache_lock = threading.Lock()
_ping_ok_at: float = 0.0
_ping_lock = threading.Lock()


def _model_list_cache_ttl() -> float:
    try:
        from config import settings

        return float(getattr(settings, "OLLAMA_MODEL_LIST_CACHE_SEC", 60))
    except Exception:
        return 60.0


def _ping_cache_ttl() -> float:
    try:
        from config import settings

        return float(getattr(settings, "OLLAMA_PING_CACHE_SEC", 15))
    except Exception:
        return 15.0


def invalidate_ollama_client_cache() -> None:
    """Invalida cache de modelos/ping (útil após pull/unload)."""
    global _models_cache, _models_cache_at, _ping_ok_at
    with _models_cache_lock:
        _models_cache = []
        _models_cache_at = 0.0
    with _ping_lock:
        _ping_ok_at = 0.0


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

    def ping(self, *, force: bool = False) -> bool:
        """Verifica se o Ollama responde (cache curto para evitar /api/tags a cada generate)."""
        global _ping_ok_at
        if not force:
            with _ping_lock:
                if _ping_ok_at and (time.time() - _ping_ok_at) < _ping_cache_ttl():
                    return True
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=(self.connect_timeout, 5),
            )
            response.raise_for_status()
            with _ping_lock:
                _ping_ok_at = time.time()
            return True
        except Exception as exc:
            logger.warning("Ollama ping falhou (%s): %s", self.base_url, exc)
            return False

    def list_models(self, *, force: bool = False) -> list[str]:
        """Lista modelos instalados no Ollama (cache TTL configurável)."""
        global _models_cache, _models_cache_at, _ping_ok_at
        ttl = _model_list_cache_ttl()
        if not force and ttl > 0:
            with _models_cache_lock:
                if _models_cache and (time.time() - _models_cache_at) < ttl:
                    return list(_models_cache)

        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=(self.connect_timeout, 10),
            )
            response.raise_for_status()
            data = response.json()
            models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
            with _models_cache_lock:
                _models_cache = models
                _models_cache_at = time.time()
            with _ping_lock:
                _ping_ok_at = time.time()
            return models
        except Exception as exc:
            logger.warning("Ollama list_models falhou: %s", exc)
            with _models_cache_lock:
                if _models_cache:
                    return list(_models_cache)
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
        from core.llm_override import is_gemini_model

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
            # Não misturar fallback Ollama quando o usuário escolheu Gemini
            if not is_gemini_model(models_to_try[0]):
                models_to_try.append(self.fallback_model)

        resolved: list[str] = []
        installed = self.list_models()
        for m in models_to_try:
            if not m:
                continue
            # Cloud Gemini não aparece em `ollama list` — preservar sempre
            if is_gemini_model(m):
                if m not in resolved:
                    resolved.append(m)
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

    def _build_generate_body(
        self,
        prompt: str,
        model: str,
        *,
        stream: bool,
        format_json: bool = False,
        options: dict | None = None,
    ) -> dict:
        body: dict = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
            "keep_alive": ollama_keep_alive(),
        }
        if format_json:
            body["format"] = "json"
        merged = merge_llm_options(options)
        if merged:
            body["options"] = merged
        return body

    def _generate_with_model(
        self,
        prompt: str,
        model: str,
        *,
        format_json: bool = False,
        options: dict | None = None,
    ) -> str:
        body = self._build_generate_body(
            prompt, model, stream=False, format_json=format_json, options=options
        )
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
        Suporta override cloud Gemini (gemini-*).
        """
        from core.llm_override import canonical_gemini_model, is_gemini_model

        models_to_try = self._models_to_try(model, fallback_models)
        if models_to_try and is_gemini_model(models_to_try[0]):
            gemini_id = canonical_gemini_model(models_to_try[0])
            try:
                from core.inspection_report.gemini_client import generate_text

                logger.info("Gemini generate model=%s", gemini_id)
                text = generate_text(
                    prompt,
                    temperature=0.2,
                    max_output_tokens=8192,
                    model=gemini_id,
                )
                return text, gemini_id
            except Exception as exc:
                logger.warning(
                    "Falha Gemini model=%s: %s — tentando fallback Ollama", gemini_id, exc
                )
                models_to_try = [m for m in models_to_try if not is_gemini_model(m)]
                if not models_to_try:
                    raise

        if not self.ping():
            raise ConnectionError(
                f"Ollama indisponível em {self.base_url} — verifique se o serviço está rodando (ollama serve)"
            )

        last_error: Optional[Exception] = None
        for current_model in models_to_try:
            if is_gemini_model(current_model):
                continue
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

    def _extract_stream_text(self, payload: dict) -> str:
        """Texto visível no chunk Ollama (response ou thinking em modelos reasoning)."""
        parts: list[str] = []
        response = payload.get("response")
        if isinstance(response, str) and response:
            parts.append(response)
        thinking = payload.get("thinking")
        if isinstance(thinking, str) and thinking:
            parts.append(thinking)
        return "".join(parts)

    def generate_stream(
        self,
        prompt: str,
        model: Optional[str] = None,
        fallback_models: Optional[list[str]] = None,
        format_json: bool = False,
        options: Optional[dict] = None,
    ) -> Iterator[tuple[str, str]]:
        """
        Stream de tokens. Yields (token, model_name).
        Gemini: generate_content_stream (tokens em tempo real, como Ollama).
        """
        from core.llm_override import canonical_gemini_model, is_gemini_model

        models_to_try = self._models_to_try(model, fallback_models)
        if models_to_try and is_gemini_model(models_to_try[0]):
            gemini_id = canonical_gemini_model(models_to_try[0])
            try:
                from core.inspection_report.gemini_client import generate_text_stream

                logger.info("Gemini stream(model=%s) — generate_content_stream", gemini_id)
                for piece in generate_text_stream(
                    prompt,
                    temperature=0.2,
                    max_output_tokens=8192,
                    model=gemini_id,
                ):
                    yield piece, gemini_id
                return
            except Exception as exc:
                logger.warning(
                    "Falha Gemini stream model=%s: %s — fallback Ollama", gemini_id, exc
                )
                models_to_try = [m for m in models_to_try if not is_gemini_model(m)]
                if not models_to_try:
                    raise

        if not self.ping():
            raise ConnectionError(
                f"Ollama indisponível em {self.base_url} — verifique se o serviço está rodando (ollama serve)"
            )

        last_error: Optional[Exception] = None

        for current_model in models_to_try:
            if is_gemini_model(current_model):
                continue
            try:
                logger.info("Ollama stream model=%s json=%s", current_model, format_json)
                body = self._build_generate_body(
                    prompt,
                    current_model,
                    stream=True,
                    format_json=format_json,
                    options=options,
                )
                token_count = 0
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
                        token = self._extract_stream_text(payload)
                        if token:
                            token_count += len(token)
                            yield token, current_model
                        if payload.get("done"):
                            if token_count == 0:
                                raise RuntimeError(
                                    f"Modelo {current_model} concluiu sem emitir tokens"
                                )
                            return
                if token_count == 0:
                    raise RuntimeError(f"Modelo {current_model} retornou stream vazio")
                return
            except Exception as exc:
                last_error = exc
                logger.warning("Falha Ollama stream model=%s: %s", current_model, exc)

        raise RuntimeError(
            f"Falha ao gerar stream LLM (modelos: {models_to_try}): {last_error}"
        )
