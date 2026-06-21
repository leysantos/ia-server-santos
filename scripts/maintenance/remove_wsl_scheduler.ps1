# Remove a tarefa agendada de backup WSL (obsoleto)
#
# Opção A — cole no PowerShell (funciona de qualquer pasta):
#   $n = "Backup Automático WSL"; if (Get-ScheduledTask -TaskName $n -EA SilentlyContinue) { Unregister-ScheduledTask -TaskName $n -Confirm:$false; "Removida: $n" } else { "Tarefa não encontrada: $n" }
#
# Opção B — caminho completo via WSL (ajuste Ubuntu se sua distro for outra):
#   powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\eng_fsantos\projetos\ia-server-santos\scripts\maintenance\remove_wsl_scheduler.ps1"

$ErrorActionPreference = "Stop"
$taskName = "Backup Automático WSL"

if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "Tarefa removida: $taskName" -ForegroundColor Green
} else {
    Write-Host "Tarefa não encontrada: $taskName (já removida ou nunca criada)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Backup WSL completo foi descontinuado." -ForegroundColor Cyan
Write-Host "Use backups seletivos: app, database, knowledge, faiss via /settings/maintenance"
Write-Host "Restore: make restore STAMP=YYYYMMDD-HHMMSS"
