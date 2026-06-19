from agents.base_agent import BaseAgent


class EstruturasAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            name="estruturas_agent",
            discipline="ESTRUTURAL"
        )

    def handle(self, text: str, context=None):
        return self.build_response(
            input_text=text,
            result=self.build_analysis_result(text, "Análise estrutural", context),
            extra=self.build_extra(["NBR 6118", "NBR 8681"], context),
        )
