from fastapi import APIRouter

from app.schemas import HealthResponse
from app.services import HealthService

router = APIRouter(tags=["Health"])
health_service = HealthService()


@router.get("/health", response_model=HealthResponse)
def health():
    """Status do sistema: banco, RAG v2 e Ollama."""
    return HealthResponse(**health_service.check())
