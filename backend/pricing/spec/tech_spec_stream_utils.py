"""Utilitários de streaming — anti-loop e limites de geração."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

_MIN_LOOP_CHECK_CHARS = 2_500
_HEADING_RE = re.compile(r"^#{2,4}\s+.+$", re.M)


def has_repetition_loop(text: str) -> bool:
    """
    Detecta loop real do modelo (não confunde com template repetido por serviço).

    Especificações técnicas repetem estrutura por serviço — só dispara em:
    - parágrafos idênticos consecutivos (≥120 chars);
    - mesmo título Markdown repetido 3× seguidas;
    - bloco longo (≥350 chars) duplicado no final.
    """
    if len(text) < _MIN_LOOP_CHECK_CHARS:
        return False

    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if len(p.strip()) >= 120]
    if len(paragraphs) >= 4:
        last = paragraphs[-1]
        if all(p == last for p in paragraphs[-4:]):
            return True

    tail = text[-6_000:]
    headings = _HEADING_RE.findall(tail)
    if len(headings) >= 3:
        for i in range(len(headings) - 2):
            if headings[i] == headings[i + 1] == headings[i + 2]:
                return True

    for block_size in (400, 350, 300):
        if len(text) < block_size * 2:
            continue
        block = text[-block_size:]
        prior = text[-block_size * 2 : -block_size]
        if block.strip() and block == prior:
            return True

    return False


def trim_repetition_tail(text: str) -> str:
    """Remove repetições no final do texto após corte por guard."""
    trimmed = text
    while len(trimmed) > 600 and has_repetition_loop(trimmed):
        cut = max(300, len(trimmed) // 10)
        trimmed = trimmed[:-cut].rstrip()
    return trimmed.rstrip()


def generate_stream_guarded(
    client: Any,
    prompt: str,
    *,
    model: str,
    fallback_models: list[str] | None,
    options: dict[str, Any],
    max_chars: int = 24_000,
    max_token_events: int = 8_000,
    yield_all_tokens: bool = False,
) -> Iterator[tuple[str, dict[str, Any]]]:
    """
    Stream com parada em loop ou tamanho máximo.
    Yields: ('token', {token}), ('guard', {message}), ('complete', {text, model})
    """
    accumulated = ""
    model_used = model
    token_events = 0

    for token, used in client.generate_stream(
        prompt,
        model=model,
        fallback_models=fallback_models,
        options=options,
    ):
        model_used = used
        candidate = accumulated + token
        token_events += 1

        if len(candidate) > max_chars:
            yield "guard", {
                "message": "Limite de tamanho atingido — encerrando esta parte.",
                "phase": "guard",
            }
            break

        if token_events > max_token_events:
            yield "guard", {
                "message": "Limite de tokens desta parte — continuando com o próximo bloco.",
                "phase": "guard",
            }
            break

        if has_repetition_loop(candidate):
            yield "guard", {
                "message": "Repetição detectada — encerrando esta parte para evitar loop.",
                "phase": "guard",
            }
            break

        accumulated = candidate
        if yield_all_tokens or token_events % 8 == 0 or len(token) > 40:
            yield "token", {"token": token}

    yield "complete", {
        "text": trim_repetition_tail(accumulated),
        "model": model_used,
    }
