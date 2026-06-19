"""Planejamento WBS por LLM — raciocínio de engenheiro orçamentista (PPD municipal)."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from core.llm_json import parse_llm_json
from core.models.budget_model_routing import estimate_budget_complexity

logger = logging.getLogger(__name__)

_WBS_PROMPT = """Você é engenheiro civil sênior, especialista em orçamentos públicos (PPD MC/OR, SINAPI/SEMINF).

Monte a ESTRUTURA COMPLETA do orçamento (WBS) — etapas macro e serviços detalhados, sequência lógica de execução.

Raciocínio de obra:
- Etapas = FASE DE EXECUÇÃO (não agrupe só por nome parecido).
- FUNDAÇÕES inclui: locação/gabarito, escavação, lastro concreto magro, formas, armadura CA-50, concretagem bloco/sapata, estacas, graute.
- ESTRUTURA inclui: montagem estrutura metálica, tabuleiro, pilares, concretagem, desforma.
- PRELIMINARES inclui: mobilização, locação topográfica, canteiro, placa de obra.

REGRAS JSON:
- Responda SOMENTE um objeto JSON válido (sem markdown, sem comentários, aspas duplas).
- NÃO inclua preços nem códigos SINAPI inventados.
- Campo "query" = termos para buscar composição na base SINAPI/SEMINF.
- Estime quantidades com base nas dimensões informadas.
- Mínimo 4 etapas; liste TODOS os serviços necessários.

Schema:
{{
  "title": "string",
  "scope": "string",
  "obra_type": "RF",
  "dimensions": {{"length": 10, "width": 2, "height": 0, "thickness": 0}},
  "etapas": [
    {{
      "code": "1",
      "name": "SERVIÇOS PRELIMINARES",
      "services": [
        {{
          "code": "1.01",
          "name": "Nome do serviço",
          "query": "termos busca sinapi",
          "unit": "un",
          "quantity": 1,
          "calculation_note": "1 verba global"
        }}
      ]
    }}
  ]
}}

{knowledge_block}

