#!/usr/bin/env bash
# B12 / §4 — validação piloto orçamento em campo (API live).
# Cobre checklist docs/e2e_validation_checklist.md §4.1–4.5.
# Uso: ./scripts/validate_budget_pilot.sh [api_base] [username] [password]

set -euo pipefail

API_BASE="${1:-http://localhost:8000}"
USER="${2:-admin}"
PASS="${3:-Admin@2026!}"

PASS_COUNT=0
WARN_COUNT=0

pass() { echo "  OK  $1"; PASS_COUNT=$((PASS_COUNT + 1)); }
warn() { echo "  AVISO $1"; WARN_COUNT=$((WARN_COUNT + 1)); }
fail() { echo "  FALHA $1"; exit 1; }

export_binary() {
  local label="$1"
  local url="$2"
  local out="$3"
  local magic_kind="$4"
  local code
  code=$(curl -s -o "$out" -w "%{http_code}" "$url" "${AUTH[@]}")
  [[ "$code" == "200" ]] || fail "${label} (HTTP ${code})"
  case "$magic_kind" in
    xlsx|xlsm)
      local magic
      magic=$(head -c 2 "$out" | od -An -tx1 | tr -d ' ')
      [[ "$magic" == "504b" ]] || fail "${label} — arquivo não é ZIP/xlsx/xlsm"
      ;;
    pdf)
      local magic
      magic=$(head -c 4 "$out")
      [[ "$magic" == "%PDF" ]] || fail "${label} — arquivo não é PDF"
      ;;
    json)
      python3 -c "import json; json.load(open('$out'))" 2>/dev/null || fail "${label} — JSON inválido"
      ;;
  esac
  pass "$label"
}

echo "=== B12 — piloto orçamento §4 — ${API_BASE} ==="

code=$(curl -s -o /dev/null -w "%{http_code}" "${API_BASE}/health")
[[ "$code" == "200" ]] || fail "/health ($code)"
pass "/health"

login=$(curl -s -X POST "${API_BASE}/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"${USER}\",\"password\":\"${PASS}\"}")
token=$(echo "$login" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || true)
[[ -n "$token" ]] || fail "login: $login"
pass "login"

AUTH=(-H "Authorization: Bearer ${token}")

# 4.1 — sessão piloto (esqueleto B12)
session=$(curl -s -X POST \
  "${API_BASE}/pricing/budget/new-from-skeleton?skeleton_id=sk-b12-piloto-passarela&projeto=Obra+Piloto+B12+Campo&obra_type=RF" \
  "${AUTH[@]}")
sid=$(echo "$session" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id',''))" 2>/dev/null || true)
[[ -n "$sid" ]] || fail "criar sessão piloto: $session"
rows=$(echo "$session" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('rows',[])))" 2>/dev/null || echo 0)
[[ "${rows:-0}" -ge 4 ]] || fail "WBS piloto com poucas linhas (${rows})"
pass "4.1 sessão piloto WBS (${rows} linhas, session_id=${sid:0:8}…)"

# 4.2 — price_bank
refs=$(curl -s "${API_BASE}/pricing/sync/bank/references" "${AUTH[@]}")
ref_count=$(echo "$refs" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('references',[])))" 2>/dev/null || echo 0)
if [[ "${ref_count:-0}" -ge 1 ]]; then
  pass "4.2 price_bank (${ref_count} referências)"
else
  warn "4.2 price_bank vazio — rode make index-price-bases"
fi

# 4.3 — busca CPU
if [[ "${ref_count:-0}" -ge 1 ]]; then
  search=$(curl -s "${API_BASE}/pricing/sync/bank/open-compositions/search?q=concreto&uf=SP&limit=3" "${AUTH[@]}")
  hits=$(echo "$search" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('items', d.get('results',[]))))" 2>/dev/null || echo 0)
  if [[ "${hits:-0}" -ge 1 ]]; then
    pass "4.3 busca CPU (concreto → ${hits} resultados)"
  else
    warn "4.3 busca CPU sem resultados"
  fi
