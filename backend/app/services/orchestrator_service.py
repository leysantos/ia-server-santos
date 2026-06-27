from typing import Optional

from core.database.conversation_access import conversation_user_id
from core.database.models import User
from core.orchestrator import process_multi_domain_request


class OrchestratorService:
    """Expõe orchestrator v1 como serviço de API."""

    def process(
        self,
        text: str,
        use_rag: bool = True,
        persist: bool = True,
        user: Optional[User] = None,
    ) -> dict:
        return process_multi_domain_request(
            text=text,
            use_rag=use_rag,
            persist=persist,
            user_id=conversation_user_id(user),
        )
