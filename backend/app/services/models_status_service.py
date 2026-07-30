from app.services.ollama_models import fetch_installed_models
from config.settings import OLLAMA_BASE_URL
from core.llm_override import list_cloud_llm_models
from core.models.model_performance_service import list_performance_profiles
from core.models.model_router import get_model_router


class ModelsStatusService:
    """Status de modelos LLM e roteamento."""

    def check(self) -> dict:
        installed = fetch_installed_models()
        cloud = list_cloud_llm_models()
        # Seletor UI: cloud (Gemini) + Ollama local
        selectable = list(cloud)
        if installed:
            for name in installed:
                if name not in selectable:
                    selectable.append(name)
        status = get_model_router().get_status(installed_models=selectable)
        status["installed_models"] = selectable
        status["cloud_models"] = cloud
        status["local_models"] = list(installed or [])
        status["ollama"] = "reachable" if installed is not None else "unreachable"
        status["gemini_available"] = bool(cloud)
        status["performance_profiles"] = list_performance_profiles(limit=30)
        status["ollama_base_url"] = OLLAMA_BASE_URL
        return status
