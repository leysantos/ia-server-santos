"""Síntese técnica com Qwen3 14B a partir de OCR + visão Gemma3."""

from __future__ import annotations

import json
import logging
from typing import Any

from core.project_review.constants import TECHNICAL_MODEL, TECHNICAL_MODEL_FALLBACK

logger = logging.getLogger(__name__)

_TECHNICAL_REPORT_PROMPT = """Você é engenheiro civil sênior elaborando relatório técnico de revisão.
Com base nos dados de OCR e análise visual abaixo, produza JSON com esta estrutura:
{{
  "titulo": "",
  "tipo_documento": "",
  "resumo_executivo": "",
  "achados": [{{"item": "", "severidade": "baixa|media|alta|critica", "descricao": ""}}],
  "nao_conformidades": [{{"codigo": "", "descricao": "", "norma": "", "recomendacao": ""}}],
  "recomendacoes": [],
  "normas_aplicaveis": [],
  "riscos": [],
  "conclusao": "",
  "parecer": ""
}}
Seja técnico, objetivo e cite normas quando aplicável.
Responda APENAS com JSON válido."""


def synthesize_technical_report(
    *,
    filename: str,
    analyzer: str,
    ocr_data: dict[str, Any],
    vision_analysis: dict[str, Any],
    extra_context: str = "",
) -> dict[str, Any]:
    """Gera relatório técnico estruturado via Qwen3 14B."""
    from models.ollama_client import OllamaClient

    ocr_snippet = json.dumps(
        {
            k: ocr_data.get(k)
            for k in ("format", "texto", "tabelas", "carimbos", "escalas", "quadros")
            if ocr_data.get(k)
        },
        ensure_ascii=False,
    )[:5000]

    vision_snippet = json.dumps(vision_analysis, ensure_ascii=False)[:6000]

    prompt = (
        f"{_TECHNICAL_REPORT_PROMPT}\n\n"
        f"Arquivo: {filename}\n"
        f"Analisador: {analyzer}\n"
        f"OCR:\n{ocr_snippet}\n\n"
        f"Análise visual (Gemma3):\n{vision_snippet}\n"
    )
    if extra_context:
        prompt += f"\nContexto adicional:\n{extra_context[:1500]}\n"

    client = OllamaClient(timeout=120)
    try:
        raw, model_used = client.generate(
            prompt,
            model=TECHNICAL_MODEL,
            fallback_models=[TECHNICAL_MODEL_FALLBACK],
        )
        parsed = _parse_json(raw)
        parsed["_model_used"] = model_used
        return parsed
    except Exception as exc:
        logger.warning("Síntese técnica falhou %s: %s", filename, exc)
        return {
            "titulo": f"Relatório técnico — {filename}",
            "resumo_executivo": vision_analysis.get("resumo_tecnico") or "",
            "nao_conformidades": vision_analysis.get("nao_conformidades") or [],
            "recomendacoes": vision_analysis.get("recomendacoes") or [],
            "conclusao": "Síntese automática parcial (fallback).",
            "error": str(exc),
        }


def _parse_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {"raw": data}
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start : end + 1])
                return data if isinstance(data, dict) else {"raw": data}
            except json.JSONDecodeError:
                pass
        return {"resumo_executivo": raw[:3000], "parse_error": True}
