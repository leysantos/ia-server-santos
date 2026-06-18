from agents.base_agent import BaseAgent


class ArquiteturaAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            name="arquitetura_agent",
            discipline="ARQUITETURA"
        )

    def handle(self, text: str, context=None):
        return self.build_response(
            input_text=text,
            result=self.build_analysis_result(text, "Análise arquitetônica", context),
            extra=self.build_extra(["NBR 9050", "NBR 15575"], context),
        )
