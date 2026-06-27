#!/usr/bin/env bash
# Configura Cloudflare Tunnel para IA Server Santos (WSL).
#
# Pré-requisitos:
#   - cloudflared instalado (já em /usr/local/bin/cloudflared)
#   - Domínio gerenciado na Cloudflare
#   - API (:8000) e frontend (:3000) rodando no WSL
#
# Uso interativo:
#   ./scripts/cloudflare/setup_tunnel.sh
#
# Ou com variáveis:
#   CF_FRONTEND_HOST=ia.seudominio.gov.br \
#   CF_API_HOST=api-ia.seudominio.gov.br \
#   ./scripts/cloudflare/setup_tunnel.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib_token.sh
source "$ROOT/scripts/cloudflare/lib_token.sh"
CF_DIR="${HOME}/.cloudflared"
TUNNEL_NAME="${CF_TUNNEL_NAME:-ia-server-santos}"
FRONTEND_PORT="${CF_FRONTEND_PORT:-3000}"
API_PORT="${CF_API_PORT:-8000}"

echo "=== Cloudflare Tunnel — IA Server Santos ==="
echo ""
echo "IMPORTANTE (painel Cloudflare):"
echo "  • Nome do túnel: use um rótulo (ex: ia-server-santos), NÃO uma URL."
echo "  • Este projeto roda no WSL — copie o TOKEN e rode no WSL (não use o .msi do Windows)."
echo "  • Depois de criar o túnel, adicione 2 Public Hostnames no painel:"
echo "      Frontend → http://localhost:3000"
echo "      API      → http://localhost:8000"
echo ""

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "Erro: cloudflared não encontrado. Instale: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/"
  exit 1
fi

cloudflared --version
echo ""

mkdir -p "$CF_DIR"

# --- Modo rápido: token do painel Zero Trust ---
if [[ -n "${CF_TUNNEL_TOKEN:-}" ]]; then
  echo "Token detectado (CF_TUNNEL_TOKEN). Salvando em network_access..."
  FE_HOST="${CF_FRONTEND_HOST:-}"
  API_HOST="${CF_API_HOST:-}"
  TOKEN="$(normalize_tunnel_token "${CF_TUNNEL_TOKEN}")"
  if [[ ! "$TOKEN" =~ ^eyJ ]]; then
    echo "Erro: CF_TUNNEL_TOKEN inválido. Use só o token eyJhIjoi..."
    exit 1
  fi
  CF_TUNNEL_TOKEN="$TOKEN"
  "$ROOT/.venv/bin/python" - <<PY
import json, os
from pathlib import Path
path = Path("${ROOT}/backend/data/system/network_access.json")
data = json.loads(path.read_text()) if path.exists() else {}
cf = data.setdefault("cloudflare", {})
cf["enabled"] = True
cf["tunnel_token"] = """${TOKEN}"""
fe = """${FE_HOST}"""
api = """${API_HOST}"""
if fe:
    cf["public_frontend_url"] = fe if fe.startswith("http") else f"https://{fe}"
    cf["public_hostname"] = cf["public_frontend_url"].replace("https://", "").replace("http://", "").split("/")[0]
if api:
    cf["public_api_url"] = api if api.startswith("http") else f"https://{api}"
origins = data.setdefault("cors_extra_origins", [])
for u in (cf.get("public_frontend_url"), cf.get("public_api_url")):
    if u and u.rstrip("/") not in origins:
        origins.append(u.rstrip("/"))
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
print("network_access.json atualizado.")
PY
  echo "Iniciando túnel..."
  exec "$ROOT/scripts/cloudflare/run_tunnel.sh"
fi

echo "Escolha o modo de configuração:"
echo "  1) Token do painel Cloudflare Zero Trust (recomendado — mais rápido)"
echo "  2) Túnel nomeado (cloudflared tunnel create + DNS)"
read -r -p "Opção [1/2]: " MODE

