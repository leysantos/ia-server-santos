#!/usr/bin/env bash
# Piloto UI manual §4.U — checklist para validação humana na /budget (B17)
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8000}"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=== Piloto UI manual §4.U (B17) ==="
echo "API: $API_BASE"
echo ""
echo -e "${YELLOW}Execute na UI /budget (validação humana orçamentista):${NC}"
echo ""
echo "  4.U1 — Carregar esqueleto passarela (sk-b12-piloto-passarela)"
echo "  4.U2 — Busca CPU: conferir CPU Caixa ComD/SemD vs planilha SINAPI oficial"
echo "  4.U3 — Lançar CPU na etapa (B13) e validar total adotado (menor)"
echo "  4.U4 — Cronograma: sync + curva físico-financeiro coerente com WBS"
echo "  4.U5 — Export .xlsm oficial (GET /budget/{id}/export/xlsm)"
echo "  4.U6 — Export compliance-pack.json e revisar checklist L1–L7"
echo "  4.U7 — Proposta comercial: margem % + export proposta_comercial"
echo ""
echo -e "${GREEN}Automação API (pré-requisito):${NC}"
if command -v curl >/dev/null 2>&1; then
  if curl -sf "$API_BASE/health" >/dev/null 2>&1; then
    echo "  ✓ API online — rode: make validate-budget-pilot"
  else
    echo "  ✗ API offline — suba com: make api"
    exit 1
  fi
else
  echo "  (curl não disponível — valide API manualmente)"
fi
echo ""
echo "Marque cada item 4.U* no docs/e2e_validation_checklist.md após conferência."
