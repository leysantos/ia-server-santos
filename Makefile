.PHONY: api db-init index-nbrs test test-backend frontend docker-up auto-tune agent-generation

BACKEND_DIR := backend
FRONTEND_DIR := frontend

api:
	cd $(BACKEND_DIR) && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

db-init:
	cd $(BACKEND_DIR) && python3 scripts/init_db.py

index-nbrs:
	cd $(BACKEND_DIR) && python3 scripts/index_nbrs.py

test test-backend:
	cd $(BACKEND_DIR) && python3 -m pytest tests/ -v

frontend:
	cd $(FRONTEND_DIR) && npm run dev

docker-up:
	cd infra/docker && docker compose up -d

auto-tune:
	cd $(BACKEND_DIR) && python3 scripts/run_auto_tune.py $(ARGS)

agent-generation:
	cd $(BACKEND_DIR) && python3 scripts/run_agent_generation.py $(ARGS)
