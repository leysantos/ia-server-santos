from abc import ABC, abstractmethod
from typing import Optional


class BaseAgent(ABC):
    """
    Classe base para todos os agentes de engenharia do IA Server Santos
    """

    def __init__(self, name: str, discipline: str):
        self.name = name
        self.discipline = discipline

    @abstractmethod
    def handle(self, text: str, context: Optional[str] = None) -> dict:
        """
        Método obrigatório para todos os agentes.
        context: trechos recuperados pelo RAG (opcional).
        """
        pass

    def build_response(self, input_text: str, result: str, extra: dict = None):
        """
        Padroniza a saída de todos os agentes
        """

        response = {
            "agent": self.name,
            "discipline": self.discipline,
            "input": input_text,
            "result": result
        }

        if extra:
            response["extra"] = extra

        return response

    def build_analysis_result(
        self,
        text: str,
        analysis_label: str,
        context: Optional[str] = None,
    ) -> str:
        result = f"{analysis_label} simulada para: {text}"
        if context:
            result += f"\n\n[Contexto normativo recuperado]\n{context}"
        return result

    def build_extra(
        self,
        normas_base: list[str],
        context: Optional[str] = None,
    ) -> dict:
        extra = {"normas_base": normas_base}
        if context:
            extra["rag"] = {
                "active": True,
                "context_length": len(context),
            }
        return extra
