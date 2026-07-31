from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse

from app.schemas import ChatRequest, ChatResponse
from app.schemas.chat import ChatCroquiRequest, ChatExportRequest, ChatSuggestDocumentsRequest
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
from core.chat.document_export import build_chat_document
from core.chat.document_suggestions import suggest_chat_documents
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


@router.post("/export/suggestions")
def chat_export_suggestions(
    request: ChatSuggestDocumentsRequest,
    user: User | None = Depends(get_current_user),
):
    """Sugere tipos de documento (PDF/Word/croqui) conforme o conteúdo da resposta."""
    del user
    items = suggest_chat_documents(
        request.text,
        discipline=request.discipline,
        source_question=request.source_question,
        route_mode=request.route_mode,
    )
    return {"suggestions": [s.to_dict() for s in items]}


@router.post("/export")
def chat_export_document(
    request: ChatExportRequest,
    user: User | None = Depends(get_current_user),
):
    """Gera PDF/DOCX a partir do texto do chat (tipo dinâmico: memória, TRD, parecer…)."""
    del user
    try:
        data, media_type, filename = build_chat_document(
            kind=request.kind,
            fmt=request.format,
            text=request.text,
            title=request.title,
            discipline=request.discipline,
            source_question=request.source_question,
        )
    except Exception as exc:
        raise HTTPException(500, detail=f"Falha ao gerar documento: {exc}") from exc
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/croqui")
def chat_generate_croqui(
    request: ChatCroquiRequest,
    user: User | None = Depends(get_current_user),
):
    """Gera croqui estrutural (determinístico para viga CA; Gemini como fallback)."""
    del user
    from core.chat.structural_croqui import try_build_structural_croqui
    from core.inspection_report.gemini_client import (
        gemini_available,
        generate_engineering_sketch,
    )

    # 1) Croqui determinístico (prancha) — prioridade para vigas CA
    built = try_build_structural_croqui(request.text, request.source_question)
    if built:
        image_bytes, mime = built
        ext = "png" if "png" in mime else "jpg"
        return Response(
            content=image_bytes,
            media_type=mime,
            headers={"Content-Disposition": f'attachment; filename="croqui_viga.{ext}"'},
        )

    # 2) Fallback Gemini (outros elementos / quando não parseia)
    if not gemini_available():
        raise HTTPException(
            422,
            detail=(
                "Não foi possível montar croqui estrutural automático para este texto. "
                "Para croqui via Gemini, configure GEMINI_API_KEY "
                "(ou descreva uma viga biapoiada com seção, vão e armaduras)."
            ),
        )

    prompt_bits = [
        "Desenho técnico estrutural brasileiro (prancha NBR 6118), preto e branco, "
        "fundo branco, linhas limpas, cotas corretas, SEM artefatos, SEM ícones decorativos, "
        "SEM números inventados. Incluir: elevação da viga biapoiada, seção transversal  "
        "com estribo e bitolas, e tabela de aço com colunas Pos./Função/φ/Qtd./Comp./Aço/Peso.",
    ]
    if request.source_question:
        prompt_bits.append(f"Pergunta: {request.source_question.strip()[:800]}")
    prompt_bits.append(f"Solução técnica:\n{request.text.strip()[:6000]}")
    prompt = "\n\n".join(prompt_bits)

    try:
        image_bytes, mime = generate_engineering_sketch(prompt)
    except Exception as exc:
        raise HTTPException(500, detail=f"Falha ao gerar croqui: {exc}") from exc

    ext = "png" if "png" in mime else "jpg" if "jpeg" in mime or "jpg" in mime else "bin"
    filename = f"croqui_chat.{ext}"
    return Response(
        content=image_bytes,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
