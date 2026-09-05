# Checklist — Máquina nova (restore do IA Server Santos)

Guia para reerguer o sistema a partir do backup seletivo no **Google Drive**  
(`G:\Meu Drive\Backups_IA_Server\`), sem clone WSL completo.

Stamp de referência (exemplo): `20260801-145931`  
Substitua pelo stamp mais recente em `logs/manifest-*.json` ou na UI **Manutenção**.

---

## Antes de começar (máquina atual)

- [ ] Backup com alvos **app + database + knowledge + faiss** (retenção **N ≥ 3**)
- [ ] Confirmar no Drive as pastas `app/`, `database/`, `knowledge/`, `faiss/`, `logs/` com o mesmo stamp
- [ ] Copiar à parte (fora do tar): `backend/.env`, `frontend/.env.local` (se houver)
- [ ] **Só se precisar dos Excel de orçamento já gerados:** o dump do banco traz a *ficha* do orçamento (itens, valores), mas os arquivos `.xlsm` ficam no **MinIO** (ou pasta local), não no SQL. Sem copiar isso, na máquina nova o orçamento abre na UI, porém “Baixar .xlsm” / PDF da planilha pode precisar regenerar o workbook. Se você sempre regenera o Excel, **pode ignorar este item**.
- [ ] Anotar modelos Ollama (`ollama list` — ver §7) e letra do Drive (`G:` etc.)

---

## Hardware / SO alvo (recomendado)

Alinhado à operação atual (WSL2 + GPU NVIDIA + Docker):

| Item | Mínimo | Ideal (multiacesso LAN) |
|------|--------|-------------------------|
| SO | Windows 11 + WSL2 Ubuntu | Idem |
| GPU | NVIDIA 12 GB VRAM | 16–24 GB |
| RAM | 32 GB | 64 GB |
| Disco | 1 TB NVMe | 2 TB+ |
| Rede | Gigabit LAN | Idem |

---

## 10 passos na máquina nova

### 1) Base do sistema

- [ ] Instalar **Windows 11**, drivers NVIDIA, **WSL2** (Ubuntu), **Docker Desktop** (integração WSL), **Git**, **Node 18+**, **Python 3.11+**
- [ ] Instalar **Ollama** no WSL (ou Windows, com `OLLAMA_BASE_URL` apontando certo)
- [ ] Instalar cliente Google Drive / File Stream e montar a pasta de backups (ex.: `G:\Meu Drive\Backups_IA_Server`)

### 2) Obter o código

**Opção A — do GitHub (preferível se o repo estiver atualizado):**

```bash
cd ~
git clone https://github.com/leysantos/ia-server-santos.git
cd ia-server-santos
```

**Opção B — do tar `app` do Drive:**

```bash
# No WSL — ajuste a letra/caminho do Drive
mkdir -p ~/projetos && cd ~/projetos
tar -xzf "/mnt/g/Meu Drive/Backups_IA_Server/app/ia-server-santos-app-STAMP.tar.gz"
# Se o tar extrair frontend/, backend/, etc. na pasta atual, renomeie/mova para ia-server-santos/
```

### 3) Dependências do monorepo

```bash
cd ~/projetos/ia-server-santos   # ou caminho real
make setup
# = setup-backend (.venv + pip) + setup-frontend (npm install)
```

### 4) Segredos e config

```bash
cp backend/.env.example backend/.env
# Colar JWT_SECRET, senhas seed, GEMINI_*, DB_* da máquina antiga
# Ajustar caminhos se necessário

# Frontend (LAN típico)
cp frontend/.env.lan.example frontend/.env.local
```

Configurar manutenção (UI depois, ou criar `backend/data/maintenance/config.json`):

- `backup_drive_win`: `G:\Meu Drive\Backups_IA_Server`
- `backup_staging_dir`: `/mnt/c/Backups/.ia-server-staging`
- `keep_latest_sets`: `3`

### 5) Infra Docker (Postgres + Redis + MinIO)

```bash
make docker-up
# Aguardar healthy: postgres :5433, redis :6379, minio :9000
```

### 6) Restaurar database + knowledge + FAISS

Dry-run primeiro:

```bash
make restore STAMP=20260801-145931 DRY_RUN=true
```

Restore real (padrão = database, knowledge, faiss; lê do Drive via PowerShell/WSL):

```bash
make restore STAMP=20260801-145931
# ou explícito:
make restore STAMP=20260801-145931 TARGETS=database,knowledge,faiss
```

Se o Drive não estiver montado no Windows da máquina nova, copie o stamp para o staging e use `FROM_DRIVE=false`.

> Restore de **app** só se não clonou do Git:  
> `make restore STAMP=… TARGETS=app` e depois `make setup` de novo.

### 7) Modelos Ollama

Inventário atual da Avell (`ollama list`, 2026-08-01) — espelhar na máquina nova (~72 GB no disco):

| Modelo | Tamanho | Papel típico |
|--------|---------|--------------|
| `nomic-embed-text:latest` | 274 MB | Embeddings RAG |
| `deepseek-coder:latest` | 776 MB | Código leve |
| `phi3:mini` | 2.2 GB | Chat leve (default chat) |
| `mistral:7b` | 4.4 GB | Chat alternativo |
| `qwen2.5-coder:latest` | 4.7 GB | Orçamento / código |
| `qwen3:8b` | 5.2 GB | Fallback engenharia |
| `gemma3:12b` | 8.1 GB | Visão / PCI |
| `deepseek-r1:14b` | 9.0 GB | Raciocínio |
| `qwen3:14b` | 9.3 GB | Engenharia (default eng) |
| `gemma4:latest` | 9.6 GB | Modelo geral |
| `qwen3-coder:latest` | 18 GB | Coder pesado (puxe por último) |

```bash
ollama pull nomic-embed-text:latest
ollama pull deepseek-coder:latest
ollama pull phi3:mini
ollama pull mistral:7b
ollama pull qwen2.5-coder:latest
ollama pull qwen3:8b
ollama pull gemma3:12b
ollama pull deepseek-r1:14b
ollama pull qwen3:14b
ollama pull gemma4:latest
ollama pull qwen3-coder:latest
```

Mínimo para subir chat + RAG + eng: `nomic-embed-text`, `phi3:mini`, `qwen3:8b`, `qwen3:14b`.  
Conferir: `ollama list` deve bater com a tabela acima.

### 8) Bases de preço (SINAPI / SICRO)

O tar **app** atual **não** inclui `price_bank`. Na máquina nova:

- Sync pela UI **Configurações → Bases de preço**, ou
- `make index-price-bases` / sync API após baixar os arquivos oficiais

Sem isso o orçamento sobe, mas sem composições locais.

### 9) Subir API + frontend

```bash
# Terminal 1
make api

# Terminal 2
cd frontend && npm run build && npm run start
# ou em lab: npm run dev
```

LAN (Windows → WSL), se for servidor de equipe:

```powershell
# PowerShell Admin, na raiz do repo (caminho Windows/WSL)
.\scripts\setup_wsl_lan_access.ps1
```

### 10) Validar

- [ ] `GET http://localhost:8000/health` — DB + Ollama ok  
- [ ] Login em `http://localhost:3000/login` (trocar senhas seed)  
- [ ] Chat com streaming  
- [ ] Abrir um orçamento / projeto conhecido do dump  
- [ ] `make validate-lan` se for uso em rede  
- [ ] Manutenção → **Inspecionar** o stamp e (opcional) novo backup de teste  

---

## Ordem rápida (cola)

```text
1. WSL + Docker + NVIDIA + Drive
2. git clone (ou tar app)
3. make setup
4. .env / .env.local
5. make docker-up
6. make restore STAMP=… 
7. ollama pull …
8. sync price_bank
9. make api + frontend
10. health + login + smoke
```

---

## O que este checklist NÃO restaura

| Item | Ação |
|------|------|
| Modelos Ollama (~/.ollama) | `ollama pull` |
| `.venv` / `node_modules` | `make setup` |
| `backend/.env` secrets | Copiar manualmente |
| price_bank SINAPI/SICRO | Sync / import |
| Objetos MinIO (`.xlsm` de orçamento, uploads workflow) | Opcional — só se quiser os Excel já gerados; senão regenera na UI |
| Fotos laudos / workflow em `backend/data/` | Cópia manual se precisar |
| Clone WSL 1:1 | Descontinuado — ver `backup-wsl/README.md` |

---

## Referências

- Control plane: `docs/project_state.md` §5 (Runbook)
- UI: `/settings/maintenance`
- CLI: `scripts/maintenance/run_backup.sh` · `scripts/maintenance/restore.sh`
- `make restore STAMP=YYYYMMDD-HHMMSS [TARGETS=…] [DRY_RUN=true]`
