# IA Server Santos

Monorepo da plataforma de engenharia civil multiagente com IA.

```
ia-server-santos/
├── backend/          # FastAPI, agentes, RAG, loops de evolução
├── frontend/         # Next.js SaaS UI
├── docs/             # Documentação (project_state.md)
└── infra/            # Docker (PostgreSQL)
```

## Quick start

```bash
# Dependências (primeira vez — cria .venv + pip install)
make setup-backend          # requer: sudo apt install python3.14-venv
make setup-frontend         # npm install

# PostgreSQL
make docker-up
make db-init

# Backend (usa .venv/bin/uvicorn automaticamente)
make api

# Frontend
make frontend
```

Documentação completa: [docs/project_state.md](docs/project_state.md)

## Backend

Ver [backend/README.md](backend/README.md).

## Frontend

Ver [frontend/README.md](frontend/README.md).
