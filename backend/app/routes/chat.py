from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas import ChatRequest, ChatResponse
from app.services import ChatService
from app.services.chat_stream_service import ChatStreamService

router = APIRouter(prefix="/chat", tags=["Chat"])
chat_service = ChatService()
chat_stream_service = ChatStreamService()


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Chat single-domain: router → RAG v2 (opcional) → dispatcher.
    """
    result = chat_service.process(
        text=request.text,
        use_rag=request.use_rag,
        persist=request.persist,
        conversation_id=request.conversation_id,
        project_id=request.project_id,
    )
    return ChatResponse(**result)


@router.post("/stream")
def chat_stream(request: ChatRequest):
    """
    Chat com streaming SSE — tokens em tempo real + status dos agentes/modelos.
    """
    return StreamingResponse(
        chat_stream_service.stream(
            text=request.text,
            use_rag=request.use_rag,
            persist=request.persist,
            conversation_id=request.conversation_id,
            project_id=request.project_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )
