from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from typing import Any

logger = logging.getLogger(__name__)


_INTENT_SCHEMA = {
    "scope": "string — escopo técnico (ex: passarela, alvenaria, instalação elétrica)",
    "title": "string — título do orçamento",
    "obra_type": "string opcional — ED, RF, FIE, IE, OPMF, SEE, AG",
    "dimensions": {"length": 0, "width": 0, "height": 0, "thickness": 0, "span": 0},
    "items": [{"name": "str", "query": "str", "unit": "m²", "quantity": 0, "calculation_note": "str"}],
}


class IntentParser:
    """
    LLM interpreta texto → intent estruturado.
    PROIBIDO retornar preços — apenas escopo, dimensões e insumos.
    """

    PROMPT = """Você é um engenheiro de orçamentos civis (PPD municipal).

Extraia a INTENÇÃO TÉCNICA do texto abaixo para montar orçamento completo.

REGRAS OBRIGATÓRIAS:
- NÃO inclua preços, valores monetários ou códigos SINAPI
- Retorne APENAS um JSON válido (sem markdown)
- Campos: scope, title, obra_type (RF para pontes/passarelas/rodovias), dimensions, items[]
- dimensions: length (vão/comprimento em m), width (largura em m), height, thickness
- items[]: opcional para passarela/ponte (o sistema usa template PPD com 4 etapas); para outros escopos liste serviços
- Cada item: name, query (termo de busca SINAPI), unit (m, m², m³, un, h), quantity (se inferível), calculation_note

Exemplo passarela:
{{"scope":"passarela pedestre","title":"Passarela sobre igarapé","obra_type":"RF","dimensions":{{"length":10,"width":2}},"items":[
  {{"name":"Locação de obra","query":"locação topográfica","unit":"un","quantity":1}},
  {{"name":"Estaca pré-moldada","query":"estaca pre moldada concreto","unit":"m","quantity":20}},
  {{"name":"Bloco de coroamento","query":"bloco concreto estrutural","unit":"m³","quantity":4}},
  {{"name":"Estrutura metálica passarela","query":"estrutura metalica","unit":"kg","quantity":500}},
  {{"name":"Guarda-corpo","query":"guarda corpo metalico","unit":"m","quantity":24}}
]}}

Texto do usuário:
{text}
"""

    def __init__(self, llm_client: Any | None = None) -> None:
        self._llm = llm_client

    def _build_prompt(self, text: str, knowledge_context: str = "") -> str:
        body = self.PROMPT.format(text=text.strip())
        if knowledge_context and knowledge_context.strip():
            return f"{knowledge_context.strip()}\n\n{body}"
        return body

    def parse(self, text: str, use_llm: bool = True) -> dict[str, Any]:
        result = None
        for event_type, data in self.parse_events(text, use_llm=use_llm):
            if event_type == "intent":
                result = data
            if event_type == "error":
                raise RuntimeError(data.get("message", "Erro no parser"))
        if result is None:
            return self._parse_fallback(text)
        return result

    def parse_events(
        self, text: str, use_llm: bool = True, knowledge_context: str = ""
    ) -> Iterator[tuple[str, dict[str, Any]]]:
        if use_llm and self._llm:
            yield ("status", {"message": "Verificando Ollama…", "phase": "intent_parser"})
            if not getattr(self._llm, "ping", lambda: True)():
                yield (
                    "status",
                    {
                        "message": "Ollama offline — usando parser local (regex). Inicie: ollama serve",
                        "phase": "fallback",
                    },
                )
            else:
                models = getattr(self._llm, "list_models", lambda: [])()
                model_hint = self._llm.primary_model if self._llm else ""
                yield (
                    "status",
                    {
                        "message": f"Ollama online — gerando intent com {model_hint}…",
                        "phase": "intent_parser",
                        "models_available": len(models),
                    },
                )
                try:
                    toks: list[str] = []
                    model_used = ""
                    for token, model in self._llm.generate_stream(
                        self._build_prompt(text, knowledge_context)
                    ):
                        model_used = model
                        toks.append(token)
                        yield (
                            "token",
                            {"token": token, "llm_model": model, "phase": "intent_parser"},
                        )
                    raw = "".join(toks)
                    if not raw.strip():
                        raise ValueError("Resposta vazia do Ollama")
                    data = self._extract_json(raw)
                    data["llm_model"] = model_used
                    data["parser"] = "llm"
                    yield (
                        "status",
                        {
                            "message": "Intent estruturado pela IA",
                            "phase": "intent_parser",
                            "llm_model": model_used,
                        },
                    )
                    yield ("intent", data)
                    return
                except Exception as exc:
                    logger.warning("IntentParser LLM falhou: %s", exc)
                    yield (
                        "status",
                        {
                            "message": f"LLM falhou ({exc}) — usando parser regex local",
                            "phase": "fallback",
                        },
                    )
        elif use_llm and not self._llm:
            yield (
                "status",
                {
                    "message": "Cliente Ollama não configurado — parser regex local",
                    "phase": "fallback",
                },
            )
        else:
            yield ("status", {"message": "Parser regex (IA desligada)", "phase": "fallback"})

        data = self._parse_fallback(text)
        data["parser"] = "regex_fallback"
        yield ("intent", data)

    def _parse_fallback(self, text: str) -> dict[str, Any]:
        lower = text.lower()
        scope = "geral"
        obra_type = "RF"

        if any(k in lower for k in ("passarela", "ponte", "tabuleiro", "viga ponte", "igarap")):
            scope = "passarela"
            obra_type = "RF"
        elif any(k in lower for k in ("muro", "alvenaria")) and "bloco" in lower and "passarela" not in lower:
            scope = "alvenaria estrutural"
        elif any(k in lower for k in ("elétric", "eletric", "tomada", "cabo")):
            scope = "instalação elétrica"
            obra_type = "IE"
        elif any(k in lower for k in ("estrutur", "fundação", "pilar", "laje", "estaca")):
            scope = "estrutura"
            obra_type = "RF"

        dims: dict[str, float] = {}

        span_m = re.search(r"v[aã]o\s*(?:de\s*)?(\d+(?:[.,]\d+)?)\s*m?", lower)
        length_m = re.search(r"(\d+(?:[.,]\d+)?)\s*m(?:etros?)?(?:\s+de\s+(?:comprimento|extens))?", lower)
        width_m = re.search(r"largura\s*(?:de\s*|da\s*)?(\d+(?:[.,]\d+)?)\s*m?", lower)
        height_m = re.search(r"(\d+(?:[.,]\d+)?)\s*m(?:etros?)?\s+de\s+altura", lower)
        if not height_m:
            height_m = re.search(r"altura\s*(?:de\s*)?(\d+(?:[.,]\d+)?)\s*m?", lower)

        if span_m:
            dims["length"] = float(span_m.group(1).replace(",", "."))
        elif length_m:
            dims["length"] = float(length_m.group(1).replace(",", "."))
        if width_m:
            dims["width"] = float(width_m.group(1).replace(",", "."))
        if height_m:
            dims["height"] = float(height_m.group(1).replace(",", "."))

        title = text.strip()[:120] if text.strip() else "Orçamento"

        items: list[dict] = []
        if scope == "passarela":
            length = dims.get("length", 10)
            width = dims.get("width", 2)
            perimeter = 2 * (length + width)
            items = [
                {"name": "Mobilização e desmobilização", "query": "mobilizacao canteiro", "unit": "un", "quantity": 1},
                {"name": "Locação topográfica", "query": "locacao topografica", "unit": "un", "quantity": 1},
                {"name": "Estaca pré-moldada concreto", "query": "estaca pre moldada", "unit": "m", "quantity": round(length * 2, 1)},
                {"name": "Bloco de coroamento / apoio", "query": "bloco concreto estrutural", "unit": "m³", "quantity": round(length * 0.4, 2)},
                {"name": "Concreto estrutural bloco", "query": "concreto fck 25", "unit": "m³", "quantity": round(length * width * 0.3, 2)},
                {"name": "Armadura aço CA-50", "query": "aco ca-50", "unit": "kg", "quantity": round(length * width * 80, 0)},
                {"name": "Estrutura metálica / tabuleiro", "query": "estrutura metalica", "unit": "m²", "quantity": round(length * width, 2)},
                {"name": "Piso antiderrapante passarela", "query": "piso antiderrapante", "unit": "m²", "quantity": round(length * width * 1.05, 2)},
                {"name": "Guarda-corpo metálico", "query": "guarda corpo metalico", "unit": "m", "quantity": round(perimeter, 1)},
                {"name": "Pintura proteção", "query": "pintura esmalte sintetico", "unit": "m²", "quantity": round(perimeter * 1.1, 1)},
                {"name": "Sinalização e acessibilidade", "query": "placa sinalizacao", "unit": "un", "quantity": 4},
            ]

        return {
            "scope": scope,
            "title": title,
            "obra_type": obra_type,
            "dimensions": dims,
            "items": items,
            "parser": "regex_fallback",
        }

    def _extract_json(self, text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if not match:
            raise ValueError("JSON não encontrado na resposta LLM")
        data = json.loads(match.group())
        if "scope" not in data:
            data["scope"] = data.get("discipline", "geral")
        scope_lower = str(data.get("scope", "")).lower()
        if any(k in scope_lower for k in ("passarela", "ponte", "igarap")):
            data.pop("items", None)
        if not data.get("obra_type"):
            if "passarela" in str(data.get("scope", "")).lower() or "ponte" in str(data.get("title", "")).lower():
                data["obra_type"] = "RF"
        data["parser"] = "llm"
        return data
