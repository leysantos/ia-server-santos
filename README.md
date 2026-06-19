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
# PostgreSQL
make docker-up
make db-init

# Backend
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# ou: make api

# Frontend
make frontend
```

Documentação completa: [docs/project_state.md](docs/project_state.md)

## Backend

Ver [backend/README.md](backend/README.md).

## Frontend

Ver [frontend/README.md](frontend/README.md).
