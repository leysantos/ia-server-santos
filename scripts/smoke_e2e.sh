#!/usr/bin/env bash
# Smoke E2E contra API em execução — login, health, conversas, projeto opcional.
# Uso: ./scripts/smoke_e2e.sh [api_base] [username] [password]
# Ex.: ./scripts/smoke_e2e.sh http://localhost:8000 admin 'Admin@2026!'

set -euo pipefail

API_BASE="${1:-http://localhost:8000}"
USER="${2:-admin}"
PASS="${3:-Admin@2026!}"

echo "=== Smoke E2E — ${API_BASE} ==="

code=$(curl -s -o /dev/null -w "%{http_code}" "${API_BASE}/health")
[[ "$code" == "200" ]] || { echo "FALHA /health ($code)"; exit 1; }
echo "  OK  /health"

login=$(curl -s -X POST "${API_BASE}/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"${USER}\",\"password\":\"${PASS}\"}")
token=$(echo "$login" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || true)
[[ -n "$token" ]] || { echo "FALHA login: $login"; exit 1; }
echo "  OK  login ($USER)"

conv_code=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer ${token}" \
  "${API_BASE}/conversations?limit=5")
[[ "$conv_code" == "200" ]] || { echo "FALHA /conversations ($conv_code)"; exit 1; }
echo "  OK  /conversations"

proj=$(curl -s -X POST "${API_BASE}/projects" \
  -H "Authorization: Bearer ${token}" \
  -H "Content-Type: application/json" \
  -d '{"name":"smoke-e2e","description":"teste automatizado"}')
proj_id=$(echo "$proj" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null || true)
if [[ -n "$proj_id" ]]; then
  echo "  OK  POST /projects ($proj_id)"
  tmpdir=$(mktemp -d)
  echo "smoke memorial" > "${tmpdir}/smoke.txt"
  up_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    -H "Authorization: Bearer ${token}" \
    -F "files=@${tmpdir}/smoke.txt;type=text/plain" \
    "${API_BASE}/projects/${proj_id}/files")
  rm -rf "$tmpdir"
  if [[ "$up_code" == "200" ]]; then
    echo "  OK  POST /projects/${proj_id}/files"
  else
    echo "  AVISO upload projeto ($up_code)"
  fi
  curl -s -o /dev/null -X DELETE \
    -H "Authorization: Bearer ${token}" \
    "${API_BASE}/projects/${proj_id}" || true
else
  echo "  AVISO POST /projects falhou (DB off?) — $proj"
fi

echo ""
echo "Resultado: smoke E2E passou."
