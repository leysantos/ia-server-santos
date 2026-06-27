#!/usr/bin/env bash
# Túnel temporário SEM domínio próprio — URLs *.trycloudflare.com (mudam a cada execução).
# Uso: ./scripts/cloudflare/quick_tunnel.sh
# Requer: make api + npm run dev rodando no WSL.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOG_DIR="${ROOT}/backend/data/system"
API_LOG="${LOG_DIR}/cloudflared-api.log"
FE_LOG="${LOG_DIR}/cloudflared-frontend.log"
URL_FILE="${LOG_DIR}/quick_tunnel_urls.txt"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "Erro: cloudflared não instalado."
  exit 1
fi

mkdir -p "$LOG_DIR"

check_port() {
  local port="$1" name="$2"
  if ! curl -s -o /dev/null --connect-timeout 2 "http://127.0.0.1:${port}/"; then
    if ! curl -s -o /dev/null --connect-timeout 2 "http://127.0.0.1:${port}/health"; then
      echo "Aviso: nada respondendo na porta ${port} (${name}). Suba o serviço antes."
    fi
  fi
}

check_port 8000 "API"
check_port 3000 "frontend"

pkill -f "cloudflared tunnel --url http://localhost:8000" 2>/dev/null || true
pkill -f "cloudflared tunnel --url http://localhost:3000" 2>/dev/null || true
sleep 1

echo "Iniciando Quick Tunnels (sem domínio próprio)..."
echo ""

cloudflared tunnel --url "http://localhost:8000" >"$API_LOG" 2>&1 &
API_PID=$!
cloudflared tunnel --url "http://localhost:3000" >"$FE_LOG" 2>&1 &
FE_PID=$!

extract_url() {
  local log="$1"
  local url=""
  for _ in $(seq 1 30); do
    url=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$log" 2>/dev/null | head -1 || true)
    if [[ -n "$url" ]]; then
      echo "$url"
      return 0
    fi
    sleep 1
  done
  return 1
}

API_URL="$(extract_url "$API_LOG" || true)"
FE_URL="$(extract_url "$FE_LOG" || true)"

if [[ -z "$API_URL" || -z "$FE_URL" ]]; then
  echo "Erro: não foi possível obter URLs trycloudflare. Veja os logs:"
  echo "  $API_LOG"
  echo "  $FE_LOG"
  kill "$API_PID" "$FE_PID" 2>/dev/null || true
  exit 1
fi

cat >"$URL_FILE" <<EOF
# Gerado em $(date -Iseconds) — URLs temporárias, mudam ao reiniciar o script
API_URL=${API_URL}
FRONTEND_URL=${FE_URL}
API_PID=${API_PID}
FRONTEND_PID=${FE_PID}
EOF

"$ROOT/.venv/bin/python" - <<PY
import json
from pathlib import Path
path = Path("${ROOT}/backend/data/system/network_access.json")
data = json.loads(path.read_text()) if path.exists() else {}
cf = data.setdefault("cloudflare", {})
cf.update({
    "enabled": True,
    "tunnel_name": "quick-tunnel-trycloudflare",
    "notes": "Sem domínio próprio — URLs temporárias trycloudflare.com",
    "public_frontend_url": "${FE_URL}",
    "public_api_url": "${API_URL}",
    "public_hostname": "${FE_URL}".replace("https://", ""),
})
for u in ("${FE_URL}", "${API_URL}"):
    if u not in data.setdefault("cors_extra_origins", []):
        data["cors_extra_origins"].append(u)
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
print("network_access.json atualizado com URLs temporárias.")
PY

echo "=============================================="
echo "  Acesso EXTERNO temporário (sem domínio)"
echo "=============================================="
echo ""
echo "  Frontend:  ${FE_URL}"
echo "  API:       ${API_URL}"
echo ""
echo "  Login:     ${FE_URL}/login"
echo "  Health:    ${API_URL}/health"
echo ""
echo "  PIDs: API=${API_PID}  Frontend=${FE_PID}"
echo "  URLs salvas em: ${URL_FILE}"
echo ""
echo "Próximo passo — frontend (.env.local):"
echo "  NEXT_PUBLIC_API_URL=${API_URL}"
echo ""
echo "  cd frontend && nano .env.local"
echo "  Reinicie: npm run dev"
echo "  Reinicie a API (make api) para CORS."
echo ""
echo "Para parar: kill ${API_PID} ${FE_PID}"
echo "=============================================="
