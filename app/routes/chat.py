from fastapi import APIRouter

from app.schemas import ChatRequest, ChatResponse
from app.services import ChatService

router = APIRouter(prefix="/chat", tags=["Chat"])
chat_service = ChatService()


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Chat single-domain: router → RAG v2 (opcional) → dispatcher.
    """
    result = chat_service.process(
        text=request.text,
        use_rag=request.use_rag,
        persist=request.persist,
    )
    return ChatResponse(**result)
