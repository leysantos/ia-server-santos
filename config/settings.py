from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Ollama
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_EMBED_MODEL = "nomic-embed-text"
OLLAMA_LLM_MODEL = "qwen3:14b"

# RAG v2
RAG_VERSION = 2
RAG_TOP_K = 5
RAG_MIN_SCORE = 0.35
RAG_SEARCH_OVERSAMPLE = 10
RAG_CHUNK_MIN_TOKENS = 600
RAG_CHUNK_MAX_TOKENS = 1200

# Score ranking (hybrid)
RAG_BOOST_DISCIPLINE = 0.10
RAG_BOOST_DOC_TYPE = 0.05
RAG_BOOST_NBR = 0.15

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

# Diretórios
DATA_DIR = BASE_DIR / "data"
NBR_DIR = DATA_DIR / "nbrs"
TDR_DIR = DATA_DIR / "tdrs"
FAISS_INDEX_DIR = BASE_DIR / "memory" / "faiss_index"
EMBEDDING_CACHE_PATH = FAISS_INDEX_DIR / "embedding_cache.db"

# Legado (migração v1 → v2)
INDEX_DIR = DATA_DIR / "index"
VECTOR_STORE_PATH = INDEX_DIR / "vector_store.json"

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
