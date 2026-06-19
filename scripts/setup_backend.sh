#!/usr/bin/env bash
# Cria .venv na raiz do monorepo e instala backend/requirements.txt
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${ROOT}/.venv"
REQ="${ROOT}/backend/requirements.txt"

cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Erro: python3 não encontrado no PATH." >&2
  exit 1
fi

if ! python3 -c "import venv" 2>/dev/null; then
  PY_VER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  echo "Erro: módulo venv indisponível (PEP 668 / Debian)." >&2
  echo "" >&2
  echo "Instale o pacote venv e rode de novo:" >&2
  echo "  sudo apt update && sudo apt install python${PY_VER}-venv" >&2
  echo "  make setup-backend" >&2
  echo "" >&2
  echo "Alternativa rápida só para benchmark (psutil):" >&2
  echo "  sudo apt install python3-psutil" >&2
  exit 1
fi

venv_is_valid() {
  [[ -x "${VENV}/bin/python" && -x "${VENV}/bin/pip" ]]
}

remove_broken_venv() {
  if [[ ! -d "$VENV" ]]; then
    return 0
  fi
  echo "→ Removendo .venv incompleto ..."
  if rm -rf "$VENV" 2>/dev/null; then
    return 0
  fi
  echo "" >&2
  echo "Erro: não foi possível remover .venv (permissão negada?)." >&2
  echo "Rode manualmente e tente de novo:" >&2
  echo "  sudo rm -rf .venv" >&2
  echo "  make setup-backend" >&2
  exit 1
}

create_venv() {
  echo "→ Criando virtualenv em .venv ..."
  if ! python3 -m venv "$VENV"; then
    echo "" >&2
    echo "Erro ao criar .venv — confira se python3-venv está instalado:" >&2
    PY_VER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    echo "  sudo apt install python${PY_VER}-venv" >&2
    exit 1
  fi
  if ! venv_is_valid; then
    echo "" >&2
    echo "Erro: .venv criado sem pip (ensurepip ausente)." >&2
    PY_VER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    echo "  sudo apt install python${PY_VER}-venv" >&2
    remove_broken_venv
    exit 1
  fi
}

if [[ -d "$VENV" ]]; then
  if venv_is_valid; then
    echo "→ Virtualenv .venv OK."
  else
    echo "→ .venv existe mas está incompleto (sem pip)."
    remove_broken_venv
    create_venv
  fi
else
  create_venv
fi

echo "→ Instalando dependências de backend/requirements.txt ..."
"${VENV}/bin/pip" install -U pip wheel
"${VENV}/bin/pip" install -r "$REQ"

echo ""
echo "✓ Backend pronto."
echo "  Ativar:  source .venv/bin/activate"
echo "  API:     make api"
echo "  Testes:  make test"
