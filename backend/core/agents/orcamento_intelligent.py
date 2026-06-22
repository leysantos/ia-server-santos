"""Agente de orçamento com ferramentas determinísticas de consulta ao price_bank."""

from __future__ import annotations

import logging
from typing import Optional

from core.agent_registry import get_agent_name
from core.agents.base_agent_intelligent import BaseAgentIntelligent
from pricing.orchestrator.budget_knowledge import fetch_budget_generation_context
from pricing.tools.budget_pricing_tools import fetch_pricing_context_for_agent

logger = logging.getLogger(__name__)

ORCAMENTO_INSTRUCTIONS = """
INSTRUÇÕES — ORÇAMENTO / SINAPI:

Quando houver bloco **DADOS OFICIAIS DO BANCO DE PREÇOS** no contexto:
- Reproduza os valores ComD e SemD EXATAMENTE como fornecidos (não arredonde diferente, não invente)
- Apresente a CPU em tabela markdown com colunas ComD e SemD
- Cite UF e período (mês/ano) usados na consulta
- O total sintético (aba fechada) pode diferir levemente da soma analítica — mencione ambos se relevante

Quando NÃO houver dados oficiais no contexto:
- Não invente códigos SINAPI nem preços
- Oriente o usuário a importar a base em Configurações → Bases de preços
- Sugira informar código da composição, UF e período (ex.: 95995, AM, 05/2026)

Estrutura sugerida da resposta:
1. **Resumo** — código, descrição, UF, período
2. **Totais** — ComD e SemD (sintético e analítico se disponível)
3. **CPU** — tabela de insumos/MO/equipamentos
4. **Observações** — premissas (desoneração, referência mensal)
"""


class OrcamentoIntelligentAgent(BaseAgentIntelligent):
    """
    Agente ORÇAMENTO — consulta price_bank via BudgetPricingTools antes do LLM.

    Evita alucinação de preços: números vêm do banco estruturado, não do RAG normativo.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("name", get_agent_name("ORÇAMENTO"))
        kwargs.setdefault("discipline", "ORÇAMENTO")
        kwargs.setdefault("normas_base", ["SINAPI", "NBR ISO 12006"])
        super().__init__(**kwargs)
        self._last_pricing_tools: list[dict] = []

    def retrieve_context(self, text: str) -> str:
        blocks: list[str] = []

        pricing_ctx, tool_calls = fetch_pricing_context_for_agent(text)
        self._last_pricing_tools = tool_calls
        if pricing_ctx:
            blocks.append(pricing_ctx)
            logger.info(
                "agent=orcamento pricing_tools=%s context_len=%d",
                [c.get("tool") for c in tool_calls],
                len(pricing_ctx),
            )

        try:
            model_ctx, _refs = fetch_budget_generation_context(text, top_k=2)
            if model_ctx:
                blocks.append(model_ctx)
        except Exception as exc:
            logger.debug("orcamento budget_models_rag skipped: %s", exc)

        return "\n\n".join(blocks)

    def _build_default_prompt(self, text: str, context: str) -> str:
        normas = ", ".join(self.normas_base) if self.normas_base else "SINAPI"

        context_block = (
            f"\n\nCONTEXTO RECUPERADO (bases de preço + modelos):\n{context}\n"
            if context
            else "\n\nCONTEXTO: nenhuma consulta ao banco de preços ou modelo retornou dados.\n"
        )

        return f"""Você é um engenheiro orçamentista especialista do IA Server Santos.

DISCIPLINA: ORÇAMENTO
REFERÊNCIAS: {normas}

INSTRUÇÕES GERAIS:
- Responda em português técnico, claro e estruturado
- Priorize dados do banco de preços oficial quando presentes no contexto
- Organize em seções com markdown (tabelas para CPUs)
- Não invente códigos nem valores unitários sem base no contexto

{ORCAMENTO_INSTRUCTIONS}
{context_block}
SOLICITAÇÃO DO USUÁRIO:
{text}

RESPOSTA TÉCNICA ESTRUTURADA:"""

    def _discipline_extra_instructions(self, text: str) -> str:
        return ""

    def handle(
        self,
        text: str,
        context: Optional[str] = None,
        use_rag: Optional[bool] = None,
    ) -> dict:
        response = super().handle(text, context=context, use_rag=use_rag)
        if self._last_pricing_tools:
            extra = response.get("extra") or {}
            extra["pricing_tools"] = self._last_pricing_tools
            response["extra"] = extra
        return response

    def build_stream_response(self, text: str, result: str, rag_context: str = "") -> dict:
        response = super().build_stream_response(text, result, rag_context)
        if self._last_pricing_tools:
            extra = response.get("extra") or {}
            extra["pricing_tools"] = self._last_pricing_tools
            response["extra"] = extra
        return response

    def prepare_prompt(
        self,
        text: str,
        context: Optional[str] = None,
        use_rag: Optional[bool] = None,
    ) -> tuple[str, str, bool]:
        rag_enabled = self.use_rag if use_rag is None else use_rag
        if context is not None:
            rag_context = context
        elif rag_enabled:
            rag_context = self.retrieve_context(text)
        else:
            rag_context = ""
        return self.build_prompt(text, rag_context), rag_context, rag_enabled
