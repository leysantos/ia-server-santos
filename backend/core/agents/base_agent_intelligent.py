import logging
from typing import Optional

from agents.base_agent import BaseAgent
from config import settings
from memory.rag_engine import RAGEngine, get_rag_engine
from models.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

# NBRs de referência por disciplina
DISCIPLINE_NBRS: dict[str, list[str]] = {
    "ARQUITETURA": ["NBR 9050", "NBR 15575"],
    "ESTRUTURAL": ["NBR 6118", "NBR 8681"],
    "HIDROSSANITÁRIO": ["NBR 5626", "NBR 8160"],
    "DRENAGEM": ["NBR 10844", "NBR 9575"],
    "ELÉTRICA": ["NBR 5410", "NBR 14039"],
    "TELECOM": ["NBR 14567", "NBR ISO/IEC 11801"],
    "INCÊNDIO": ["NBR 17240", "NBR 10898"],
    "GEOTECNIA": ["NBR 6122", "NBR 7185"],
    "TRANSPORTES": ["NBR 7188", "NBR 7200"],
    "INFRAESTRUTURA": ["NBR 6118", "NBR 7188"],
    "SANEAMENTO": ["NBR 9649", "NBR 9814"],
    "GEOPROCESSAMENTO": ["ISO 19115", "OGC Standards"],
    "TOPOGRAFIA": ["NBR 13133"],
    "ORÇAMENTO": ["SINAPI", "NBR ISO 12006"],
    "MEIO_AMBIENTE": ["NBR ISO 14001", "Resoluções CONAMA"],
}