Pedido:
{text}
"""


class EngineeringWbsPlanner:
    """
    LLM monta WBS completa (etapas + serviços) com raciocínio de engenheiro.
    Substitui templates fixos quando Ollama está disponível.
    """

    def __init__(self, llm_client: Any | None = None) -> None:
        self._llm = llm_client

    def plan_events(
        self,
        text: str,
        knowledge_context: str = "",
    ) -> Iterator[tuple[str, dict[str, Any]]]:
        if not self._llm:
            yield ("status", {"message": "LLM não configurado — WBS por template", "phase": "fallback"})
            yield ("intent", self._fallback_wbs(text))
            return

        yield ("status", {"message": "Verificando Ollama…", "phase": "wbs_planner"})
        if not getattr(self._llm, "ping", lambda: True)():
            yield (
                "status",
                {"message": "Ollama offline — WBS por template local", "phase": "fallback"},
            )
            yield ("intent", self._fallback_wbs(text))
            return

        cx = estimate_budget_complexity(text.strip())
        yield (
            "status",
            {
                "message": f"Engenheiro IA montando WBS · complexidade {cx}…",
                "phase": "wbs_planner",
                "complexity": cx,
            },
        )

        knowledge_block = ""
        if knowledge_context and knowledge_context.strip():
            knowledge_block = (
                "Modelos de referência:\n" + knowledge_context.strip()[:6000]
            )

        prompt = _WBS_PROMPT.format(
            knowledge_block=knowledge_block,
            text=text.strip(),
        )

        try:
            from core.models.budget_model_routing import budget_generate

            raw, model_used = budget_generate(
                prompt,
                user_text=text.strip(),
                task="wbs",
                format_json=True,
                client=self._llm,
            )
            if not raw.strip():
                raise ValueError("Resposta vazia do Ollama")

            for i in range(0, len(raw), 48):
                yield (
                    "token",
                    {"token": raw[i : i + 48], "llm_model": model_used, "phase": "wbs_planner"},
                )

            data = parse_llm_json(raw, require_keys=("etapas",))
            data["llm_model"] = model_used
            data["parser"] = "llm_wbs"
            data["structure_source"] = "llm_wbs"
            self._normalize_etapas(data)
            svc_count = sum(len(e.get("services") or []) for e in data.get("etapas") or [])
            yield (
                "status",
                {
                    "message": f"WBS montada — {len(data.get('etapas') or [])} etapas, {svc_count} serviços · {model_used}",
                    "phase": "wbs_planner",
                    "llm_model": model_used,
                    "complexity": estimate_budget_complexity(text.strip(), data),
                },
            )
            yield ("intent", data)
        except Exception as exc:
            logger.warning("EngineeringWbsPlanner falhou (%s), tentando stream…", exc)
            try:
                data = self._plan_via_stream(prompt, text.strip())
                svc_count = sum(len(e.get("services") or []) for e in data.get("etapas") or [])
                yield (
                    "status",
                    {
                        "message": f"WBS montada (stream) — {len(data.get('etapas') or [])} etapas, {svc_count} serviços",
                        "phase": "wbs_planner",
                        "llm_model": data.get("llm_model"),
                    },
                )
                yield ("intent", data)
            except Exception as exc2:
                logger.warning("EngineeringWbsPlanner stream falhou: %s", exc2)
                yield (
                    "status",
                    {
                        "message": f"WBS LLM falhou — template local ({exc2})",
                        "phase": "fallback",
                    },
                )
                fallback = self._fallback_wbs(text)
                fallback["wbs_error"] = str(exc2)
                yield ("intent", fallback)

    def _plan_via_stream(self, prompt: str, user_text: str) -> dict[str, Any]:
        from core.models.budget_model_routing import budget_generate

        raw, model_used = budget_generate(
            prompt,
            user_text=user_text,
            task="wbs",
            format_json=False,
            client=self._llm,
        )
        if not raw.strip():
            raise ValueError("Resposta vazia do Ollama (stream)")
        data = parse_llm_json(raw, require_keys=("etapas",))
        data["llm_model"] = model_used
        data["parser"] = "llm_wbs"
        data["structure_source"] = "llm_wbs"
        self._normalize_etapas(data)
        return data

    def _normalize_etapas(self, data: dict[str, Any]) -> None:
        etapas = data.get("etapas") or []
        for i, etapa in enumerate(etapas, start=1):
            etapa["code"] = str(etapa.get("code") or i)
            services = etapa.get("services") or []
            for j, svc in enumerate(services, start=1):
                svc["code"] = str(svc.get("code") or f"{etapa['code']}.{j:02d}")
                if not svc.get("query"):
                    svc["query"] = svc.get("name") or ""
                if not svc.get("name"):
                    svc["name"] = svc.get("query") or "Serviço"
                qty = svc.get("quantity")
                if qty is not None:
                    try:
                        svc["quantity"] = float(qty)
                    except (TypeError, ValueError):
                        svc["quantity"] = 1.0
        data["etapas"] = etapas
        if not data.get("scope"):
            data["scope"] = data.get("discipline", "geral")

    def _fallback_wbs(self, text: str) -> dict[str, Any]:
        from pricing.orchestrator.intent_parser import IntentParser

        base = IntentParser(llm_client=None)._parse_fallback(text)
        base["structure_source"] = "template_fallback"
        base["parser"] = "regex_fallback"
        etapas = self._template_to_etapas(base)
        if etapas:
            base["etapas"] = etapas
        return base

    def _template_to_etapas(self, intent: dict[str, Any]) -> list[dict[str, Any]]:
        """Converte template passarela/items fallback em etapas para StructureEngine."""
        from pricing.budget.structure_engine import StructureEngine

        try:
            roots = StructureEngine().generate(intent)
        except Exception:
            return []

        etapas: list[dict[str, Any]] = []
        for root in roots:
            services = []
            for child in root.children:
                services.append(
                    {
                        "code": child.code,
                        "name": child.name,
                        "query": child.pricing_query or child.name,
                        "unit": child.unit,
                        "quantity": child.quantity,
                        "calculation_note": child.calculation_note or "",
                    }
                )
            etapas.append(
                {
                    "code": root.code,
                    "name": root.name,
                    "services": services,
                }
            )
        return etapas
