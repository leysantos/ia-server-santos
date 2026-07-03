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
make test-budget-e2e   # Playwright smoke /budget (frontend, mocks API)
make test-budget-pilot # pytest fluxo piloto B12 (sem API externa)
make test-ci           # CI local: pytest subset orçamento + Playwright /budget
make test-ci-backend   # só pytest (2 fases: unit orçamento + smoke/piloto)
make validate-budget-pilot  # API :8000 — sessão, save, export, BDI
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

> **Automatizado (sem UI):**  
> `make test-budget-pilot` — pytest incl. `test_pilot_section4_field_checklist` (§4.4–4.5 exports + cronograma)  
> `make validate-budget-pilot` — API live `:8000` (requer `make api`) — cobre §4.1–4.5 ponta a ponta  
> Esqueleto recomendado: **PASSARELA PEDESTRE — PILOTO B12** (`sk-b12-piloto-passarela`)

| # | Passo | OK | Data | Notas |
|---|-------|----|------|-------|
| 4.1 | `/budget` — criar sessão piloto (esqueleto B12 ou reforma quadra) | | | `make test-budget-pilot` · `validate-budget-pilot` |
| 4.2 | Sync SINAPI ou SICRO referência ativa | | | `make validate-price-bases` · aviso se vazio |
| 4.3 | Busca CPU retorna composições | | | Aba Busca CPU · `RUN_BUDGET_PILOT_LIVE=1 make test-budget-pilot` |
| 4.4 | Orç. sintético + analítico preenchidos; serviço lançado; cronograma sync; ComD/SemD | | | `test_pilot_section4_field_checklist` |
| 4.5 | Export Excel/PDF — sintético, analítico, MCQ, **curva ABC**, cronograma | | | `make validate-budget-pilot` (8–10 arquivos) |

### UI manual (complementar ao script)

| # | Passo | OK | Data | Notas |
|---|-------|----|------|-------|
| 4.U1 | Novo orçamento → esqueleto passarela B12 na UI | | | `/budget` → Cadastrar modelo |
| 4.U2 | Busca CPU → lançar na etapa (painel B13) | | | Playwright `test-budget-e2e` cobre mock |
| 4.U3 | Abas Cronograma + Curva ABC visualmente corretas | | | Gantt + classificação Pareto |
| 4.U4 | Cronograma sync + curvas físico-financeiro | | | Aba Dados → `BudgetPilotChecklist` |
| 4.U5 | Export `.xlsm` oficial PPD SEMINF | | | Toolbar ou checklist 4.U5 |
| 4.U6 | Compliance-pack + checklist L1–L7 | | | Aba Dados → painel compliance |
| 4.U7 | Proposta comercial com margem % | | | `BudgetCommercialPanel` + export |
| 4.U∑ | Export JSON assinatura do checklist | | | Botão "Exportar assinatura" no checklist |

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
