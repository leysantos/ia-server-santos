#!/usr/bin/env bash
# Restore guiado por stamp — espelha POST /maintenance/restore
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then
  PYTHON="python3"
fi

STAMP="${1:-${STAMP:-}}"
TARGETS="${2:-${TARGETS:-database,knowledge,faiss}}"
FROM_DRIVE="${FROM_DRIVE:-true}"
DRY_RUN="${DRY_RUN:-false}"

if [[ -z "${STAMP}" ]]; then
  echo "Uso:"
  echo "  make restore STAMP=YYYYMMDD-HHMMSS"
  echo "  make restore STAMP=YYYYMMDD-HHMMSS TARGETS=database,faiss"
  echo "  bash scripts/maintenance/restore.sh YYYYMMDD-HHMMSS [database,knowledge,faiss,app]"
  echo ""
  echo "Variáveis: DRY_RUN=true  FROM_DRIVE=false"
  exit 1
fi

cd "${ROOT}/backend"
export PYTHONPATH=.

exec "${PYTHON}" -c "
import json, sys
from core.maintenance.restore_service import MaintenanceRestoreService

stamp = sys.argv[1]
targets = [t.strip() for t in sys.argv[2].split(',') if t.strip()]
from_drive = sys.argv[3].lower() in ('1', 'true', 'yes')
dry_run = sys.argv[4].lower() in ('1', 'true', 'yes')

svc = MaintenanceRestoreService()
print('=== Inspeção ===')
print(json.dumps(svc.inspect_stamp(stamp, from_drive=from_drive), indent=2, ensure_ascii=False))
if dry_run:
    print('=== DRY RUN ===')
else:
    print('=== Restaurando ===')

def progress(data):
    print(f\"[{data.get('percent', 0)}%] {data.get('message')}\")

result = svc.run_restore(
    stamp,
    targets,
    from_drive=from_drive,
    dry_run=dry_run,
    on_progress=progress,
)
print(json.dumps(result, indent=2, ensure_ascii=False))
if result.get('errors'):
    sys.exit(1)
" "${STAMP}" "${TARGETS}" "${FROM_DRIVE}" "${DRY_RUN}"
