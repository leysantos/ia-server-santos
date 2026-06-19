"""
Configuração central — Pydantic BaseSettings + compatibilidade com imports legados.

Uso:
  from config.settings import DATABASE_URL, USE_MODEL_ROUTER
  from config import settings  # módulo config.settings
  settings.USE_MODEL_ROUTER
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

# Constantes não-ambientais (RAG tuning, limites por agente)
RAG_VERSION = 2
RAG_TOP_K = 5
RAG_TOP_K_MIN = 3
RAG_TOP_K_MAX = 8
RAG_MIN_SCORE = 0.35
RAG_SEARCH_OVERSAMPLE = 10
RAG_CHUNK_MIN_TOKENS = 600
RAG_CHUNK_MAX_TOKENS = 1200
RAG_TARGET_LATENCY_MS = 800
RAG_BOOST_DISCIPLINE = 0.10
RAG_BOOST_DOC_TYPE = 0.05
RAG_BOOST_NBR = 0.15

AGENT_CONTEXT_LIMITS: dict[str, int] = {
    "ARQUITETURA": 3500,
    "ESTRUTURAL": 4500,
    "HIDROSSANITÁRIO": 4000,
    "DRENAGEM": 4000,
    "ELÉTRICA": 4000,
    "TELECOM": 3500,
    "INCÊNDIO": 4000,
    "GEOTECNIA": 4500,
    "TRANSPORTES": 4000,
    "INFRAESTRUTURA": 4500,
    "SANEAMENTO": 4000,
    "GEOPROCESSAMENTO": 3500,
    "TOPOGRAFIA": 3500,
    "ORÇAMENTO": 3000,
    "MEIO_AMBIENTE": 4000,
    "default": 3500,
}


class AppSettings(BaseSettings):
    """Configuração tipada carregada de variáveis de ambiente / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # --- PostgreSQL ---
    db_host: str = Field(default="localhost", validation_alias="DB_HOST")
    db_port: int = Field(default=5433, validation_alias="DB_PORT")
    db_name: str = Field(default="ia_server_santos", validation_alias="DB_NAME")
    db_user: str = Field(default="ia_user", validation_alias="DB_USER")
    db_password: str = Field(default="ia_password", validation_alias="DB_PASSWORD")
    db_enabled: bool = Field(default=True, validation_alias="DB_ENABLED")
    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")

    # --- CORS ---
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"],
        validation_alias="CORS_ALLOWED_ORIGINS",
    )

    # --- Ollama ---
    ollama_base_url: str = Field(
        default="http://localhost:11434", validation_alias="OLLAMA_BASE_URL"
    )
    ollama_embed_model: str = Field(
        default="nomic-embed-text", validation_alias="OLLAMA_EMBED_MODEL"
    )
    ollama_llm_model: str = Field(
        default="qwen2.5-coder:latest", validation_alias="OLLAMA_LLM_MODEL"
    )
    ollama_llm_fallback_model: str = Field(
        default="mistral:7b", validation_alias="OLLAMA_LLM_FALLBACK_MODEL"
    )
    ollama_connect_timeout: int = Field(default=5, validation_alias="OLLAMA_CONNECT_TIMEOUT")
    ollama_budget_model: str = Field(
        default="qwen2.5-coder:latest", validation_alias="OLLAMA_BUDGET_MODEL"
    )
    ollama_budget_timeout: int = Field(default=180, validation_alias="OLLAMA_BUDGET_TIMEOUT")
    ollama_chat_model: str = Field(
        default="qwen2.5-coder:latest", validation_alias="OLLAMA_CHAT_MODEL"
    )
    ollama_chat_timeout: int = Field(default=45, validation_alias="OLLAMA_CHAT_TIMEOUT")
    chat_use_llm: bool = Field(default=True, validation_alias="CHAT_USE_LLM")

    # --- Feature flags ---
    use_intent_layer: bool = Field(default=True, validation_alias="USE_INTENT_LAYER")
    use_intelligent_agents: bool = Field(default=True, validation_alias="USE_INTELLIGENT_AGENTS")
    use_tuned_prompts: bool = Field(default=False, validation_alias="USE_TUNED_PROMPTS")
    use_model_router: bool = Field(default=True, validation_alias="USE_MODEL_ROUTER")
    use_budget_smart_routing: bool = Field(
        default=True, validation_alias="USE_BUDGET_SMART_ROUTING"
    )
    use_engineering_smart_routing: bool = Field(
        default=True, validation_alias="USE_ENGINEERING_SMART_ROUTING"
    )
    use_model_evaluation: bool = Field(default=False, validation_alias="USE_MODEL_EVALUATION")
    use_evolution_loop: bool = Field(default=False, validation_alias="USE_EVOLUTION_LOOP")
    use_safe_rollout: bool = Field(default=True, validation_alias="USE_SAFE_ROLLOUT")
    use_agent_generation: bool = Field(default=False, validation_alias="USE_AGENT_GENERATION")
    use_knowledge_router: bool = Field(default=False, validation_alias="USE_KNOWLEDGE_ROUTER")
    use_discipline_knowledge_router: bool = Field(
        default=False, validation_alias="USE_DISCIPLINE_KNOWLEDGE_ROUTER"
    )
    use_discipline_ingestion: bool = Field(
        default=True, validation_alias="USE_DISCIPLINE_INGESTION"
    )
    use_rag_semantic_cache: bool = Field(
        default=True, validation_alias="USE_RAG_SEMANTIC_CACHE"
    )
    rag_semantic_cache_threshold: float = Field(
        default=0.92, validation_alias="RAG_SEMANTIC_CACHE_THRESHOLD"
    )
    rag_semantic_cache_max_entries: int = Field(
        default=500, validation_alias="RAG_SEMANTIC_CACHE_MAX_ENTRIES"
    )
    use_rag_light_rerank: bool = Field(default=True, validation_alias="USE_RAG_LIGHT_RERANK")
    rag_observability_enabled: bool = Field(
        default=True, validation_alias="RAG_OBSERVABILITY_ENABLED"
    )
    use_agent_scoped_rag: bool = Field(default=True, validation_alias="USE_AGENT_SCOPED_RAG")
    use_engineering_orchestrator: bool = Field(
        default=True, validation_alias="USE_ENGINEERING_ORCHESTRATOR"
    )
    use_nbr_edition_rerank: bool = Field(default=True, validation_alias="USE_NBR_EDITION_RERANK")
    rag_boost_nbr_edition_match: float = Field(
        default=0.35, validation_alias="RAG_BOOST_NBR_EDITION_MATCH"
    )
    rag_boost_nbr_edition_recency: float = Field(
        default=0.004, validation_alias="RAG_BOOST_NBR_EDITION_RECENCY"
    )
    rag_boost_nbr_edition_max: float = Field(
        default=0.15, validation_alias="RAG_BOOST_NBR_EDITION_MAX"
    )
    rag_penalty_nbr_edition_mismatch: float = Field(
        default=0.25, validation_alias="RAG_PENALTY_NBR_EDITION_MISMATCH"
    )

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: Any) -> list[str]:
        if value is None:
            return ["http://localhost:3000", "http://127.0.0.1:3000"]
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",") if part.strip()]
            return parts or ["http://localhost:3000", "http://127.0.0.1:3000"]
        if isinstance(value, list):
            return value
        return ["http://localhost:3000", "http://127.0.0.1:3000"]

    @model_validator(mode="after")
    def _validate_database(self) -> AppSettings:
        if self.db_enabled and not self.resolved_database_url:
            raise ValueError("DATABASE_URL ou credenciais DB_* são obrigatórias quando DB_ENABLED=true")
        return self

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


