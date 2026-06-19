from agents.base_agent import BaseAgent


class TransportesAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            name="transportes_agent",
            discipline="TRANSPORTES"
        )

    def handle(self, text: str, context=None):
        return self.build_response(
            input_text=text,
            result=self.build_analysis_result(text, "Análise de transportes", context),
            extra=self.build_extra(["NBR 7188", "NBR 7200"], context),
        )
