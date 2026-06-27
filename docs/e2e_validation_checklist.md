# Checklist de validação E2E — IA Server Santos

> Evidência operacional para fechar Fase 2 (Project RAG, PCI Vision, orçamento piloto).  
> Marque cada item com data, responsável e observações após executar.

## Pré-requisitos

- [ ] `make api` e `npm run dev` (ou deploy) em execução
- [ ] PostgreSQL ativo (`make db-init` se necessário)
- [ ] Ollama com modelos mínimos: `phi3:mini` ou `qwen2.5-coder`, `nomic-embed-text`
- [ ] Auth habilitada (`AUTH_ENABLED=true`) para testes multi-usuário
- [ ] Hardening M1: `JWT_SECRET` e senhas seed alterados antes de tunnel prolongado

## M2 — Smoke automatizado

```bash
make test-backend   # inclui test_smoke_e2e.py, test_project_rag_e2e.py e test_conversation_user_scope.py
make test-project-rag   # só R10 (upload → FAISS → chat), sem Ollama
make smoke-e2e      # API em :8000
make validate-project-rag   # R10 contra API + Ollama (indexação real)
make validate-price-bases   # Fase 2 — price_bank + composition FAISS + prévia CPU
make validate-lan   # LAN + proxy /api-backend
```

| Teste | Comando / rota | Esperado |
|-------|----------------|----------|
| Health API | `GET /health` | 200, `status` ok |
| Login | `POST /auth/login` | `access_token` |
| Conversas isoladas | `test_conversation_user_scope` | dev não vê conversa do admin |
| Proxy LAN | `GET /api-backend/health` via :3000 | 200 |

## 1 — Auth e chat por usuário

| # | Passo | OK | Data | Notas |
|---|-------|----|------|-------|
| 1.1 | Login `admin` → `/chat` | | | |
| 1.2 | Enviar mensagem com persist → nova conversa na sidebar | | | |
| 1.3 | Login `dev_user1` → lista de conversas **não** mostra conversa do admin | | | |
| 1.4 | `dev_user1` tenta `GET /conversations/{id_admin}` → 404 | | | |
| 1.5 | Histórico `/history` filtrado por usuário | | | |

## 2 — Project RAG (upload + chat contextual)

| # | Passo | OK | Data | Notas |
|---|-------|----|------|-------|
| 2.1 | Criar projeto em `/projects` | | | |
| 2.2 | Upload PDF/DXF (LAN: via UI em `http://<host>:3000`) | | | |
| 2.3 | Reindexar RAG se necessário | | | |
| 2.4 | Chat com `project_id` — resposta cita trechos do arquivo | | | |
| 2.5 | Busca workspace `GET /workspace/search?q=...` retorna projeto | | | |

## 2b — Bases de preço SINAPI (Fase 2 item 2)

> SINAPI/TCPO vivem em `price_bank` + FAISS `budget/compositions` — **não** em `knowledge/cost_index`.

```bash
make index-price-bases      # reindexa provider + FAISS a partir da referência ativa
make validate-price-bases   # API: inventário + prévia composição 95995
```

| # | Passo | OK | Data | Notas |
|---|-------|----|------|-------|
| 2b.1 | `/settings/price-bases` — períodos SINAPI importados | | | |
| 2b.2 | `make validate-price-bases` passa | | | |
| 2b.3 | `/budget` — busca CPU retorna composições | | | |

## 3 — PCI / Vision Analysis

| # | Passo | OK | Data | Notas |
|---|-------|----|------|-------|
| 3.1 | Projeto com planta PDF ou imagem PCI | | | |
| 3.2 | Abrir `/projects/{id}/vision` | | | |
| 3.3 | Executar análise (modo PCI) — SSE completa sem erro | | | |
| 3.4 | JSON/checklist IT-11 visível na UI | | | |
| 3.5 | Export DOCX gerado (se habilitado) | | | |

## 4 — Orçamento piloto

| # | Passo | OK | Data | Notas |
|---|-------|----|------|-------|
| 4.1 | `/budget` — criar sessão piloto | | | |
| 4.2 | Sync SINAPI ou SICRO referência ativa | | | |
| 4.3 | Busca CPU retorna composições | | | |
| 4.4 | Orç. sintético + analítico preenchidos | | | |
| 4.5 | Export Excel/PDF de pelo menos um documento | | | |

## 5 — Copilot e AED (M3)

| # | Passo | OK | Data | Notas |
|---|-------|----|------|-------|
| 5.1 | `/copilot` — prompt estrutural simples | | | |
| 5.2 | Evaluation v2 na resposta | | | |
| 5.3 | `/aed` — problema de dimensionamento | | | |
| 5.4 | Relatório JSON com `selection` e `report` | | | |

## 6 — Exposição rede (opcional)

| # | Passo | OK | Data | Notas |
|---|-------|----|------|-------|
| 6.1 | Quick Tunnel em `/settings/access` | | | |
| 6.2 | Login externo `*.trycloudflare.com` | | | |
| 6.3 | Upload na URL externa (proxy same-origin) | | | |
| 6.4 | Logs sem `AUTH HARDENING` warnings críticos | | | |

## Registro de execução

| Execução | Responsável | Ambiente | Resultado global |
|----------|-------------|----------|------------------|
| | | local / LAN / tunnel | |

---

**Referências:** `docs/project_state.md` (seção 5 runbook, M1–M5), `make test-cov`, `scripts/smoke_e2e.sh`
