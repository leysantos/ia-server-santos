from agents.base_agent import BaseAgent


class DrenagemAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            name="drenagem_agent",
            discipline="DRENAGEM"
        )

    def handle(self, text: str, context=None):
        return self.build_response(
            input_text=text,
            result=self.build_analysis_result(text, "Análise de drenagem", context),
            extra=self.build_extra(["NBR 10844", "NBR 9575"], context),
        )
