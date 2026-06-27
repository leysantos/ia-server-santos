#!/usr/bin/env bash
# Extrai o token JWT do cloudflared a partir de colagem parcial ou comando Windows completo.
normalize_tunnel_token() {
  local raw="${1:-}"
  raw="${raw#"${raw%%[![:space:]]*}"}"
  raw="${raw%"${raw##*[![:space:]]}"}"

  # Remove prefixo do comando Windows se o usuário colou a linha inteira
  raw="${raw#cloudflared.exe service install }"
  raw="${raw#cloudflared service install }"
  raw="${raw#cloudflared tunnel run --token }"
  raw="${raw#--token }"

  # Pega só o trecho eyJ... (JWT base64)
  if [[ "$raw" =~ (eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+) ]]; then
    echo "${BASH_REMATCH[1]}"
    return 0
  fi

  echo "$raw"
}

normalize_public_hostname() {
  local raw="${1:-}"
  raw="${raw#https://}"
  raw="${raw#http://}"
  raw="${raw%%/*}"
  raw="${raw%%:*}"  # remove :port se colou localhost:3000

  if [[ -z "$raw" ]] || [[ "$raw" == "localhost" ]] || [[ "$raw" == "127.0.0.1" ]]; then
    return 1
  fi
  echo "$raw"
}
