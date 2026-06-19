"""
Prompt Builder — gera prompt técnico especializado para engenharia estrutural.
"""

from __future__ import annotations

from typing import Any, Optional


class PromptBuilder:
    _SYSTEM_LABELS = {
        "CONCRETE_ARMED": "Concreto Armado",
        "CONCRETE_PRESTRESSED": "Concreto Protendido",
        "PRECAST_CONCRETE": "Concreto Pré-moldado",
        "STEEL_STRUCTURE": "Estrutura Metálica",
        "TIMBER_STRUCTURE": "Estrutura de Madeira",
        "MIXED_SYSTEMS": "Sistemas Mistas / Híbridos",
    }

    def build(
        self,
        context: dict[str, Any],
        user_input: str,
        *,
        rag_context: Optional[str] = None,
    ) -> str:
        system = context.get("system", "CONCRETE_ARMED")
        subsystem = context.get("subsystem")
        norms = context.get("norms") or []
        complexity = context.get("complexity", "LOW")
        span = context.get("span_estimate")
        confidence = context.get("confidence", 0.0)

        label = self._SYSTEM_LABELS.get(system, system)
        normas_str = ", ".join(norms) if norms else "normas ABNT aplicáveis"
        subsystem_line = f"\nSUBSISTEMA: {subsystem}" if subsystem else ""
        span_line = f"\nVÃO ESTIMADO: {span} m" if span is not None else ""

        rag_block = ""
        if rag_context:
            rag_block = f"\n\nCONTEXTO NORMATIVO RECUPERADO (RAG v2):\n{rag_context}\n"
        else:
            rag_block = (
                "\n\nCONTEXTO NORMATIVO: índice RAG indisponível ou vazio. "
                "Baseie-se nas NBRs listadas e boas práticas.\n"
            )

        return f"""Você é um engenheiro estrutural sênior do IA Server Santos (SIE v1).

DISCIPLINA: ESTRUTURAL
SISTEMA ESTRUTURAL IDENTIFICADO: {label} ({system}){subsystem_line}
COMPLEXIDADE: {complexity}
CONFIANÇA DA CLASSIFICAÇÃO: {confidence:.0%}{span_line}
NORMAS APLICÁVEIS: {normas_str}

INSTRUÇÕES TÉCNICAS:
- Responda em português técnico, claro e estruturado
- Aplique exclusivamente as normas listadas para o sistema identificado
- Organize em: Análise estrutural, Premissas, Dimensionamento/Recomendações, Normas citadas, Riscos
- Para estruturas metálicas: verifique estabilidade, ligações e ações de vento (NBR 6123)
- Para concreto armado: estados limites, durabilidade e agressividade ambiental (NBR 6118)
- Para madeira: umidade, classe de serviço e ligações (NBR 7190)
- Declare premissas quando faltarem dados (cargas, apoios, geometria)
- Não invente coeficientes ou tabelas sem base normativa ou contexto RAG
- Priorize segurança, conformidade normativa e executabilidade de obra

{rag_block}
SOLICITAÇÃO DO USUÁRIO:
{user_input}

RESPOSTA TÉCNICA ESTRUTURADA:"""
