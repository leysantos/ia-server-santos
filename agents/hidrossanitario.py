from agents.base_agent import BaseAgent


class HidrossanitarioAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            name="hidrossanitario_agent",
            discipline="HIDROSSANITÁRIO"
        )

    def handle(self, text: str, context=None):
        return self.build_response(
            input_text=text,
            result=self.build_analysis_result(text, "Análise hidrossanitária", context),
            extra=self.build_extra(["NBR 5626", "NBR 8160"], context),
        )
