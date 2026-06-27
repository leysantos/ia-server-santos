#!/usr/bin/env bash
# Fase 2 — validação bases de preço (price_bank + composition FAISS + API).
# Uso: ./scripts/validate_price_bases.sh [api_base] [username] [password]

set -euo pipefail

API_BASE="${1:-http://localhost:8000}"
USER="${2:-admin}"
PASS="${3:-Admin@2026!}"

echo "=== Fase 2 — price bases — ${API_BASE} ==="

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

refs=$(curl -s "${API_BASE}/pricing/sync/bank/references" "${AUTH[@]}")
total=$(echo "$refs" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('references', d if isinstance(d,list) else [])))" 2>/dev/null || echo 0)
if [[ "$total" -lt 1 ]]; then
  echo "FALHA sem referências no price_bank: $refs"
  exit 1
fi
echo "  OK  /pricing/sync/bank/references ($total períodos)"

inv=$(curl -s "${API_BASE}/pricing/sync/bank/inventory" "${AUTH[@]}")
sinapi_n=$(echo "$inv" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for g in d.get('groups', []):
    if g.get('source') == 'sinapi':
        print(sum(int(p.get('counts',{}).get('compositions_closed',0) or 0) for p in g.get('periods',[])))
        break
else:
    print(0)
" 2>/dev/null || echo 0)
if [[ "${sinapi_n:-0}" -lt 1000 ]]; then
  echo "  AVISO SINAPI com poucas composições no inventário ($sinapi_n)"
else
  echo "  OK  inventário SINAPI (~${sinapi_n} composições fechadas)"
fi

comp=$(curl -s "${API_BASE}/pricing/sync/bank/composition/95995?uf=AM&reference=BR-2026-05" "${AUTH[@]}")
has_code=$(echo "$comp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(1 if d.get('code') or d.get('composition') or d.get('open') else 0)" 2>/dev/null || echo 0)
if [[ "$has_code" == "1" ]]; then
  echo "  OK  prévia composição 95995 (SINAPI BR-2026-05 / AM)"
else
  echo "  AVISO prévia composição: $comp"
fi

echo ""
echo "Resultado: validação price bases concluída."
