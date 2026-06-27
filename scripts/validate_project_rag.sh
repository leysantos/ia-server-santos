#!/usr/bin/env bash
# R10 — validação Project RAG contra API em execução.
# Upload memorial → reindex → busca workspace → chat com project_id (opcional).
#
# Uso: ./scripts/validate_project_rag.sh [api_base] [username] [password]
# Requer: API (:8000), PostgreSQL, Ollama com nomic-embed-text para indexação completa.

set -euo pipefail

API_BASE="${1:-http://localhost:8000}"
USER="${2:-admin}"
PASS="${3:-Admin@2026!}"
MARKER="VALIDATE_RAG_$(date +%s)"

echo "=== R10 Project RAG — ${API_BASE} ==="

code=$(curl -s -o /dev/null -w "%{http_code}" "${API_BASE}/health")
[[ "$code" == "200" ]] || { echo "FALHA /health ($code)"; exit 1; }
echo "  OK  /health"

login=$(curl -s -X POST "${API_BASE}/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"${USER}\",\"password\":\"${PASS}\"}")
token=$(echo "$login" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || true)
[[ -n "$token" ]] || { echo "FALHA login: $login"; exit 1; }
echo "  OK  login"

AUTH=(-H "Authorization: Bearer ${token}")

proj=$(curl -s -X POST "${API_BASE}/projects" \
  "${AUTH[@]}" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"RAG validate ${MARKER}\",\"description\":\"R10 script\"}")
proj_id=$(echo "$proj" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || true)
[[ -n "$proj_id" ]] || { echo "FALHA criar projeto: $proj"; exit 1; }
echo "  OK  projeto $proj_id"

tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT
printf 'Memorial RAG\nViga V1 — %s\nCarga 200 kN\n' "$MARKER" > "${tmpdir}/memorial.txt"

upload=$(curl -s -X POST "${API_BASE}/projects/${proj_id}/files" \
  "${AUTH[@]}" \
  -F "files=@${tmpdir}/memorial.txt;type=text/plain")
uploaded=$(echo "$upload" | python3 -c "import sys,json; print(json.load(sys.stdin).get('uploaded',0))" 2>/dev/null || echo 0)
[[ "$uploaded" == "1" ]] || { echo "FALHA upload: $upload"; exit 1; }
echo "  OK  upload memorial.txt"

reindex=$(curl -s -X POST "${API_BASE}/projects/${proj_id}/reindex" "${AUTH[@]}")
indexed=$(echo "$reindex" | python3 -c "import sys,json; print(json.load(sys.stdin).get('indexed',0))" 2>/dev/null || echo 0)
if [[ "$indexed" -ge 1 ]]; then
  echo "  OK  reindex ($indexed arquivo(s))"
else
  echo "  AVISO reindex sem chunks (Ollama/embed offline?): $reindex"
fi

search=$(curl -s "${API_BASE}/workspace/search?q=RAG+validate+${MARKER}" "${AUTH[@]}")
found=$(echo "$search" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(1 if any('${MARKER}' in (p.get('name') or '') for p in d.get('projects', [])) else 0)
" 2>/dev/null || echo 0)
[[ "$found" == "1" ]] || { echo "FALHA busca workspace: $search"; exit 1; }
echo "  OK  workspace/search"

if [[ "$indexed" -ge 1 ]]; then
  chat=$(curl -s -X POST "${API_BASE}/chat" \
    "${AUTH[@]}" \
    -H "Content-Type: application/json" \
    -d "{\"text\":\"O memorial menciona ${MARKER}?\",\"persist\":false,\"use_rag\":true,\"project_id\":\"${proj_id}\"}")
  chat_ok=$(echo "$chat" | python3 -c "import sys,json; d=json.load(sys.stdin); print(1 if d.get('result') else 0)" 2>/dev/null || echo 0)
  if [[ "$chat_ok" == "1" ]]; then
    echo "  OK  /chat com project_id"
  else
    echo "  AVISO chat sem result (LLM offline?): $chat"
  fi
fi

curl -s -o /dev/null -X DELETE "${API_BASE}/projects/${proj_id}" "${AUTH[@]}" || true
echo ""
echo "Resultado: validação R10 Project RAG concluída."
