from agents.base_agent import BaseAgent


class SaneamentoAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            name="saneamento_agent",
            discipline="SANEAMENTO"
        )

    def handle(self, text: str, context=None):
        return self.build_response(
            input_text=text,
            result=self.build_analysis_result(text, "Análise de saneamento", context),
            extra=self.build_extra(["NBR 9649", "NBR 9814"], context),
        )
