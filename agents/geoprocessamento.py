from agents.base_agent import BaseAgent


class GeoprocessamentoAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            name="geoprocessamento_agent",
            discipline="GEOPROCESSAMENTO"
        )

    def handle(self, text: str, context=None):
        return self.build_response(
            input_text=text,
            result=self.build_analysis_result(text, "Análise de geoprocessamento", context),
            extra=self.build_extra(["ISO 19115", "OGC Standards"], context),
        )
