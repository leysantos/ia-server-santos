from core.orchestrator import process_multi_domain_request


class OrchestratorService:
    """Expõe orchestrator v1 como serviço de API."""

    def process(
        self,
        text: str,
        use_rag: bool = True,
        persist: bool = True,
    ) -> dict:
        return process_multi_domain_request(
            text=text,
            use_rag=use_rag,
            persist=persist,
        )
