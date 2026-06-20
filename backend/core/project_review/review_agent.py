"""ProjectReviewAgent — agente principal de revisão (Módulo G)."""

from __future__ import annotations

import json
import logging
from typing import Any

from core.project_review.constants import TECHNICAL_MODEL, TECHNICAL_MODEL_FALLBACK
from core.project_review.rag_bridge import retrieve_normative_context
from core.project_review.vision_analysis_service import extract_analysis

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Você é o ProjectReviewAgent — engenheiro civil sênior auditor de projetos.
Analise documentos, extractions e digital twin. Identifique:
- inconsistências
- omissões
- divergências
- conflitos entre disciplinas
- riscos
- documentos faltantes
- incompatibilidades normativas

Responda APENAS JSON válido:
{
  "resumo": "",
  "inconsistencias": [{"descricao": "", "disciplina": "", "criticidade": "baixa|media|alta|critica"}],
  "omissoes": [{"descricao": "", "documento_esperado": ""}],
  "divergencias": [{"descricao": "", "evidencia": ""}],
  "conflitos": [{"disciplinas": [], "descricao": ""}],
  "riscos": [{"descricao": "", "impacto": ""}],
  "documentos_faltantes": [],
  "incompatibilidades": [{"norma": "", "descricao": ""}],
  "nao_conformidades": [{
    "codigo": "NC-001",
    "categoria": "documental|estrutural|arquitetonica|hidraulica|eletrica|pci|orcamentaria",
    "criticidade": "baixa|media|alta|critica",
    "descricao": "",
    "evidencia": "",
    "norma": "",
    "impacto": "",
    "recomendacao": ""
  }],
  "recomendacoes": [{"prioridade": "alta|media|baixa", "texto": ""}]
}"""


class ProjectReviewAgent:
    """Agente de revisão técnica integrado ao Ollama."""

    def analyze(
        self,
        *,
        project_name: str,
        twin_payload: dict[str, Any],
        extractions: list[dict[str, Any]],
        discipline: str | None = None,
    ) -> dict[str, Any]:
        context = self._build_context(project_name, twin_payload, extractions)
        norm_hits = retrieve_normative_context(
            f"Revisão projeto {project_name} disciplina {discipline or 'multidisciplinar'}",
            discipline=discipline,
        )
        norm_text = json.dumps(norm_hits[:6], ensure_ascii=False, indent=2)

        prompt = (
            f"{_SYSTEM_PROMPT}\n\n"
            f"## Projeto: {project_name}\n\n"
            f"## Digital Twin\n{json.dumps(twin_payload, ensure_ascii=False)[:8000]}\n\n"
            f"## Extrações\n{context[:12000]}\n\n"
            f"## Normas aplicáveis (RAG)\n{norm_text}\n"
        )

        try:
            from models.ollama_client import OllamaClient

            client = OllamaClient(timeout=120)
            raw, model = client.generate(
                prompt,
                model=TECHNICAL_MODEL,
                fallback_models=[TECHNICAL_MODEL_FALLBACK],
                format_json=True,
            )
            parsed = self._parse_json(raw)
            parsed["model"] = model
            parsed["normas_consultadas"] = norm_hits
            return parsed
        except Exception as exc:
            logger.error("ProjectReviewAgent falhou: %s", exc)
            return self._heuristic_fallback(extractions, str(exc))

    def _build_context(
        self,
        project_name: str,
        twin: dict[str, Any],
        extractions: list[dict[str, Any]],
    ) -> str:
        parts: list[str] = [f"Projeto: {project_name}"]
        for item in extractions[:20]:
            ext = item.get("extraction_json") or {}
            vis = extract_analysis(item.get("vision_json"))
            parts.append(
                f"\n### {item.get('filename')} [{item.get('discipline')}]\n"
                f"Texto: {(ext.get('texto') or '')[:1500]}\n"
                f"Elementos: {ext.get('elementos_detectados') or vis.get('elementos_detectados')}\n"
                f"Vision NCs: {vis.get('nao_conformidades')}\n"
                f"Resumo visão: {vis.get('resumo_tecnico') or vis.get('legenda_relatorio') or ''}\n"
            )
        return "\n".join(parts)

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)

    @staticmethod
    def _heuristic_fallback(extractions: list[dict[str, Any]], error: str) -> dict[str, Any]:
        ncs = []
        for i, item in enumerate(extractions, start=1):
            vis = extract_analysis(item.get("vision_json"))
            for nc in vis.get("nao_conformidades") or []:
                ncs.append(
                    {
                        "codigo": f"NC-{i:03d}",
                        "categoria": item.get("discipline", "documental"),
                        "criticidade": "media",
                        "descricao": str(nc),
                        "evidencia": item.get("filename"),
                        "norma": "",
                        "impacto": "",
                        "recomendacao": "Revisar documento",
                    }
                )
        return {
            "resumo": "Análise heurística (LLM indisponível)",
            "inconsistencias": [],
            "omissoes": [],
            "divergencias": [],
            "conflitos": [],
            "riscos": [],
            "documentos_faltantes": [],
            "incompatibilidades": [],
            "nao_conformidades": ncs,
            "recomendacoes": [{"prioridade": "alta", "texto": f"Verificar Ollama: {error}"}],
            "model": "heuristic",
        }
