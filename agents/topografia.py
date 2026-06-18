from agents.base_agent import BaseAgent


class TopografiaAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            name="topografia_agent",
            discipline="TOPOGRAFIA"
        )

    def handle(self, text: str, context=None):
        return self.build_response(
            input_text=text,
            result=self.build_analysis_result(text, "Análise topográfica", context),
            extra=self.build_extra(["NBR 13133"], context),
        )