else
  warn "4.3 busca CPU ignorada (sem price_bank)"
fi

# 4.4 — lançar serviço + cronograma + ComD/SemD na sessão
etapa_code=$(echo "$session" | python3 -c "
import sys, json
rows = json.load(sys.stdin).get('rows') or []
for r in rows:
    if r.get('row_type') == 'ETAPA' and int(r.get('level') or 0) == 0:
        print(r.get('code', '1'))
        break
else:
    print('1')
" 2>/dev/null || echo "1")

added=$(curl -s -X POST "${API_BASE}/pricing/budget/${sid}/services" \
  -H "Content-Type: application/json" "${AUTH[@]}" \
  -d "{\"etapa_code\":\"${etapa_code}\",\"code\":\"PILOTO-001\",\"description\":\"Serviço piloto campo B12\",\"unit\":\"vb\",\"price\":1500,\"source\":\"manual\",\"quantity\":2}")
added_ok=$(echo "$added" | python3 -c "import sys,json; d=json.load(sys.stdin); print(1 if d.get('session_id') else 0)" 2>/dev/null || echo 0)
[[ "$added_ok" == "1" ]] || fail "4.4 lançar serviço: $added"
pass "4.4 serviço lançado na etapa ${etapa_code}"

sync=$(curl -s -X POST "${API_BASE}/pricing/budget/${sid}/schedule/sync" "${AUTH[@]}")
sync_ok=$(echo "$sync" | python3 -c "import sys,json; d=json.load(sys.stdin); print(1 if d.get('schedule',{}).get('tasks') else 0)" 2>/dev/null || echo 0)
if [[ "$sync_ok" == "1" ]]; then
  tasks=$(echo "$sync" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('schedule',{}).get('tasks',[])))" 2>/dev/null || echo 0)
  pass "4.4 cronograma sincronizado (${tasks} tarefas)"
else
  warn "4.4 cronograma sem tarefas após sync"
fi

got=$(curl -s "${API_BASE}/pricing/budget/${sid}" "${AUTH[@]}")
has_semd=$(echo "$got" | python3 -c "
import sys, json
rows = json.load(sys.stdin).get('rows') or []
print(1 if any(r.get('total_price_semd') is not None or r.get('unit_price_semd') is not None for r in rows) else 0)
" 2>/dev/null || echo 0)
if [[ "$has_semd" == "1" ]]; then
  pass "4.4 ComD/SemD presentes na sessão (total_price_semd / unit_price_semd)"
else
  warn "4.4 ComD/SemD — linhas sem coluna SemD (obra só manual pode não ter SemD)"
fi

# Salvar no banco
saved=$(curl -s -X POST "${API_BASE}/pricing/budget/saved" \
  -H "Content-Type: application/json" "${AUTH[@]}" \
  -d "{\"title\":\"Obra Piloto B12 Campo\",\"payload\":$(echo "$got" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin)))")}")
db_id=$(echo "$saved" | python3 -c "import sys,json; print(json.load(sys.stdin).get('db_id',''))" 2>/dev/null || true)
[[ -n "$db_id" ]] || fail "salvar orçamento: $saved"
pass "persistência POST /pricing/budget/saved (db_id=${db_id:0:8}…)"

# BDI edital
bdi=$(curl -s -X PATCH "${API_BASE}/pricing/budget/${sid}/bdi" \
  -H "Content-Type: application/json" "${AUTH[@]}" \
  -d '{"obra_type":"RF","profile_id":"seminf_table"}')
bdi_ok=$(echo "$bdi" | python3 -c "import sys,json; d=json.load(sys.stdin); print(1 if d.get('session_id') else 0)" 2>/dev/null || echo 0)
[[ "$bdi_ok" == "1" ]] && pass "PATCH BDI edital" || warn "BDI: $bdi"

# 4.5 — exports Excel/PDF
tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT

export_binary "4.5 Excel orc_sintetico" \
  "${API_BASE}/pricing/budget/${sid}/export/xlsx/orc_sintetico" \
  "${tmpdir}/orc_sintetico.xlsx" xlsx