class BaseAgentIntelligent(BaseAgent):
    """
    Agente inteligente com pipeline RAG v2 + LLM (Ollama).

    Pipeline handle():
        retrieve_context → build_prompt → call_llm → build_response

    Compatível com BaseAgent — agentes legados continuam inalterados.
    """

    def __init__(
        self,
        name: str,
        discipline: str,
        normas_base: Optional[list[str]] = None,
        rag_engine: Optional[RAGEngine] = None,
        llm_client: Optional[OllamaClient] = None,
        use_rag: bool = True,
    ):
        super().__init__(name=name, discipline=discipline)
        self.normas_base = normas_base or DISCIPLINE_NBRS.get(discipline, [])
        self.rag_engine = rag_engine or get_rag_engine()
        self.llm_client = llm_client or OllamaClient()
        self.use_rag = use_rag
        self._last_model_used: Optional[str] = None
        self._last_prompt_meta: Optional[dict] = None

    def _build_default_prompt(self, text: str, context: str) -> str:
        """Prompt base padrão (sem Learning Loop v2)."""
        normas = ", ".join(self.normas_base) if self.normas_base else "normas ABNT aplicáveis"

        context_block = (
            f"\n\nCONTEXTO NORMATIVO RECUPERADO (RAG v2):\n{context}\n"
            if context
            else "\n\nCONTEXTO NORMATIVO: não disponível no índice. Baseie-se nas NBRs listadas.\n"
        )

        return f"""Você é um engenheiro especialista em {self.discipline} do IA Server Santos.

DISCIPLINA: {self.discipline}
NORMAS DE REFERÊNCIA: {normas}

INSTRUÇÕES:
- Responda em português técnico, claro e estruturado
- Cite NBRs e requisitos normativos quando aplicável
- Organize a resposta em seções: Análise, Premissas, Recomendações, Normas citadas
- Se o usuário pedir tabelas normativas, reproduza-as de forma organizada (markdown)
- Se faltar dado, declare premissas explicitamente
- Não invente valores numéricos sem base normativa ou contexto fornecido
- Priorize segurança, conformidade normativa e boas práticas de engenharia civil

{context_block}
SOLICITAÇÃO DO USUÁRIO:
{text}

RESPOSTA TÉCNICA ESTRUTURADA:"""

    def _try_tuned_prompt(self, text: str, context: str) -> Optional[str]:
        """Tenta carregar prompt versionado do Learning Loop v2."""
        if not settings.USE_TUNED_PROMPTS:
            self._last_prompt_meta = None
            return None

        try:
            from core.learning_v2.prompt_resolver import resolve_tuned_prompt

            resolved = resolve_tuned_prompt(self.discipline, text, context)
        except Exception as exc:
            logger.warning(
                "agent=%s discipline=%s tuned_prompt_error=%s",
                self.name,
                self.discipline,
                exc,
            )
            self._last_prompt_meta = None
            return None

        if not resolved:
            self._last_prompt_meta = None
            return None

        prompt, meta = resolved
        self._last_prompt_meta = meta
        logger.info(
            "agent=%s discipline=%s prompt_key=%s prompt_version=%s",
            self.name,
            self.discipline,
            meta.get("prompt_key"),
            meta.get("prompt_version"),
        )
        return prompt

    def _apply_prompt_meta(self, extra: dict) -> dict:
        if self._last_prompt_meta:
            extra["prompt_tuned"] = self._last_prompt_meta
        return extra

    def retrieve_context(self, text: str) -> str:
        """Recupera contexto normativo via RAG v2 filtrado por disciplina."""
        if not self.use_rag:
            logger.info(
                "agent=%s discipline=%s rag=disabled",
                self.name,
                self.discipline,
            )
            return ""

        try:
            context = self.rag_engine.build_context(
                query=text,
                discipline=self.discipline,
                doc_type="nbr",
            )
        except Exception as exc:
            logger.warning(
                "agent=%s discipline=%s rag_error=%s",
                self.name,
                self.discipline,
                exc,
            )
            return ""

        logger.info(
            "agent=%s discipline=%s context_length=%d rag_chunks=%d",
            self.name,
            self.discipline,
            len(context),
            self.rag_engine.indexed_chunks,
        )
        return context

    def build_prompt(self, text: str, context: str) -> str:
        """Monta prompt técnico — usa versão otimizada se USE_TUNED_PROMPTS=true."""
        tuned = self._try_tuned_prompt(text, context)
        if tuned:
            return tuned
        return self._build_default_prompt(text, context)

    def call_llm(self, prompt: str, text: str = "") -> str:
        """Chama Ollama com roteamento opcional via ModelRouter."""
        from config import settings

        if settings.USE_MODEL_ROUTER or settings.USE_MODEL_EVALUATION:
            from core.models.model_router import get_model_router, routed_generate

            router = get_model_router()
            task_type = router.resolve_engineering_task(
                text or prompt,
                self.discipline,
            )
            result, model_used = routed_generate(
                prompt,
                task_type,
                context={"text": text or prompt, "discipline": self.discipline},
                module="agent",
                discipline=self.discipline,
                client=self.llm_client,
            )
            self._last_model_used = model_used
            return result

        result, model_used = self.llm_client.generate(prompt)
        self._last_model_used = model_used
        logger.info(
            "agent=%s discipline=%s llm_model=%s response_length=%d",
            self.name,
            self.discipline,
            model_used,
            len(result),
        )
        return result

    def handle(
        self,
        text: str,
        context: Optional[str] = None,
        use_rag: Optional[bool] = None,
    ) -> dict:
        """
        Pipeline completo: RAG → prompt → LLM → resposta padronizada.
        use_rag: override por requisição (ex.: chat/orchestrator com use_rag=False).
        """
        rag_enabled = self.use_rag if use_rag is None else use_rag

        if context is not None:
            rag_context = context
        elif rag_enabled:
            rag_context = self.retrieve_context(text)
        else:
            rag_context = ""

        prompt = self.build_prompt(text, rag_context)
        result = self.call_llm(prompt, text=text)

        extra = self.build_extra(self.normas_base, rag_context or None)
        extra["intelligent"] = True
        extra["llm_model"] = self._last_model_used
        extra = self._apply_prompt_meta(extra)

        if rag_context:
            extra.setdefault("rag", {})
            extra["rag"]["active"] = True
            extra["rag"]["context_length"] = len(rag_context)

        return self.build_response(
            input_text=text,
            result=result,
            extra=extra,
        )

    def prepare_prompt(
        self,
        text: str,
        context: Optional[str] = None,
        use_rag: Optional[bool] = None,
    ) -> tuple[str, str, bool]:
        """Monta prompt e retorna (prompt, rag_context, rag_enabled)."""
        rag_enabled = self.use_rag if use_rag is None else use_rag
        if context is not None:
            rag_context = context
        elif rag_enabled:
            rag_context = self.retrieve_context(text)
        else:
            rag_context = ""
        return self.build_prompt(text, rag_context), rag_context, rag_enabled

    def build_stream_response(
        self,
        text: str,
        result: str,
        rag_context: str = "",
    ) -> dict:
        extra = self.build_extra(self.normas_base, rag_context or None)
        extra["intelligent"] = True
        extra["llm_model"] = self._last_model_used
        extra = self._apply_prompt_meta(extra)
        extra["response_source"] = "llm_stream"
        if rag_context:
            extra.setdefault("rag", {})
            extra["rag"]["active"] = True
            extra["rag"]["context_length"] = len(rag_context)
        return self.build_response(input_text=text, result=result, extra=extra)

    def iter_tokens(
        self,
        text: str,
        context: Optional[str] = None,
        use_rag: Optional[bool] = None,
    ):
        """Stream de tokens LLM para resposta técnica."""
        prompt, _, _ = self.prepare_prompt(text, context, use_rag)
        for token, model_used in self.llm_client.generate_stream(prompt):
            self._last_model_used = model_used
            yield token

    def get_specialty_label(self) -> str:
        return self.discipline
