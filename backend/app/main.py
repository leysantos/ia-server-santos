"""
IA Server Santos — API REST (FastAPI)

Expõe router, dispatcher, orchestrator e RAG v2 como endpoints HTTP.
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routes import aed, auth, chat, console, copilot, devops, feedback, health, history, knowledge, maintenance, models, orchestrator, pricing, project_review, system, system_company, system_network, vision, workflow, workspace
from config.settings import get_settings
from core.auth.middleware import AuthMiddleware
from core.database import init_db, is_db_enabled
from core.system.network_access_store import get_network_access_config

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    from core.auth.security_hardening import run_auth_hardening_check

    run_auth_hardening_check(settings)
    if is_db_enabled():
        init_db()
    yield


app = FastAPI(
    title="IA Server Santos",
    description="API REST de engenharia multidisciplinar com RAG v2",
    version="1.0.0",
    lifespan=lifespan,
)

_cors = list(get_settings().cors_allowed_origins)
_network = get_network_access_config()
for origin in _network.suggested_cors_origins():
    if origin not in _cors:
        _cors.append(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "X-Requested-With",
        "X-Tenant-Id",
    ],
)

app.add_middleware(AuthMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Garante resposta JSON (com CORS) em erros não tratados."""
    logger.exception("Erro não tratado: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc) or "Erro interno do servidor"},
    )


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(system.router)
app.include_router(system_company.router)
app.include_router(system_network.router)
app.include_router(models.router)
app.include_router(chat.router)
app.include_router(aed.router)
app.include_router(copilot.router)
app.include_router(feedback.router)
app.include_router(orchestrator.router)
app.include_router(history.router)
app.include_router(console.router)
app.include_router(workspace.router)
app.include_router(project_review.router)
app.include_router(vision.router)
app.include_router(knowledge.router)
app.include_router(maintenance.router)
app.include_router(devops.router)
app.include_router(pricing.router)
app.include_router(workflow.router)


@app.get("/")
def root():
    return {
        "service": "IA Server Santos",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "chat": "POST /chat",
            "chat_stream": "POST /chat/stream",
            "copilot": "POST /copilot",
            "aed": "POST /aed",
            "feedback": "POST /feedback",
            "orchestrate": "POST /orchestrate",
            "history": "GET /history",
            "projects": "GET/POST /projects",
            "conversations": "GET/PATCH /conversations",
            "health": "GET /health",
            "models_status": "GET /models/status",
            "knowledge_ingest": "POST /knowledge/ingest",
            "knowledge_ingest_web": "POST /knowledge/ingest-web",
            "knowledge_index": "POST /knowledge/index",
            "knowledge_catalog": "GET /knowledge/catalog",
            "knowledge_stats": "GET /knowledge/stats",
            "pricing_resolve": "POST /pricing/resolve",
            "pricing_budget": "POST /pricing/budget/build",
            "pricing_generate": "POST /pricing/budget/generate",
            "pricing_providers": "GET /pricing/providers",
            "pricing_upload": "POST /pricing/providers/{name}/upload",
            "vision_status": "GET /projects/vision/status",
            "vision_workspace_status": "GET /projects/vision/workspace-status",
            "vision_analyze": "POST /projects/{id}/vision/analyze",
            "vision_analyze_stream": "POST /projects/{id}/vision/analyze/stream",
            "vision_report": "POST /projects/{id}/vision/report",
            "project_file_preview": "GET /projects/{id}/files/{file_id}/preview",
        },
    }
