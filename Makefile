.PHONY: setup setup-backend setup-frontend api db-init index-nbrs index-knowledge backup-app restore test test-backend frontend docker-up auto-tune agent-generation workflow-worker workflow-infra

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

index-knowledge:
	cd $(BACKEND_DIR) && $(BACKEND_PYTHON) scripts/index_knowledge_bases.py

backup-app:
	bash scripts/maintenance/run_backup.sh app,database,knowledge,faiss

restore:
ifndef STAMP
	@echo "Uso: make restore STAMP=YYYYMMDD-HHMMSS [TARGETS=database,knowledge,faiss] [DRY_RUN=true]"
	@exit 1
endif
	bash scripts/maintenance/restore.sh "$(STAMP)" "$(or $(TARGETS),database,knowledge,faiss)"

test test-backend:
	cd $(BACKEND_DIR) && $(BACKEND_PYTHON) -m pytest tests/ -v

frontend:
	cd $(FRONTEND_DIR) && npm run dev

docker-up:
	cd infra/docker && docker compose up -d

workflow-infra:
	cd infra/docker && docker compose up -d redis minio

workflow-worker:
	cd $(BACKEND_DIR) && $(BACKEND_PYTHON) -m celery -A core.workflow.workers.celery_app:celery_app worker -l info -Q workflow -c 2

auto-tune:
	cd $(BACKEND_DIR) && $(BACKEND_PYTHON) scripts/run_auto_tune.py $(ARGS)

agent-generation:
	cd $(BACKEND_DIR) && $(BACKEND_PYTHON) scripts/run_agent_generation.py $(ARGS)
