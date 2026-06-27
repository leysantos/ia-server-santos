#!/usr/bin/env bash
# Inicia o Cloudflare Tunnel usando token (network_access.json) ou config nomeada.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib_token.sh
source "$ROOT/scripts/cloudflare/lib_token.sh"
CF_DIR="${HOME}/.cloudflared"
TUNNEL_NAME="${CF_TUNNEL_NAME:-ia-server-santos}"
LOG="${ROOT}/backend/data/system/cloudflared.log"
PID_FILE="${ROOT}/backend/data/system/cloudflared.pid"

mkdir -p "$(dirname "$LOG")"

get_token() {
  (cd "$ROOT" && "$ROOT/.venv/bin/python" - <<'PY'
import json
from pathlib import Path
p = Path("backend/data/system/network_access.json")
if not p.exists():
    exit(0)
cf = json.loads(p.read_text()).get("cloudflare") or {}
print(cf.get("tunnel_token") or "")
PY
)
}

TOKEN="$(normalize_tunnel_token "${CF_TUNNEL_TOKEN:-$(get_token)}")"

if [[ -n "$TOKEN" ]]; then
  if [[ ! "$TOKEN" =~ ^eyJ ]]; then
    echo "Erro: token inválido em network_access.json (cole só eyJhIjoi...)."
    exit 1
  fi
  echo "Iniciando túnel via token..."
  exec cloudflared tunnel run --token "$TOKEN" 2>&1 | tee -a "$LOG"
fi

CONFIG="${CF_DIR}/${TUNNEL_NAME}.yml"
if [[ -f "$CONFIG" ]]; then
  echo "Iniciando túnel nomeado: $CONFIG"
  exec cloudflared tunnel --config "$CONFIG" run 2>&1 | tee -a "$LOG"
fi

echo "Erro: nenhum token nem config encontrado."
echo "  Rode: ./scripts/cloudflare/setup_tunnel.sh"
echo "  Ou cole o token em Configurações → Acesso e rede → Cloudflare"
exit 1
