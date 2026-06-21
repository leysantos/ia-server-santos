# Backup WSL — descontinuado

O backup completo do WSL (`wsl --export`) foi **removido** do IA Server Santos.

## Por quê?

- **~69 GB** por arquivo, pouco valor vs backups seletivos (~1–2 GB)
- **Modelos Ollama não migram de forma confiável** — ficam em `~/.ollama` e dependem de GPU/drivers
- **Restore em hardware diferente** (ex.: notebook → servidor RTX) costuma falhar ou exigir o mesmo PC
- **Só faria sentido** como clone 1:1 do mesmo Avell Storm 460 — mesmo CPU/GPU/drivers

## O que usar agora

| Backup | Conteúdo | Restore |
|--------|----------|---------|
| app | Código | `make restore STAMP=… TARGETS=app` + `make setup` |
| database | PostgreSQL | `make restore STAMP=… TARGETS=database` |
| knowledge | Catálogo + sidecars (+ PDFs opcional) | incluído no restore padrão |
| faiss | Índices vetoriais | incluído no restore padrão |

```bash
make restore STAMP=20260621-165953
make restore STAMP=20260621-165953 TARGETS=database,faiss DRY_RUN=true
```

UI: **Configurações → Manutenção → Restaurar backup**

## Remover agendador Windows (uma vez)

**Opção mais fácil** — cole no PowerShell (Admin ou normal):

```powershell
$n = "Backup Automático WSL"
if (Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue) {
  Unregister-ScheduledTask -TaskName $n -Confirm:$false
  Write-Host "Removida: $n" -ForegroundColor Green
} else {
  Write-Host "Tarefa não encontrada (já removida)" -ForegroundColor Yellow
}
```

**Ou** com caminho completo do repo no WSL:

```powershell
powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\eng_fsantos\projetos\ia-server-santos\scripts\maintenance\remove_wsl_scheduler.ps1"
```

> Não use `scripts\maintenance\...` a partir de `C:\Windows\System32` — esse caminho relativo não existe lá.

Arquivos antigos no Drive (`Backups_WSL/*.tar`) podem ser apagados manualmente para liberar espaço.
