#!/usr/bin/env bash
# Reinicia o Next.js dev com cache limpo (corrige 404/500 após HMR corrompido).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND="$ROOT/frontend"

echo "→ Parando instâncias next dev..."
pkill -f "$FRONTEND/node_modules/.bin/next dev" 2>/dev/null || true
pkill -f "next-server" 2>/dev/null || true
sleep 1

echo "→ Limpando .next..."
rm -rf "$FRONTEND/.next"

cd "$FRONTEND"
echo "→ Iniciando npm run dev (porta 3000)..."
exec npm run dev
