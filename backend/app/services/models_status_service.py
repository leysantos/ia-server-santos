from app.services.ollama_models import fetch_installed_models
from config.settings import OLLAMA_BASE_URL
from core.models.model_performance_service import list_performance_profiles
from core.models.model_router import get_model_router


class ModelsStatusService:
    """Status de modelos LLM e roteamento."""

    def check(self) -> dict:
        installed = fetch_installed_models()
        status = get_model_router().get_status(installed_models=installed)
        status["ollama"] = "reachable" if installed is not None else "unreachable"
        status["performance_profiles"] = list_performance_profiles(limit=30)
        return status
