.PHONY: setup setup-backend setup-frontend api db-init index-nbrs test test-backend frontend docker-up auto-tune agent-generation

BACKEND_DIR := backend
FRONTEND_DIR := frontend
VENV := .venv
# Caminho absoluto evita RuntimeWarning do venv (backend/../.venv vs .venv)
VENV_PYTHON := $(abspath $(VENV)/bin/python)
BACKEND_PYTHON := $(if $(wildcard $(VENV)/bin/python),$(VENV_PYTHON),python3)

setup: setup-backend setup-frontend

setup-backend:
	@bash scripts/setup_backend.sh

setup-frontend:
	cd $(FRONTEND_DIR) && npm install

api:
	@if [ ! -x "$(VENV)/bin/python" ]; then \
		echo "Aviso: .venv não encontrado — rode 'make setup-backend' primeiro."; \
	fi
	cd $(BACKEND_DIR) && $(BACKEND_PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

db-init:
	cd $(BACKEND_DIR) && $(BACKEND_PYTHON) scripts/init_db.py

index-nbrs:
	cd $(BACKEND_DIR) && $(BACKEND_PYTHON) scripts/index_nbrs.py

test test-backend:
	cd $(BACKEND_DIR) && $(BACKEND_PYTHON) -m pytest tests/ -v

frontend:
	cd $(FRONTEND_DIR) && npm run dev

docker-up:
	cd infra/docker && docker compose up -d

auto-tune:
	cd $(BACKEND_DIR) && $(BACKEND_PYTHON) scripts/run_auto_tune.py $(ARGS)

agent-generation:
	cd $(BACKEND_DIR) && $(BACKEND_PYTHON) scripts/run_agent_generation.py $(ARGS)
