from core.aed.aed_orchestrator import run_aed


class AedService:
    """Expõe AED v1 como serviço de API."""

    def process(
        self,
        text: str,
        use_rag: bool = True,
        persist: bool = False,
    ) -> dict:
        result = run_aed(text=text, use_rag=use_rag, persist=persist)
        return result
