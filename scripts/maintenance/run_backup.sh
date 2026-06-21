#!/usr/bin/env bash
# Backup manual via CLI — espelha POST /maintenance/backup
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON="${ROOT}/.venv/bin/python"
TARGETS="${1:-app,database,knowledge,faiss}"

cd "${ROOT}/backend"
export PYTHONPATH=.
exec "${PYTHON}" -c "
import json, sys
from core.maintenance.backup_service import MaintenanceBackupService

targets = sys.argv[1].split(',') if len(sys.argv) > 1 else ['app', 'database', 'knowledge', 'faiss']
svc = MaintenanceBackupService()
print('Inicializando pastas...')
print(json.dumps(svc.init_folders(), indent=2, ensure_ascii=False))
print('Executando backup:', targets)

def progress(data):
    print(f\"[{data.get('percent', 0)}%] {data.get('message')}\")

result = svc.run_backup(targets, on_progress=progress)
print(json.dumps(result, indent=2, ensure_ascii=False))
" "$TARGETS"