# Mapeamento UPPER_CASE (legado) → snake_case (Pydantic)
_LEGACY_FIELD_MAP: dict[str, str] = {
    "DATABASE_URL": "resolved_database_url",
    "DB_HOST": "db_host",
    "DB_PORT": "db_port",
    "DB_NAME": "db_name",
    "DB_USER": "db_user",
    "DB_PASSWORD": "db_password",
    "DB_ENABLED": "db_enabled",
    "CORS_ALLOWED_ORIGINS": "cors_allowed_origins",
    "OLLAMA_BASE_URL": "ollama_base_url",
    "OLLAMA_EMBED_MODEL": "ollama_embed_model",
    "OLLAMA_LLM_MODEL": "ollama_llm_model",
    "OLLAMA_LLM_FALLBACK_MODEL": "ollama_llm_fallback_model",
    "OLLAMA_CONNECT_TIMEOUT": "ollama_connect_timeout",
    "OLLAMA_BUDGET_MODEL": "ollama_budget_model",
    "OLLAMA_BUDGET_TIMEOUT": "ollama_budget_timeout",
    "OLLAMA_CHAT_MODEL": "ollama_chat_model",
    "OLLAMA_CHAT_TIMEOUT": "ollama_chat_timeout",
    "CHAT_USE_LLM": "chat_use_llm",
    "USE_INTENT_LAYER": "use_intent_layer",
    "USE_INTELLIGENT_AGENTS": "use_intelligent_agents",
    "USE_TUNED_PROMPTS": "use_tuned_prompts",
    "USE_MODEL_ROUTER": "use_model_router",
    "USE_BUDGET_SMART_ROUTING": "use_budget_smart_routing",
    "USE_ENGINEERING_SMART_ROUTING": "use_engineering_smart_routing",
    "USE_MODEL_EVALUATION": "use_model_evaluation",
    "USE_EVOLUTION_LOOP": "use_evolution_loop",
    "USE_SAFE_ROLLOUT": "use_safe_rollout",
    "USE_AGENT_GENERATION": "use_agent_generation",
    "USE_KNOWLEDGE_ROUTER": "use_knowledge_router",
    "USE_DISCIPLINE_KNOWLEDGE_ROUTER": "use_discipline_knowledge_router",
    "USE_DISCIPLINE_INGESTION": "use_discipline_ingestion",
    "USE_RAG_SEMANTIC_CACHE": "use_rag_semantic_cache",
    "RAG_SEMANTIC_CACHE_THRESHOLD": "rag_semantic_cache_threshold",
    "RAG_SEMANTIC_CACHE_MAX_ENTRIES": "rag_semantic_cache_max_entries",
    "USE_RAG_LIGHT_RERANK": "use_rag_light_rerank",
    "RAG_OBSERVABILITY_ENABLED": "rag_observability_enabled",
    "USE_AGENT_SCOPED_RAG": "use_agent_scoped_rag",
    "USE_ENGINEERING_ORCHESTRATOR": "use_engineering_orchestrator",
    "USE_NBR_EDITION_RERANK": "use_nbr_edition_rerank",
    "RAG_BOOST_NBR_EDITION_MATCH": "rag_boost_nbr_edition_match",
    "RAG_BOOST_NBR_EDITION_RECENCY": "rag_boost_nbr_edition_recency",
    "RAG_BOOST_NBR_EDITION_MAX": "rag_boost_nbr_edition_max",
    "RAG_PENALTY_NBR_EDITION_MISMATCH": "rag_penalty_nbr_edition_mismatch",
}


