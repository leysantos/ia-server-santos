"""
IA Server Santos — API REST (FastAPI)

Expõe router, dispatcher, orchestrator e RAG v2 como endpoints HTTP.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import chat, health, history, orchestrator
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(orchestrator.router)
app.include_router(history.router)


@app.get("/")
def root():
    return {
        "service": "IA Server Santos",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "chat": "POST /chat",
            "orchestrate": "POST /orchestrate",
            "history": "GET /history",
            "health": "GET /health",
        },
    }
