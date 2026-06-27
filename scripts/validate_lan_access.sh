#!/usr/bin/env bash
# Valida acesso LAN (rede SEMINF) — health, frontend e auth/status.
# Uso: ./scripts/validate_lan_access.sh [host_ip]

set -euo pipefail

HOST="${1:-172.22.3.234}"
API="http://${HOST}:8000"
WEB="http://${HOST}:3000"

echo "=== Validação LAN — ${HOST} ==="
echo ""

check() {
  local name="$1" url="$2" expect="${3:-200}"
  code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$url" || echo "000")
  if [[ "$code" == "$expect" ]]; then
    echo "  OK  $name ($code) — $url"
  else
    echo "  FALHA $name (esperado $expect, obteve $code) — $url"
    return 1
  fi
}

fail=0
check "API /health" "${API}/health" || fail=1
check "Frontend proxy /api-backend/health" "${WEB}/api-backend/health" || fail=1
check "Frontend /login" "${WEB}/login" || fail=1
check "Auth /status" "${API}/auth/status" || fail=1

echo ""
echo "=== Teste de login (outro PC da equipe) ==="
echo "  1. Abra no navegador: ${WEB}/login"
echo "  2. Usuário: admin (ou dev_user1 / dev_user2)"
echo "  3. Após login deve ir para /chat sem tela branca"
echo ""
echo "  Se o login falhar com erro de rede, reinicie o frontend (npm run dev)."
echo "  O browser na LAN usa proxy same-origin: ${WEB}/api-backend → API :8000"
echo ""

if [[ "$fail" -eq 0 ]]; then
  echo "Resultado: LAN acessível para API e frontend."
else
  echo "Resultado: há falhas — verifique make api, npm run dev e setup_wsl_lan_access.ps1"
  exit 1
fi
