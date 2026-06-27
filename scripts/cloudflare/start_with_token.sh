#!/usr/bin/env bash
# Inicia o túnel com token (argumento ou network_access.json).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib_token.sh
source "$ROOT/scripts/cloudflare/lib_token.sh"

TOKEN="$(normalize_tunnel_token "${1:-}")"
if [[ -z "$TOKEN" ]]; then
  echo "Uso: $0 <token-do-painel-cloudflare>"
  echo "Cole só eyJhIjoi... (não a linha cloudflared.exe service install)"
  exit 1
fi
if [[ ! "$TOKEN" =~ ^eyJ ]]; then
  echo "Erro: token não parece válido (deve começar com eyJ)"
  exit 1
fi
export CF_TUNNEL_TOKEN="$TOKEN"
read -r -p "Hostname público do frontend (ex: ia.seudominio.gov.br, Enter para pular): " FE
read -r -p "Hostname público da API (ex: api-ia.seudominio.gov.br, Enter para pular): " API
CF_FRONTEND_HOST="$(normalize_public_hostname "$FE" 2>/dev/null || true)"
CF_API_HOST="$(normalize_public_hostname "$API" 2>/dev/null || true)"
export CF_FRONTEND_HOST CF_API_HOST
exec bash "$ROOT/scripts/cloudflare/setup_tunnel.sh"
