"""
IA Server Santos — API REST (FastAPI)

Expõe router, dispatcher, orchestrator e RAG v2 como endpoints HTTP.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import aed, chat, console, copilot, feedback, health, history, knowledge, models, orchestrator, pricing, project_review, system, vision, workspace
from config.settings import get_settings
from core.database import init_db, is_db_enabled


@asynccontextmanager
async def lifespan(app: FastAPI):
    if is_db_enabled():
        init_db()
    yield


app = FastAPI(
    title="IA Server Santos",
    description="API REST de engenharia multidisciplinar com RAG v2",
    version="1.0.0",
    lifespan=lifespan,
)

_cors = get_settings().cors_allowed_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)

app.include_router(health.router)
app.include_router(system.router)
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
app.include_router(pricing.router)


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
