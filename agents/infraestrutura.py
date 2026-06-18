from agents.base_agent import BaseAgent


class InfraestruturaAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            name="infraestrutura_agent",
            discipline="INFRAESTRUTURA"
        )

    def handle(self, text: str, context=None):
        return self.build_response(
            input_text=text,
            result=self.build_analysis_result(text, "Análise de infraestrutura", context),
            extra=self.build_extra(["NBR 6118", "NBR 7188"], context),
        )
