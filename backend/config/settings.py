from pathlib import Path

import os

BASE_DIR = Path(__file__).resolve().parent.parent

# Ollama
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_EMBED_MODEL = "nomic-embed-text"
OLLAMA_LLM_MODEL = "qwen3:14b"
OLLAMA_LLM_FALLBACK_MODEL = "qwen3-coder"
# Modelo leve para chat conversacional (sem RAG)
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "qwen3:8b")
OLLAMA_CHAT_TIMEOUT = int(os.getenv("OLLAMA_CHAT_TIMEOUT", "45"))
CHAT_USE_LLM = os.getenv("CHAT_USE_LLM", "true").lower() == "true"

# Intent Layer v2 — decisão central chat vs engenharia vs mixed
USE_INTENT_LAYER = os.getenv("USE_INTENT_LAYER", "true").lower() == "true"

# Agentes: true = RAG v2 + LLM (BaseAgentIntelligent), false = simulados (BaseAgent)
USE_INTELLIGENT_AGENTS = os.getenv("USE_INTELLIGENT_AGENTS", "true").lower() == "true"

# Learning Loop v2 — usar prompts otimizados por disciplina quando disponíveis
USE_TUNED_PROMPTS = os.getenv("USE_TUNED_PROMPTS", "false").lower() == "true"

# Model Router — roteamento centralizado de LLMs por task_type
USE_MODEL_ROUTER = os.getenv("USE_MODEL_ROUTER", "false").lower() == "true"

# Model Evaluation Loop v1 — comparação automática e ranking dinâmico
USE_MODEL_EVALUATION = os.getenv("USE_MODEL_EVALUATION", "false").lower() == "true"

# Evolution Loop v1 — auto-otimização contínua (modelos, prompts, RAG)
USE_EVOLUTION_LOOP = os.getenv("USE_EVOLUTION_LOOP", "false").lower() == "true"
USE_SAFE_ROLLOUT = os.getenv("USE_SAFE_ROLLOUT", "true").lower() == "true"

# Agent Generation Loop v1 — proposta controlada de novos agentes (nunca auto-ativa)
USE_AGENT_GENERATION = os.getenv("USE_AGENT_GENERATION", "false").lower() == "true"

# Knowledge Layer — RAG multi-base (NBR, SINAPI, TCPO, TDR, catálogos)
USE_KNOWLEDGE_ROUTER = os.getenv("USE_KNOWLEDGE_ROUTER", "false").lower() == "true"

# Knowledge por disciplina — evolução paralela (off = comportamento atual inalterado)
USE_DISCIPLINE_KNOWLEDGE_ROUTER = os.getenv(
    "USE_DISCIPLINE_KNOWLEDGE_ROUTER", "false"
).lower() == "true"

# Ingestão — todos os documentos em knowledge/raw/documents/
USE_DISCIPLINE_INGESTION = os.getenv("USE_DISCIPLINE_INGESTION", "true").lower() == "true"

# RAG v2
RAG_VERSION = 2
RAG_TOP_K = 5
RAG_TOP_K_MIN = 3
RAG_TOP_K_MAX = 8
RAG_MIN_SCORE = 0.35
RAG_SEARCH_OVERSAMPLE = 10
RAG_CHUNK_MIN_TOKENS = 600
RAG_CHUNK_MAX_TOKENS = 1200
RAG_TARGET_LATENCY_MS = 800

# RAG performance — cache semântico + rerank leve
USE_RAG_SEMANTIC_CACHE = os.getenv("USE_RAG_SEMANTIC_CACHE", "true").lower() == "true"
RAG_SEMANTIC_CACHE_THRESHOLD = float(os.getenv("RAG_SEMANTIC_CACHE_THRESHOLD", "0.92"))
RAG_SEMANTIC_CACHE_MAX_ENTRIES = int(os.getenv("RAG_SEMANTIC_CACHE_MAX_ENTRIES", "500"))
USE_RAG_LIGHT_RERANK = os.getenv("USE_RAG_LIGHT_RERANK", "true").lower() == "true"
RAG_OBSERVABILITY_ENABLED = os.getenv("RAG_OBSERVABILITY_ENABLED", "true").lower() == "true"

# RAG por agente — cada agente busca apenas no seu escopo (default ON)
USE_AGENT_SCOPED_RAG = os.getenv("USE_AGENT_SCOPED_RAG", "true").lower() == "true"

# Orquestrador engenharia vs orçamento — separação SINAPI/NBR (default ON)
USE_ENGINEERING_ORCHESTRATOR = os.getenv(
    "USE_ENGINEERING_ORCHESTRATOR", "true"
).lower() == "true"

# Score ranking (hybrid)
RAG_BOOST_DISCIPLINE = 0.10
RAG_BOOST_DOC_TYPE = 0.05
RAG_BOOST_NBR = 0.15

# Rerank por edição da NBR (2014 > 2004 > 2001; match explícito na query)
USE_NBR_EDITION_RERANK = os.getenv("USE_NBR_EDITION_RERANK", "true").lower() == "true"
RAG_BOOST_NBR_EDITION_MATCH = float(os.getenv("RAG_BOOST_NBR_EDITION_MATCH", "0.35"))
RAG_BOOST_NBR_EDITION_RECENCY = float(os.getenv("RAG_BOOST_NBR_EDITION_RECENCY", "0.004"))
RAG_BOOST_NBR_EDITION_MAX = float(os.getenv("RAG_BOOST_NBR_EDITION_MAX", "0.15"))
RAG_PENALTY_NBR_EDITION_MISMATCH = float(os.getenv("RAG_PENALTY_NBR_EDITION_MISMATCH", "0.25"))

# Limite de contexto por agente (caracteres)
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

# Diretórios — estado mutável local (loops). NÃO colocar PDFs/conhecimento aqui.
DATA_DIR = BASE_DIR / "data"
LEARNING_V2_DIR = DATA_DIR / "learning_v2"
LEARNING_V2_PROFILES_DIR = LEARNING_V2_DIR / "profiles"
LEARNING_V2_PROMPTS_DIR = LEARNING_V2_DIR / "prompts"
EVOLUTION_DATA_DIR = DATA_DIR / "evolution"
AGENT_GENERATION_DATA_DIR = DATA_DIR / "agent_generation"

# Base técnica — storage flat
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
KNOWLEDGE_DOCUMENTS_DIR = KNOWLEDGE_DIR / "raw" / "documents"
KNOWLEDGE_DISCIPLINE_DIR = KNOWLEDGE_DOCUMENTS_DIR  # compat alias
NBR_DIR = KNOWLEDGE_DOCUMENTS_DIR
TDR_DIR = KNOWLEDGE_DOCUMENTS_DIR

# Índices vetoriais FAISS (gerados por scripts — memory/faiss_index/)
FAISS_INDEX_DIR = BASE_DIR / "memory" / "faiss_index"
EMBEDDING_CACHE_PATH = FAISS_INDEX_DIR / "embedding_cache.db"
SEMANTIC_CACHE_PATH = KNOWLEDGE_DIR / "cache" / "semantic_cache.db"
RAG_OBSERVABILITY_LOG_PATH = KNOWLEDGE_DIR / "cache" / "rag_failing_queries.jsonl"

# PostgreSQL
DB_HOST = "localhost"
DB_PORT = 5433
DB_NAME = "ia_server_santos"
DB_USER = "ia_user"
DB_PASSWORD = "ia_password"
DB_ENABLED = True

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
