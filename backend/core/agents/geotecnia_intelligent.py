"""Agente de geotecnia com prompt orientado a decisão técnica em fundações."""

from core.agent_registry import get_agent_name
from core.agents.base_agent_intelligent import BaseAgentIntelligent
from core.agents.discipline_prompts import GEOTECNIA_INSTRUCTIONS


class GeotecniaIntelligentAgent(BaseAgentIntelligent):
    """
    Agente geotécnico — RAG v2 + LLM com instruções para:
    - solução recomendada objetiva
    - cálculo A_min = P/σ_adm
    - classificação correta do solo
    - recalque (NBR 6122) e normas aplicáveis
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("name", get_agent_name("GEOTECNIA"))
        kwargs.setdefault("discipline", "GEOTECNIA")
        kwargs.setdefault("normas_base", ["NBR 6122", "NBR 7185"])
        super().__init__(**kwargs)

    def _build_default_prompt(self, text: str, context: str) -> str:
        normas = ", ".join(self.normas_base) if self.normas_base else "NBR 6122, NBR 7185"

        context_block = (
            f"\n\nCONTEXTO NORMATIVO RECUPERADO (RAG v2):\n{context}\n"
            if context
            else "\n\nCONTEXTO NORMATIVO: não disponível no índice. Baseie-se nas NBRs listadas.\n"
        )

        return f"""Você é um engenheiro geotécnico especialista do IA Server Santos.

DISCIPLINA: GEOTECNIA
NORMAS DE REFERÊNCIA: {normas}

INSTRUÇÕES GERAIS:
- Responda em português técnico, claro e objetivo
- Priorize uma recomendação principal antes de alternativas
- Cite itens normativos quando o contexto RAG ou o enunciado permitirem
- Se faltar dado, declare premissas e liste perguntas em aberto no final
- Não invente parâmetros de solo sem base; cálculos com dados do usuário são esperados

{GEOTECNIA_INSTRUCTIONS}
{context_block}
SOLICITAÇÃO DO USUÁRIO:
{text}

RESPOSTA TÉCNICA ESTRUTURADA:"""

    def _discipline_extra_instructions(self, text: str) -> str:
        """Instruções já embutidas no prompt geotécnico dedicado."""
        return ""