if [[ "$MODE" == "1" ]]; then
  echo ""
  echo "No painel Cloudflare: Zero Trust → Networks → Tunnels → Create tunnel"
  echo "Configure Public Hostname:"
  echo "  - Frontend → http://localhost:${FRONTEND_PORT}"
  echo "  - API      → http://localhost:${API_PORT}"
  echo ""
  echo "  Cole APENAS o token (string que começa com eyJhIjoi...)."
  echo "  NÃO cole a linha inteira 'cloudflared.exe service install ...'."
  echo ""
  read -r -p "Cole o token do túnel: " TOKEN_RAW
  TOKEN="$(normalize_tunnel_token "$TOKEN_RAW")"
  if [[ ! "$TOKEN" =~ ^eyJ ]]; then
    echo "Erro: token inválido. Copie só a parte eyJhIjoi... do painel Cloudflare."
    exit 1
  fi
  read -r -p "Hostname público do frontend (ex: ia.seudominio.gov.br, SEM http://): " FE_RAW
  read -r -p "Hostname público da API (ex: api-ia.seudominio.gov.br): " API_RAW
  FE_HOST="$(normalize_public_hostname "$FE_RAW" || true)"
  API_HOST="$(normalize_public_hostname "$API_RAW" || true)"
  if [[ -z "$FE_HOST" || -z "$API_HOST" ]]; then
    echo ""
    echo "Aviso: hostnames públicos devem ser domínios reais na Cloudflare (não localhost)."
    echo "Configure Public Hostnames no painel Zero Trust e informe os domínios aqui."
    echo "O túnel pode subir mesmo assim; URLs públicas ficam só no painel Cloudflare."
  fi
  CF_TUNNEL_TOKEN="$TOKEN" CF_FRONTEND_HOST="${FE_HOST:-}" CF_API_HOST="${API_HOST:-}" \
    exec "$ROOT/scripts/cloudflare/setup_tunnel.sh"
fi

# --- Modo 2: túnel nomeado ---
if [[ ! -f "${CF_DIR}/cert.pem" ]]; then
  echo ""
  echo "Login na Cloudflare (abrirá o navegador no Windows)..."
  cloudflared tunnel login
fi

echo ""
read -r -p "Hostname frontend (ex: ia.seudominio.gov.br): " FE_HOST
read -r -p "Hostname API (ex: api-ia.seudominio.gov.br): " API_HOST

if cloudflared tunnel list 2>/dev/null | grep -q "$TUNNEL_NAME"; then
  echo "Túnel '$TUNNEL_NAME' já existe."
else
  cloudflared tunnel create "$TUNNEL_NAME"
fi

TUNNEL_ID=$(cloudflared tunnel list 2>/dev/null | awk -v n="$TUNNEL_NAME" '$0 ~ n {print $1; exit}')
if [[ -z "$TUNNEL_ID" ]]; then
  echo "Erro: não foi possível obter o ID do túnel."
  exit 1
fi

CONFIG="${CF_DIR}/${TUNNEL_NAME}.yml"
cat > "$CONFIG" <<EOF
# Gerado por scripts/cloudflare/setup_tunnel.sh
tunnel: ${TUNNEL_ID}
credentials-file: ${CF_DIR}/${TUNNEL_ID}.json

ingress:
  - hostname: ${FE_HOST}
    service: http://localhost:${FRONTEND_PORT}
  - hostname: ${API_HOST}
    service: http://localhost:${API_PORT}
  - service: http_status:404
EOF

echo "Config: $CONFIG"
cloudflared tunnel route dns "$TUNNEL_NAME" "$FE_HOST" || true
cloudflared tunnel route dns "$TUNNEL_NAME" "$API_HOST" || true

"$ROOT/.venv/bin/python" - <<PY
import json
from pathlib import Path
path = Path("${ROOT}/backend/data/system/network_access.json")
data = json.loads(path.read_text())
cf = data.setdefault("cloudflare", {})
cf.update({
    "enabled": True,
    "tunnel_name": "${TUNNEL_NAME}",
    "tunnel_id": "${TUNNEL_ID}",
    "public_hostname": "${FE_HOST}",
    "public_frontend_url": "https://${FE_HOST}",
    "public_api_url": "https://${API_HOST}",
    "notes": "Túnel nomeado; config em ${CONFIG}",
})
for u in (cf["public_frontend_url"], cf["public_api_url"]):
    if u not in data.setdefault("cors_extra_origins", []):
        data["cors_extra_origins"].append(u)
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
print("network_access.json atualizado.")
PY

echo ""
echo "=== Próximos passos ==="
echo "  1. Inicie o túnel:  make cloudflare-run"
echo "  2. Frontend externo: cp frontend/.env.cloudflare.example frontend/.env.local"
echo "     Ajuste NEXT_PUBLIC_API_URL=https://${API_HOST} e reinicie npm run dev"
echo "  3. Reinicie a API para CORS com os domínios HTTPS"
echo "  4. (Opcional) Cloudflare Access no painel Zero Trust para proteger o login"
echo ""
read -r -p "Iniciar túnel agora? [s/N]: " START
if [[ "${START,,}" == "s" ]]; then
  exec "$ROOT/scripts/cloudflare/run_tunnel.sh"
fi