# --- Paths (derivados de BASE_DIR, não env) ---
DATA_DIR = BASE_DIR / "data"
LEARNING_V2_DIR = DATA_DIR / "learning_v2"
LEARNING_V2_PROFILES_DIR = LEARNING_V2_DIR / "profiles"
LEARNING_V2_PROMPTS_DIR = LEARNING_V2_DIR / "prompts"
EVOLUTION_DATA_DIR = DATA_DIR / "evolution"
AGENT_GENERATION_DATA_DIR = DATA_DIR / "agent_generation"

KNOWLEDGE_DIR = BASE_DIR / "knowledge"
KNOWLEDGE_DOCUMENTS_DIR = KNOWLEDGE_DIR / "raw" / "documents"
KNOWLEDGE_DISCIPLINE_DIR = KNOWLEDGE_DOCUMENTS_DIR
NBR_DIR = KNOWLEDGE_DOCUMENTS_DIR
TDR_DIR = KNOWLEDGE_DOCUMENTS_DIR

FAISS_INDEX_DIR = BASE_DIR / "memory" / "faiss_index"
EMBEDDING_CACHE_PATH = FAISS_INDEX_DIR / "embedding_cache.db"
SEMANTIC_CACHE_PATH = KNOWLEDGE_DIR / "cache" / "semantic_cache.db"
RAG_OBSERVABILITY_LOG_PATH = KNOWLEDGE_DIR / "cache" / "rag_failing_queries.jsonl"


def _export_module_aliases() -> None:
    """Exporta constantes UPPER_CASE no módulo para imports legados e patch em testes."""
    g = globals()
    inner: AppSettings = g["_app_settings"]
    for legacy_name, attr in _LEGACY_FIELD_MAP.items():
        if attr == "resolved_database_url":
            g[legacy_name] = inner.resolved_database_url
        else:
            g[legacy_name] = getattr(inner, attr)


_app_settings = AppSettings()
_export_module_aliases()


def get_settings() -> AppSettings:
    return _app_settings


def reload_settings() -> AppSettings:
    """Recarrega configuração (útil em testes)."""
    global _app_settings
    _app_settings = AppSettings()
    _export_module_aliases()
    return _app_settings
