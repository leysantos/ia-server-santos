from agents.base_agent import BaseAgent


class MeioAmbienteAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            name="meio_ambiente_agent",
            discipline="MEIO_AMBIENTE"
        )

    def handle(self, text: str, context=None):
        return self.build_response(
            input_text=text,
            result=self.build_analysis_result(text, "Análise de meio ambiente", context),
            extra=self.build_extra(["NBR ISO 14001", "Resoluções CONAMA"], context),
        )
