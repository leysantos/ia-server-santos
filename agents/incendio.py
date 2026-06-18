from agents.base_agent import BaseAgent


class IncendioAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            name="incendio_agent",
            discipline="INCÊNDIO"
        )

    def handle(self, text: str, context=None):
        return self.build_response(
            input_text=text,
            result=self.build_analysis_result(text, "Análise de combate a incêndio", context),
            extra=self.build_extra(["NBR 17240", "NBR 10898"], context),
        )