export_binary "4.5 PDF orc_sintetico" \
  "${API_BASE}/pricing/budget/${sid}/export/pdf/orc_sintetico" \
  "${tmpdir}/orc_sintetico.pdf" pdf

export_binary "4.5 Excel orc_analitico" \
  "${API_BASE}/pricing/budget/${sid}/export/xlsx/orc_analitico" \
  "${tmpdir}/orc_analitico.xlsx" xlsx

export_binary "4.5 PDF orc_analitico" \
  "${API_BASE}/pricing/budget/${sid}/export/pdf/orc_analitico" \
  "${tmpdir}/orc_analitico.pdf" pdf

export_binary "4.5 Excel curva_abc" \
  "${API_BASE}/pricing/budget/${sid}/export/xlsx/curva_abc" \
  "${tmpdir}/curva_abc.xlsx" xlsx

export_binary "4.5 PDF curva_abc" \
  "${API_BASE}/pricing/budget/${sid}/export/pdf/curva_abc" \
  "${tmpdir}/curva_abc.pdf" pdf

export_binary "4.5 Excel mcq" \
  "${API_BASE}/pricing/budget/${sid}/export/xlsx/mcq" \
  "${tmpdir}/mcq.xlsx" xlsx

export_binary "4.5 PDF mcq" \
  "${API_BASE}/pricing/budget/${sid}/export/pdf/mcq" \
  "${tmpdir}/mcq.pdf" pdf

if [[ "$sync_ok" == "1" ]]; then
  export_binary "4.5 Excel cronograma" \
    "${API_BASE}/pricing/budget/${sid}/export/xlsx/cronograma" \
    "${tmpdir}/cronograma.xlsx" xlsx
  export_binary "4.5 PDF cronograma" \
    "${API_BASE}/pricing/budget/${sid}/export/pdf/cronograma" \
    "${tmpdir}/cronograma.pdf" pdf
fi

# 4.U5 — PPD oficial .xlsm (B19/B23) — requer templates em planilhas-exemplos/
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PPD_TEMPLATE_AVAILABLE=0
for candidate in \
  "${ROOT_DIR}/planilhas-exemplos/ppd_seminf_abril_2026.xlsm" \
  "${ROOT_DIR}/planilhas-exemplos/00_MOD_MC_OR_R00-Nivel-1-2-Abril2026-10-06-2026v8.1.xlsm" \
  "${ROOT_DIR}/planilhas-exemplos/19_PPD_MC_OR_R01-Nivel-1-2-Marco2026-14-05-2026.xlsm"
do
  if [[ -f "$candidate" ]]; then
    PPD_TEMPLATE_AVAILABLE=1
    break
  fi
done

if [[ "$PPD_TEMPLATE_AVAILABLE" == "1" ]]; then
  export_binary "4.U5 PPD oficial .xlsm" \
    "${API_BASE}/pricing/budget/${sid}/export/xlsm?sync=true" \
    "${tmpdir}/ppd_oficial.xlsm" xlsm
else
  warn "4.U5 PPD oficial .xlsm — templates ausentes em planilhas-exemplos/ (ppd_seminf_abril_2026, v8.1 ou R01)"
fi

# 4.U6 — compliance-pack.json (B22/B23)
export_binary "4.U6 compliance-pack.json" \
  "${API_BASE}/pricing/budget/${sid}/export/compliance-pack.json" \
  "${tmpdir}/compliance_pack.json" json

# BDI validação edital (B26)
bdi_val=$(curl -s "${API_BASE}/pricing/budget/${sid}/bdi/validation" "${AUTH[@]}")
bdi_status=$(echo "$bdi_val" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || true)
[[ -n "$bdi_status" ]] && pass "BDI validação edital (status=${bdi_status})" || warn "BDI validação: $bdi_val"

echo ""
echo "Resultado: piloto §4 validado — ${PASS_COUNT} OK, ${WARN_COUNT} aviso(s)"
echo "Marque §4 em docs/e2e_validation_checklist.md (data $(date -I), ambiente local/API)"
