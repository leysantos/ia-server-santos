from agents.base_agent import BaseAgent


class OrcamentoAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            name="orcamento_agent",
            discipline="ORÇAMENTO"
        )

    def handle(self, text: str, context=None):
        return self.build_response(
            input_text=text,
            result=self.build_analysis_result(text, "Análise de orçamento", context),
            extra=self.build_extra(["SINAPI", "NBR ISO 12006"], context),
        )
