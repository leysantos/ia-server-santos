from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.schemas import ChatRequest, ChatResponse
from app.services import ChatService
from app.services.chat_stream_service import ChatStreamService
from core.auth.dependencies import get_current_user
from core.chat.chat_attachment_service import (
    MAX_FILES,
    prepare_uploaded_file,
    purge_stale_attachments,
    save_prepared_attachment,
)
from core.chat.chat_attachment_routing import resolve_auto_llm_model_for_attachments
from core.database.models import User
from core.llm_override import llm_model_scope, normalize_llm_model_choice

router = APIRouter(prefix="/chat", tags=["Chat"])
chat_service = ChatService()
chat_stream_service = ChatStreamService()


@router.post("/attachments")
async def upload_chat_attachments(
    files: list[UploadFile] = File(...),
    user: User | None = Depends(get_current_user),
):
    """Prepara anexos para o chat — extrai texto / visão e retorna IDs."""
    del user  # reservado para quota por usuário
    if not files:
        raise HTTPException(status_code=400, detail="Envie ao menos um arquivo")
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Máximo de {MAX_FILES} arquivos por envio")

    purge_stale_attachments()
    prepared = []
    paths = []
    for upload in files[:MAX_FILES]:
        raw = await upload.read()
        if not raw:
            continue
        item = prepare_uploaded_file(upload.filename or "anexo", raw)
        if item.path:
            paths.append(item.path)
        prepared.append(item)

    if not prepared:
        raise HTTPException(status_code=400, detail="Nenhum arquivo válido recebido")

    try:
        from models.ollama_client import OllamaClient

        installed = set(OllamaClient().list_models() or [])
    except Exception:
        installed = set()

    batch_hint = resolve_auto_llm_model_for_attachments(paths, installed_models=installed)
    items = [save_prepared_attachment(p, model_hint=batch_hint).to_dict() for p in prepared]
    return {"items": items, "model_hint": batch_hint}


@router.post("", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    user: User | None = Depends(get_current_user),
):
    """
    Chat single-domain: router → RAG v2 (opcional) → dispatcher.
    """
    with llm_model_scope(request.llm_model):
        result = chat_service.process(
            text=request.text,
            use_rag=request.use_rag,
            persist=request.persist,
            conversation_id=request.conversation_id,
            project_id=request.project_id,
            user=user,
        )
    return ChatResponse(**result)


@router.post("/stream")
def chat_stream(
    request: ChatRequest,
    user: User | None = Depends(get_current_user),
):
    """
    Chat com streaming SSE — tokens em tempo real + status dos agentes/modelos.
    """
    if not request.text.strip() and not request.attachment_ids:
        raise HTTPException(status_code=400, detail="Informe texto ou anexos")

    def event_stream():
        # Não usar llm_model_scope aqui — ContextVar quebra no thread pool do SSE.
        yield from chat_stream_service.stream(
            text=request.text,
            use_rag=request.use_rag,
            persist=request.persist,
            conversation_id=request.conversation_id,
            project_id=request.project_id,
            llm_model=normalize_llm_model_choice(request.llm_model),
            attachment_ids=request.attachment_ids,
            user=user,
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )
