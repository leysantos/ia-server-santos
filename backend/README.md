# IA Server Santos — Backend

API FastAPI, agentes multi-disciplina, RAG v2 (FAISS), loops de evolução e PostgreSQL.

## Setup

```bash
# Na raiz do monorepo (recomendado)
make setup-backend
source ../.venv/bin/activate

# Manual
cd backend
python3 -m venv ../.venv    # requer: sudo apt install python3.14-venv
source ../.venv/bin/activate
pip install -r requirements.txt
```

## Comandos

```bash
# API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Banco
python scripts/init_db.py

# Indexar NBRs (PDFs em knowledge_base/nbrs/)
python scripts/index_nbrs.py

# Indexar todas as bases técnicas (multi-FAISS)
python scripts/index_knowledge_bases.py

# Testes
python -m pytest tests/ -v
```

Na raiz do monorepo, use `make api`, `make test`, etc.

## Estrutura

| Pasta | Conteúdo |
|-------|----------|
| `app/` | FastAPI routes e services |
| `core/` | Router, dispatcher, orchestrator, loops |
| `agents/` | Agentes por disciplina |
| `memory/` | RAG v2 (FAISS, embeddings) |
| `config/` | Settings e feature flags |
| `data/` | PDFs NBR/TDR, perfis de learning/evolution |
| `scripts/` | CLI (init_db, index_nbrs, auto_tune) |
| `tests/` | Test suites |
