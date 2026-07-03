#!/usr/bin/env bash
# Subset estável de pytest para CI (sem PostgreSQL/Ollama/FAISS pesado).
# Duas fases: testes unitários do orçamento, depois smoke+piloto (app FastAPI).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="${ROOT}/backend"
VENV_PY="${ROOT}/.venv/bin/python"

if [[ ! -x "$VENV_PY" ]]; then
  echo "Erro: .venv não encontrado — rode 'make setup-backend' antes." >&2
  exit 1
fi

export AUTH_ENABLED="${AUTH_ENABLED:-true}"
export JWT_SECRET="${JWT_SECRET:-test-jwt-secret-key-minimum-32-chars}"
export DB_ENABLED="${DB_ENABLED:-true}"
export MINIO_ENABLED="${MINIO_ENABLED:-false}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///${TMPDIR:-/tmp}/iaserver-ci.db}"

cd "$BACKEND"

UNIT_TESTS=(
  tests/test_pricing_engine.py
  tests/test_budget_engine_v2.py
  tests/test_budget_ownership.py
  tests/test_budget_tenant.py
  tests/test_budget_session_lock.py
  tests/test_budget_revisions.py
  tests/test_budget_session_restore.py
  tests/test_budget_audit_b16.py
  tests/test_budget_commercial.py
  tests/test_budget_compliance_pack.py
  tests/test_bdi_edital_validator.py
  tests/test_bdi_edital_profiles.py
  tests/test_sinapi_caixa_pricing.py
  tests/test_orse_connector.py
  tests/test_orse_portal_scraper.py
  tests/test_budget_export.py
  tests/test_budget_analytics.py
)

APP_TESTS=(
  tests/test_smoke_e2e.py
  tests/test_budget_pilot_flow.py
)

echo "→ CI backend fase 1: orçamento/pricing (${#UNIT_TESTS[@]} arquivos)"
"$VENV_PY" -m pytest "${UNIT_TESTS[@]}" -v --tb=short "$@"

echo "→ CI backend fase 2: smoke + piloto B12 (${#APP_TESTS[@]} arquivos)"
"$VENV_PY" -m pytest "${APP_TESTS[@]}" -v --tb=short "$@"
