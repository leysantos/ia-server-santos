"""Parse tolerante de JSON retornado por LLMs."""

from __future__ import annotations

import json
import re
from typing import Any


def parse_llm_json(text: str, *, require_keys: tuple[str, ...] = ()) -> dict[str, Any]:
    """Extrai e parseia JSON de respostas LLM (markdown, vírgulas finais, etc.)."""
    cleaned = _strip_fences(text.strip())
    blob = _extract_object(cleaned)
    if not blob:
        raise ValueError("JSON não encontrado na resposta LLM")

    last_error: Exception | None = None
    for candidate in _repair_candidates(blob):
        try:
            data = json.loads(candidate)
            if not isinstance(data, dict):
                raise ValueError("Resposta não é um objeto JSON")
            for key in require_keys:
                if not data.get(key):
                    raise ValueError(f"JSON sem campo obrigatório: {key}")
            return data
        except Exception as exc:
            last_error = exc
            continue

    raise ValueError(f"JSON inválido: {last_error}")


def _strip_fences(text: str) -> str:
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def _extract_object(text: str) -> str:
    match = re.search(r"\{[\s\S]*\}", text)
    return match.group(0) if match else ""


def _repair_candidates(blob: str) -> list[str]:
    out = [blob]
    step = blob
    step = re.sub(r",\s*([}\]])", r"\1", step)
    if step not in out:
        out.append(step)
    step2 = step.replace("'", '"')
    if step2 not in out:
        out.append(step2)
    step3 = re.sub(r"//[^\n]*", "", step2)
    step3 = re.sub(r"/\*[\s\S]*?\*/", "", step3)
    if step3 not in out:
        out.append(step3)
    step4 = re.sub(r",\s*([}\]])", r"\1", step3)
    if step4 not in out:
        out.append(step4)
    return out
