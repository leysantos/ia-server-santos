from agents.base_agent import BaseAgent


class TelecomAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            name="telecom_agent",
            discipline="TELECOM"
        )

    def handle(self, text: str, context=None):
        return self.build_response(
            input_text=text,
            result=self.build_analysis_result(text, "Análise de telecomunicações", context),
            extra=self.build_extra(["NBR 14567", "NBR ISO/IEC 11801"], context),
        )
