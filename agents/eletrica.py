from agents.base_agent import BaseAgent


class EletricaAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            name="eletrica_agent",
            discipline="ELÉTRICA"
        )

    def handle(self, text: str, context=None):
        return self.build_response(
            input_text=text,
            result=self.build_analysis_result(text, "Análise elétrica", context),
            extra=self.build_extra(["NBR 5410", "NBR 14039"], context),
        )
