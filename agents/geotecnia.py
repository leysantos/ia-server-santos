from agents.base_agent import BaseAgent


class GeotecniaAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            name="geotecnia_agent",
            discipline="GEOTECNIA"
        )

    def handle(self, text: str, context=None):
        return self.build_response(
            input_text=text,
            result=self.build_analysis_result(text, "Análise geotécnica", context),
            extra=self.build_extra(["NBR 6122", "NBR 7185"], context),
        )
