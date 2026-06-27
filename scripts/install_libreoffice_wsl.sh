#!/usr/bin/env bash
# Instala LibreOffice Calc no WSL/Ubuntu — necessário para PDF Planilha/MCQ SEMINF.
set -euo pipefail

if command -v libreoffice >/dev/null 2>&1; then
  echo "LibreOffice já instalado:"
  libreoffice --version
  exit 0
fi

if command -v soffice >/dev/null 2>&1; then
  echo "LibreOffice (soffice) já instalado:"
  soffice --version
  exit 0
fi

for win in \
  "/mnt/c/Program Files/LibreOffice/program/soffice.exe" \
  "/mnt/c/Program Files (x86)/LibreOffice/program/soffice.exe"
do
  if [[ -x "$win" ]]; then
    echo "LibreOffice Windows encontrado: $win"
    echo "Exporte no .env ou shell:"
    echo "  export LIBREOFFICE_PATH=\"$win\""
    exit 0
  fi
done

echo "Instalando libreoffice-calc (requer sudo)..."
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y libreoffice-calc
libreoffice --version
echo "OK — PDF Planilha/MCQ disponíveis na API /pricing/budget/{id}/workbook/pdf/*"
