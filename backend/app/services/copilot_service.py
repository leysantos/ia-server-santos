from core.copilot.copilot_engine import run_copilot


class CopilotService:
    """Expõe Copilot v1 como serviço de API."""

    def process(
        self,
        text: str,
        use_rag: bool = True,
        persist: bool = False,
    ) -> dict:
        return run_copilot(
            text=text,
            use_rag=use_rag,
            persist=persist,
        )
