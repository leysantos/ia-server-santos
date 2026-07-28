# 🧠 IA SERVER SANTOS — PROJECT STATE (CONTROL PLANE)

> **Painel de controle de engenharia do sistema** — fonte única de verdade sobre arquitetura, status, riscos e roadmap.  
> Atualizar este documento a cada marco relevante (feature merge, mudança de infra, decisão arquitetural).

| Campo | Valor |
|-------|-------|
| **Versão do sistema** | 1.0.0 |
| **Última atualização** | 2026-07-27 (Laudos follow-up · órfãos · ART live · PAdES flag) |
| **Próximo foco** | Piloto UI §4.U `/budget` · Laudos PAdES com cert A1 em produção |
| **Marco atual** | M1–M8 ✅ · Orçamento B1–B30 ✅ |
| **Repositório** | [github.com/leysantos/ia-server-santos](https://github.com/leysantos/ia-server-santos) |
| **Branch principal** | `main` |
| **Modo padrão de agentes** | Inteligente (`USE_INTELLIGENT_AGENTS=true`) |
| **Layout do repo** | Monorepo: `backend/` (Python) + `frontend/` (Next.js) |

---

# 📤 HANDOFF — RESUMO PARA GPT / NOVA SESSÃO

> Copie esta seção para contextualizar qualquer LLM sobre o estado atual do projeto.

## O que é

**IA Server Santos** — SaaS de engenharia civil multiagente: chat, orquestração multi-disciplina, Copilot de planejamento, AED (Autonomous Engineering Designer), RAG normativo (NBR), loops de auto-evolução. Stack: **FastAPI + PostgreSQL + Ollama local + FAISS + Next.js**.

## Estrutura do repositório

```
ia-server-santos/
├── backend/     ← todo Python (app, core, agents, memory, tests, scripts)
├── frontend/    ← Next.js (:3000)
├── docs/        ← este arquivo (control plane)
└── infra/docker ← PostgreSQL (:5433)
```

**Subir:** `cd backend && uvicorn app.main:app --reload --port 8000` · `cd frontend && npm run dev` · `make api` / `make db-init` na raiz.

**Acesso equipe:** LAN `http://172.22.3.234:3000` (portproxy Windows + proxy `/api-backend`) · externo Quick Tunnel em `/settings/access` · runbook completo na **seção 5** · análise geral na **seção 8**.

## O que já funciona (produção local)

| Área | Status |
|------|--------|
| API REST (`:8000`) | 🟢 chat, chat/stream, orchestrate, copilot, aed, feedback, history, health, **knowledge/**, **workspace/** |
| 15 agentes inteligentes + ChatAgent | 🟢 RAG + Ollama via `BaseAgentIntelligent` |
| Intent Layer v2 | 🟢 chat / engenharia / mixed + SSE streaming |
| Orchestrator v1 + Engineering Orchestrator | 🟢 multi-disciplina · NBR≠SINAPI · ContextGraph |
| Copilot v1 + Evaluation v2 + Self-Improving | 🟢 |
| AED v1 + Structural Selector | 🟢 pipeline completo, persistência `aed_runs` |
| SIE v1 (Structural Intelligence) | 🟢 só disciplina ESTRUTURAL via `dispatch_adapter` |
| Model Router + Model Evaluation Loop | 🟢 implementados, **off por default** |
| Evolution Loop v1 | 🟢 implementado, **off por default** |
| Agent Generation Loop v1 | 🟢 proposta/sandbox/promotion gate, **off por default** |
| Learning Loop v1 + v2 | 🟢 feedback + auto-tune prompts (v2 opt-in) |
| RAG v2 pipeline | 🟢 **~14.5k chunks NBR** · cobertura ~90% códigos · OCR Tesseract ativo · retry pendentes em andamento |
| **Sync bases de preço** | 🟢 barra unificada · tipos custom · download SINAPI via portal `categoria_888` (API SharePoint + retificações) · **SICRO DNIT** (parser `.7z`/pasta · sync por UF ou todas as regiões · `BR-SICRO-{UF}-YYYY-MM`) · inventário · **sem catálogo RAG** |
| Knowledge Layer multi-base | 🟢 FAISS por base (NBR, TDR, catálogos…) — SINAPI/TCPO **fora** do catálogo/FAISS RAG |
| **Norm Pack Studio** | 🟢 Gap analysis por pacote (arquitetura, documentação, PCI, estrutural) · `/settings/norm-packs` · API `/knowledge/norm-packs/*` · só PDF licenciado / legislação pública |
| **Importação em lote NBR/NR** | 🟢 `/settings/imports` · pasta ou multi-PDF · classificação automática (**IN SICRO → ORÇAMENTO**) · SSE progresso **por arquivo na indexação FAISS** · **embed batch Ollama + indexação parcial** (chunks resilientes) · job `norm_bulk` no Console · **CSV auditoria pós-lote** · CLI `scripts/ingest_nbr_folder.py` |
| **Manutenção / Backup** | 🟢 `/settings/maintenance` · backup app, PostgreSQL, knowledge, FAISS → Google Drive · **restore** por stamp (`make restore STAMP=…`, UI e `/maintenance/restore`) · CLI `scripts/maintenance/run_backup.sh` · backup WSL completo **removido** |
| **Serviços / DevOps** | 🟢 `/settings/servers` · API `/devops/*` · status PostgreSQL/API/Ollama/Redis/MinIO · subir stack backend (Docker + db-init) · start/stop frontend e Celery · console bash com blocklist · API e frontend manual (`make api`, `npm run dev`) |
| Knowledge storage flat | 🟢 `knowledge/raw/documents/` + metadata sidecar + `catalog.jsonl` |
| RAG agent-aware | 🟢 15 agentes com escopo isolado — `USE_AGENT_SCOPED_RAG=true` |
| Engineering Orchestrator | 🟢 Separação NBR ↔ SINAPI — `USE_ENGINEERING_ORCHESTRATOR=true` |
| RAG performance | 🟢 Cache semântico, rerank leve, métricas latência — default ON |
| **Workspace (projetos + conversas)** | 🟢 CRUD projetos/conversas · busca · multi-turn · painel lateral no `/chat` |
| **Project RAG multi-formato** | 🟢 FAISS por projeto — PDF, Office, CSV, TXT, DXF, IFC, DWG, PNG/JPG/ZIP |
| **Project Review Engine** | 🟡 Fundação — digital twin, ingestão, OCR/BIM/CAD, agente, NCs, scoring, DOCX — `/projects/{id}/review` |
| **Vision Analysis** | 🟢 Vision Engine — OCR → RAG CBMAM (modo PCI) → `gemma3:12b` → JSON → `qwen3:14b` → DOCX · checklist IT-11/NT-03 · SSE · `/projects/{id}/vision` |
| **Workflow Projetos** | 🟡 Fase 3 — Wizard de Entrega (`/workflow/wizard`) · seleção manual arquivos · templates A4–A0 · nomenclatura `DISC-FLnn-TIPO-DESC-REV` · análise CAD/IA · GRD PDF · ZIP estruturado · Fase 2.1 (classificador, skip, presigned) mantida |
| **Operational Transparency** | 🟢 ActivityPanel global · Operations Console `/console` (SSE live + fila Ollama + log `norm_bulk`/`knowledge`) · timeline `/projects/{id}/activity` · `project_decisions` + auto-capture |
| **Orçamento `/budget`** | 🟢 **Produção interna alta** + **enterprise técnico** (B1–B30): 11 docs nativos + `proposta_comercial` + `.xlsm` oficial + **Lançar Preços** (import PDF hierárquico etapas/sub-etapas/composições · persistência imediata · abas PPD na mesma tela · Salvar/Editar/Excluir · matching SEMINF→SINAPI→SICRO→ORSE) · auditoria · tenant · lock · §8.1 |
| **Laudos de Vistoria `/inspection-reports`** | 🟢 **L1–L19 + follow-up** ✅: croqui · ART live · PAdES opcional · órfãos admin · mapa · metrologia · ensaios |
| Chat streaming UX | 🟢 SSE instantâneo (`connected`) + tokens ~60fps · **anexos no prompt** (PDF/planilha/imagem/CAD) em `/chat`, `/orchestrate`, `/copilot`, `/aed` + roteamento auto por tipo |
| Agente Geotecnia dedicado | 🟢 `GeotecniaIntelligentAgent` — NBR 6122/7185, classificação solo, A_min |
| Frontend | 🟢 `/chat`, `/projects`, `/inspection-reports`, `/budget`, `/mobile/*` (telefone), `/orchestrate`, `/copilot`, `/aed`, `/console`, `/history`, `/settings`, `/projects/{id}/workflow` |
| Auth SaaS | 🟢 JWT · middleware · papéis `admin` \| `dev_user` + **tipos customizados** · **permissões por módulo** (oculto/bloqueado) · `/settings/users` (**editar** + **excluir**/desativar) |

## Feature flags importantes (defaults)

| Flag | Default | Nota |
|------|---------|------|
| `USE_INTELLIGENT_AGENTS` | `true` | Agentes com LLM real |
| `USE_INTENT_LAYER` | `true` | Intent Layer no `/chat` |
| `USE_MODEL_ROUTER` | `false` | Roteamento LLM por task_type |
| `USE_MODEL_EVALUATION` | `false` | Comparação primary vs fallback |
| `USE_EVOLUTION_LOOP` | `false` | Auto-otimização modelos/prompts/RAG |
| `USE_AGENT_GENERATION` | `false` | Proposta controlada de novos agentes |
| `USE_KNOWLEDGE_ROUTER` | `false` | Multi-index FAISS (NBR, SINAPI, TCPO, TDR, catálogos) |
| `USE_AGENT_SCOPED_RAG` | `true` | RAG por agente — cada `agents/*.py` com escopo próprio |
| `USE_ENGINEERING_ORCHESTRATOR` | `true` | Orquestrador: engenharia (NBR) ≠ orçamento (SINAPI/TCPO) |
| `USE_RAG_SEMANTIC_CACHE` | `true` | Cache de top-K por query similar (cosine ≥ 0.92) |
| `USE_DISCIPLINE_KNOWLEDGE_ROUTER` | `false` | Router legado por disciplina (supersedido por agent-scoped) |
| `USE_DISCIPLINE_INGESTION` | `true` | Ingestão → `knowledge/raw/documents/` + sidecar `.knowledge.json` |
| `USE_TUNED_PROMPTS` | `false` | Prompts Learning v2 por disciplina |

## Modelos Ollama no WSL (instalados)

`gemma4:latest` · `deepseek-r1:14b` · `deepseek-coder:latest` · `mistral:7b` · `qwen2.5-coder:latest` · `phi3:mini` · `gemma3:12b` · `nomic-embed-text:latest` · `qwen3-coder:latest` · `qwen3:14b` · `qwen3:8b`

Config padrão: chat=`phi3:mini`/mistral · eng=`qwen3:14b` · fallback=`qwen3:8b` · embed=`nomic-embed-text`.  
Router sincroniza `model_map` com `ollama list` via `installed_model_registry.py` (`build_router_model_map`, `refresh_installed_models`).  
`GET /health` retorna lista dinâmica via Ollama; frontend exibe badge **WSL:** no `/chat`.

## Bloqueio principal

**Bases de custo — operacionais via `price_bank`, não via catálogo RAG**

NBRs: **~14.5k chunks** FAISS (90%+ cobertura). SINAPI/TCPO vivem em `knowledge/price_bank/BR-YYYY-MM/` + `composition_index` (orçamento). Sync **não** grava mais em `catalog.jsonl` nem indexa `cost_index`. Purge: `DELETE /pricing/sync/bank/faiss/sinapi` ou botão na UI. Import via UI ou API:

```bash
# Sync mês/ano específico (SSE)
curl -N -X POST http://localhost:8000/pricing/sync/sinapi/stream \
  -H 'Content-Type: application/json' \
  -d '{"uf":"SP","year":2026,"month":5,"index_faiss":true}'

# Listar referências / trocar ativa
curl http://localhost:8000/pricing/sync/bank/references
curl -X POST http://localhost:8000/pricing/sync/bank/active \
  -H 'Content-Type: application/json' -d '{"reference":"BR-2026-05"}'

# Prévia CPU por UF e período (código com `/` — ex. ORSE — usar query `code=`)
curl 'http://localhost:8000/pricing/sync/bank/composition?code=00084/ORSE&uf=SE&reference=BR-ORSE-2026-04'
curl 'http://localhost:8000/pricing/sync/bank/composition?code=95995&uf=AM&reference=BR-2026-05'
```

UI: `/settings/price-bases` → inventário por fonte (clique no período = prévia; sem badge “ativo”) · `/budget` → **Adicionar base** (SINAPI / DP/SEMINF / SICRO — tipo, UF, período) + **Editar**/**Remover** · aditivos usam a mesma base do orçamento original · **busca manual** e **composição por prompt** usam bases da sessão.

Dependências de indexação (knowledge): `pip install pypdf python-multipart openpyxl python-docx xlrd`  
Dependências de indexação (project RAG): `ezdxf ifcopenshell` (opcional CAD/BIM)

Ativar multi-index explícito (opcional): `USE_KNOWLEDGE_ROUTER=true`

**Regra arquitetural:** SINAPI/TCPO = **somente orçamento**. NBR = **somente engenharia**. Orquestrador garante separação mesmo com flags ON.

**Regra SINAPI — fórmula Caixa (CPU):** insumo → `preco_uf` (ISD/ICD/ISE) → `preco_regional_as` → `preco_sp`; composição → PROCX CSD/CCD/CSE **sem fallback SP**. Código: `sinapi_caixa_pricing.py`. Ex.: 95995/AM/03/2026 SemD — 1518 **512,50** · total **1.469,59**.

## Próximos passos (ordem recomendada)

1. **Hardening** — trocar `JWT_SECRET` e senhas seed antes de uso prolongado via Quick Tunnel
2. **Smoke E2E** — validar LAN: login → chat → upload projeto (`make validate-lan` + teste manual)
3. **Teste PCI** — projeto combate a incêndio: upload fotos/plantas → `/projects/{id}/vision` modo `pci`
4. Validar Operational Transparency end-to-end: orquestração → Console · orçamento salvo → timeline
5. Validar Project RAG end-to-end: upload DOCX/XLSX/IFC → reindex → `/chat?project=<id>`
6. Popular SINAPI/TCPO: `make index-price-bases` (price_bank → composition FAISS) — **não** `index_knowledge_bases --base sinapi`
7. Validar orçamento `/budget` em obra piloto (ComD/SemD, cronograma, export PPD)
8. Páginas frontend `/aed` e `/copilot`
9. `pytest-cov` + subset CI estável
10. Execution Planner (Orchestrator v2)

## Operational Transparency Layer (roadmap incremental)

> Direção "Agent-first" **sem rewrite** — expor pipelines já existentes (Intent SSE, Vision SSE, Budget resolve, orchestrator_logs).

| Fase | Escopo | Status |
|------|--------|--------|
| **Fase 1** | ActivityPanel global · Orchestrator Console `/console` · aba Atividade `/projects/{id}/activity` · PipelineSteps + badges SSE | ✅ |
| **Fase 2** | `project_activity_events` + `project_decisions` · auto-capture orchestrator/vision/budget/upload · BudgetTracePanel | ✅ |
| **Console Fase 1** | `/console/live` · GPU/VRAM · `JobRegistry` (visão) · cancel/unload Ollama | ✅ |
| **Console Fase 2** | SSE `/console/live/stream` · jobs chat/budget/orchestrator · barra fila Ollama | ✅ |
| **Console Fase 3** | Log ao vivo (`ops_log`) · análise visual rápida (`skip_technical`) | ✅ |
| **Fase 3** | pgvector memória cognitiva · SaaS multi-prefeitura · redesign UI completo | 🔴 adiar |

**APIs novas:** `GET /console/logs` · `GET /console/stats` · `GET /console/live` · `GET /console/live/stream` · `POST /console/jobs/{id}/cancel` · `POST /console/ollama/unload` · `GET /projects/{id}/activity` · `GET /projects/{id}/decisions`

## Restrições arquiteturais recorrentes

- Pipelines novos = camadas paralelas + feature flags + fallback seguro
- Não alterar RAG v2 core, router global, agentes existentes, orchestrator base sem flag
- Loops de evolução **nunca** auto-modificam código de agentes nem deletam modelos
- Agent Generation **nunca** ativa agentes no dispatcher — só candidate registry auditável
- **Knowledge bases são imutáveis** — Evolution/Agent Generation nunca escrevem nos índices FAISS
- **Paths canônicos** — `knowledge/raw/documents/` + `catalog.jsonl` + sidecars `.knowledge.json`; FAISS global em `memory/faiss_index/`; **FAISS de projeto** em `data/projects/{id}/faiss_index/`; loops em `data/`
- **Knowledge types:** ENGINEERING (NBR) · COST (SINAPI/TCPO) · DOCUMENTATION (TDR/projetos) — ver `core/orchestrator/domain_classifier.py`
- **Orquestrador inteligente** — único ponto de decisão domínio/agente/knowledge (`USE_ENGINEERING_ORCHESTRATOR=true`)
- **`USE_DISCIPLINE_KNOWLEDGE_ROUTER=false`** — legado; preferir agent-scoped RAG
- **SINAPI CPU — fórmula Caixa** — insumo UF→regional_as→SP; composição só CSD/CCD/CSE; ver § Pricing Engine

---

# 🔥 0. REGRA DE USO (OBRIGATÓRIA)

**Antes de qualquer novo prompt ou tarefa no Cursor:**

```
👉 "atualiza project_state.md"
```

O agente deve **ler** este arquivo, **sincronizar** com o código atual e só então **executar** a tarefa.

**Depois de concluir qualquer marco**, atualizar este doc (snapshot, roadmap, decision log, riscos).

| Sem control plane | Com control plane |
|-------------------|-------------------|
| Memória humana | Histórico do sistema |
| Retrabalho | Visão do que foi feito |
| Escopo difuso | Controle de evolução |
| "Onde paramos?" | Clareza do próximo passo |

Regra Cursor: `.cursor/rules/project-state-control-plane.mdc` (`alwaysApply: true`)

---

## 📊 Snapshot operacional

| Métrica (Jun/26) | Valor |
|------------------|-------|
| Módulos Python `backend/` | ~604 arquivos |
| Handlers REST (`app/routes/`) | ~223 endpoints (22 módulos) |
| Maior rota | `pricing.py` — 92 endpoints |
| Testes backend | **618** coletados · 99 arquivos `test_*.py` |
| Testes frontend | **0** |
| Páginas Next.js | 27 · componentes ~59 |
| Cliente API | `frontend/services/api.ts` ~2.7k linhas |

| Componente | Status | Observação |
|------------|--------|------------|
| FastAPI (`:8000`) | 🟢 | Gateway REST — rodar de `backend/` |
| PostgreSQL (`:5433`) | 🟢 | conversations, messages, projects, project_files, agent_runs, orchestrator_logs, … |
| Ollama (`:11434`) | 🟢 | 9+ modelos no WSL (ver handoff) |
| RAG v2 pipeline | 🟢 | **~14.5k chunks NBR** · cobertura ~90% códigos · SINAPI/TCPO via `price_bank` (não FAISS RAG) |
| Knowledge upload UI | 🟢 | `/settings` — upload em lote + indexação manual |
| Knowledge flat + metadata | 🟢 | `raw/documents/` · sidecars · sem pastas por disciplina |
| RAG agent-aware | 🟢 | `core/knowledge/rag/` — escopo por `agents/*.py` |
| Engineering Orchestrator | 🟢 | `core/orchestrator/` — NBR ≠ SINAPI |
| Agentes inteligentes | 🟢 | 15 disciplinas via `BaseAgentIntelligent` |
| ChatAgent (CHAT) | 🟢 | Intent layer + `qwen3:8b` + badge modelos WSL no UI |
| SIE v1 (ESTRUTURAL) | 🟢 | Classificação + normas + LLM especializado (opt-in no dispatch) |
| Model Router + Eval Loop | 🟢 | `USE_MODEL_ROUTER=false` · `USE_MODEL_EVALUATION=false` |
| Evolution Loop v1 | 🟢 | `USE_EVOLUTION_LOOP=false` — sinais, mutações, RAG boost |
| Agent Generation v1 | 🟢 | `USE_AGENT_GENERATION=false` — sandbox + promotion gate |
| Agentes legados | 🟡 | `USE_INTELLIGENT_AGENTS=false` |
| Frontend Next.js | 🟢 | `/chat`, `/projects`, `/budget`, `/orchestrate`, `/console`, `/history`, `/settings` — tema visual alinhado à `landing-reference` (surface/brand) · falta `/copilot`, `/aed` |
| **Workspace** | 🟢 | Projetos, conversas multi-turn, busca, painel lateral — `WorkspacePanel` |
| **Project RAG** | 🟢 | FAISS isolado por projeto · 12 formatos · `GET /projects/formats` |
| **Budget Engine v2** | 🟢 | `/budget` — PPD, WBS, ComD/SemD, memória de cálculo, persistência DB |
| **Cronograma (CPM + Gantt)** | 🟢 | Sync orçamento → tarefas · curvas físico/financeiro · agente IA |
| Agente Geotecnia | 🟢 | `geotecnia_intelligent.py` — prompts NBR 6122/7185 |
| Copilot v1 | 🟢 | `POST /copilot` + Evaluation v2 + Self-Improving (background) |
| AED v1 | 🟢 | `POST /aed` + Structural Selector + `aed_runs` |
| Learning Loops | 🟢 | v1 (feedback) + v2 (auto-tune, `USE_TUNED_PROMPTS=false`) |
| Autenticação SaaS | 🟡 | JWT + usuários + LAN/Quick Tunnel ✅ · multi-tenant e hardening produção 🔴 |
| Acesso em rede | 🟢 | Proxy `/api-backend` · portproxy WSL · painel `/settings/access` |
| Orchestrator v2 | 🟡 | ContextGraph ✅ · Execution Planner 🔴 |
| ContextGraph | 🟢 | Ativo no orchestrator e Copilot |
| Monorepo | 🟢 | `backend/` + `frontend/` |

**Health check:** `GET /health` → status, DB, RAG chunks, Ollama, `installed_models[]`, `models.installed_llm`  
**Models status:** `GET /models/status` → router map, perfis PostgreSQL, modelos instalados

---

## 📍 ONDE ESTAMOS AGORA

```
Fase 0  Core Infra          ████████████████████  100%  ✅
Fase 1  Agentes + RAG       ██████████████████░░   85%  🟡  ← NBR indexada; falta SINAPI/TCPO
Fase 1b Loops de evolução    ████████████████████  100%  ✅
Fase 2  Orquestração + AED   ██████████████████░░   90%  🟡  ← estamos aqui (+ orçamento/cronograma)
Fase 3  RAG avançado         ██████████░░░░░░░░░░   50%  🟡  ← agent-scoped OK; project RAG OK; falta TDRs/custo
Fase 4  SaaS produção        ██████░░░░░░░░░░░░░░   30%  🟡  ← auth + rede OK; falta tenant, billing, deploy prod
```

### Linha do tempo (marcos concluídos)

| Período | Marco | Status |
|---------|-------|--------|
| Jun/26 | Core: FastAPI, Router v2, Dispatcher, Orchestrator v1, PostgreSQL | ✅ |
| Jun/26 | RAG v2 pipeline (FAISS) + 15 agentes inteligentes | ✅ |
| Jun/26 | Intent Layer v2 + Chat streaming SSE | ✅ |
| Jun/26 | Learning Loop v1 (feedback) + v2 (auto-tune prompts) | ✅ |
| Jun/26 | Copilot v1 + Evaluation Loop v2 + Self-Improving Loop v1 | ✅ |
| Jun/26 | ContextGraph integrado (Orchestrator + Copilot) | ✅ |
| Jun/26 | **AED v1** — design autônomo multi-alternativa | ✅ |
| Jun/26 | **Structural System Selector v1** | ✅ |
| Jun/26 | **SIE v1** — Structural Intelligence Engine (ESTRUTURAL) | ✅ |
| Jun/26 | **Model Router + Model Evaluation Loop v1** | ✅ |
| Jun/26 | **Evolution Loop v1** + **Agent Generation Loop v1** | ✅ |
| Jun/26 | **Monorepo** `backend/` + `frontend/` | ✅ |
| Jun/26 | Health dinâmico — modelos Ollama WSL no UI | ✅ |
| Jun/26 | **Knowledge flat** — `raw/documents/` + metadata (sem 64+ pastas) | ✅ |
| Jun/26 | **RAG performance** — cache semântico, métricas, index-first | ✅ |
| Jun/26 | **RAG agent-aware** — escopo por agente, anti-contaminação SINAPI/NBR | ✅ |
| Jun/26 | **Engineering Orchestrator** — domínio engenharia vs orçamento | ✅ |
| Jun/26 | **Workspace** — projetos, conversas multi-turn, busca, CRUD | ✅ |
| Jun/26 | **Project RAG multi-formato** — FAISS por projeto (PDF, Office, CAD, BIM) | ✅ |
| Jun/26 | **Chat streaming UX** — SSE instantâneo + render ~60fps no frontend | ✅ |
| Jun/26 | **GeotecniaIntelligentAgent** — prompts geotécnicos especializados | ✅ |
| Jun/26 | **Pricing Engine v1** — providers plugáveis, cache, itemização orçamentária | ✅ |
| Jun/26 | **Budget Engine v2 + Orchestrator** — planilha editável, pipeline LLM→qty→preço | ✅ |
| Jun/26 | **Formato PPD MC/OR** — import/export .xlsm, BDI, ETAPA/S, base SINAPI Mar/2026 | ✅ |
| Jun/26 | **Cronograma CPM + Gantt** — sync orçamento, curvas mensais, agente IA, edição manual | ✅ |
| Jun/26 | **Renumeração WBS automática** — `renumber_wbs` + botão Organizar numeração | ✅ |
| Jun/26 | **UI ComD/SemD** — colunas paralelas, custo sem BDI + valor BDI + total adotado (menor) | ✅ |
| Jun/26 | **Vision Analysis** — modos obra/laudo/relatório fotográfico, API REST, UI `/projects/{id}/vision`, export DOCX | ✅ ← último marco |

### O que falta para fechar a Fase 2

| # | Tarefa | Prioridade | Esforço |
|---|--------|------------|---------|
| 1 | **Validar Project RAG** — upload multi-formato → `/chat?project=` | ✅ | Baixo — `test_project_rag_e2e.py` · `make validate-project-rag` |
| 2 | **Indexar SINAPI/TCPO (orçamento)** — `price_bank` + `composition_index` FAISS | ✅ | Baixo — `make index-price-bases` · `make validate-price-bases` |
| 3 | Simuladores por sistema estrutural (`concrete_armed_simulator`, etc.) | Alta | Médio |
| 4 | Execution Planner (ordem + dependências entre disciplinas) | Alta | Alto |
| 5 | Frontend `/aed` e `/copilot` | ✅ | Médio — M3 concluído |
| 6 | Integrar Copilot → AED (disparo automático p/ projetos estruturais) | Média | Baixo |
| 7 | Propagação de premissas entre agentes (Orchestrator v2 completo) | Média | Alto |

### Próximo passo recomendado

> **1.** Criar projeto em `/projects`, fazer upload de memorial/planilha/IFC e testar `/chat?project=<id>`  
> **2.** Indexar SINAPI/TCPO em `knowledge/raw/documents/`  
> **3.** Montar orçamento em `/budget` (etapas + cronograma + conferir ComD/SemD) e exportar PPD  
> **4.** Implementar simulador dedicado `concrete_armed_simulator` (primeiro do registry)

**Git:** `main` @ commit `ffa593a` — cronograma Gantt, agente IA, renumeração WBS (push GitHub Jun/26). Alterações ComD/SemD UI **locais** — commit pendente se ainda não enviado.

---

# 🟢 1. CORE INFRAESTRUTURA (CONCLUÍDO)

## Backend

| Módulo | Path | Responsabilidade |
|--------|------|------------------|
| API Gateway | `app/main.py` | FastAPI, CORS, lifespan, rotas |
| Router v2 | `core/router.py` | Saudação → regras (keywords) → LLM fallback → GERAL |
| Agent Registry | `core/agent_registry.py` | Fonte única: disciplina → `{modulo}_agent` |
| Dispatcher | `core/dispatcher.py` | Roteia para agente; persiste `agent_runs` + Learning Loop |
| Orchestrator v1 | `core/orchestrator/multi_domain.py` | Decomposição multi-disciplina + síntese + filtro domínio |
| Engineering Orchestrator | `core/orchestrator/engineering_orchestrator.py` | Classifica domínio · escolhe agente · separa NBR/SINAPI |
| Learning Loop v1 | `core/learning/` | Coleta `agent_feedback` (execução + rating) |
| Learning Loop v2 | `core/learning_v2/` | Auto-tuning de prompts por disciplina (rule-based) |
| Evolution Loop v1 | `core/evolution/` | Auto-otimização contínua: modelos, prompts, agentes, RAG |
| Agent Generation v1 | `core/agent_generation/` | Proposta controlada de novos agentes (sandbox + promotion gate) |
| Model Router | `core/models/model_router.py` | Roteamento LLM por `task_type` + fallbacks |
| Model Evaluation Loop | `core/models/model_evaluation_loop.py` | Comparação primary vs fallback + perfis PostgreSQL |
| Copilot v1 | `core/copilot/` | Intent → plan → execute → synthesize → evaluate |
| Evaluation Loop v2 | `core/evaluation_v2/` | Autoavaliação do Copilot (4 níveis + PostgreSQL) |
| Self-Improving Loop v1 | `core/self_improving/` | Meta-análise + patches propostos (sem auto-apply) |
| AED v1 | `core/aed/` | Design autônomo: gerar → simular → comparar → selecionar → relatório |
| Structural Selector | `core/structural_selector/` | Classificação de sistema estrutural antes da simulação AED |
| SIE v1 | `core/structural_intelligence/` | Inteligência estrutural (classificação, normas, LLM) — só ESTRUTURAL |
| PostgreSQL | `core/database/` | Models, repository, service, connection, `migrate_workspace.py`, `migrate_audit_fks.py` |
| **Workspace service** | `app/services/workspace_service.py` | Projetos, arquivos, conversas, busca |
| **Project RAG** | `core/project_rag/` | FAISS por projeto + extractors multi-formato |
| **Conversation context** | `core/conversation_context.py` | Multi-turn: `conversation_id`, thread history |
| Settings | `config/settings.py` | Ollama, RAG, DB, feature flags |

### Endpoints REST

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/health` | Status DB, RAG, Ollama, modelos instalados WSL |
| `GET` | `/models/status` | Model Router map, perfis, modelos Ollama |
| `POST` | `/chat` | Single-domain: router → RAG → agente |
| `POST` | `/orchestrate` | Multi-domain: decompose → N agentes → síntese |
| `POST` | `/copilot` | Copilot v1: plan → multi-agente → síntese → score |
| `POST` | `/aed` | AED v1: understanding → designs → simulação → seleção → relatório |
| `POST` | `/chat/stream` | Chat SSE (Intent Layer + tokens + fases rag/llm) |
| `POST` | `/feedback` | Rating/comentário sobre resposta (Learning Loop) |
| `GET` | `/history` | Histórico de conversas e execuções |
| `GET` | `/workspace/search?q=` | Busca em projetos e conversas |
| `GET/POST/PATCH/DELETE` | `/projects` | CRUD de projetos (workspace) |
| `GET` | `/projects/formats` | Formatos indexáveis + `accept` para upload |
| `POST/DELETE` | `/projects/{id}/files` | Upload multi-formato + remoção |
| `POST` | `/projects/{id}/reindex` | Reindexar FAISS do projeto |
| `GET/PATCH/DELETE` | `/conversations` | Listar, renomear, excluir conversas |
| `GET` | `/conversations/{id}` | Detalhe com mensagens (multi-turn) |
| `GET/POST` | `/knowledge/*` | Ingest, index, catalog, stats |
| `GET` | `/docs` | OpenAPI Swagger |

## Frontend

| Rota | Path | Descrição |
|------|------|-----------|
| `/chat` | `frontend/app/chat/page.tsx` | Chat single-agent + painel workspace + resume `?c=` / `?project=` |
| `/projects` | `frontend/app/projects/page.tsx` | Lista de projetos |
| `/projects/[id]` | `frontend/app/projects/[id]/page.tsx` | Detalhe: conversas, upload multi-formato, reindex |
| `/orchestrate` | `frontend/app/orchestrate/page.tsx` | Orquestração multi-disciplina |
| `/history` | `frontend/app/history/page.tsx` | Histórico de execuções + continuar no chat |
| `/settings` | `frontend/app/settings/page.tsx` | Upload/indexação `knowledge` (NBR, SINAPI…) |
| `/budget` | `frontend/app/budget/page.tsx` | Orçamento PPD: abas flat, etapas, planilha ComD/SemD, cronograma Gantt, memória de cálculo |
| `/budget/models` | `frontend/app/budget/models/page.tsx` | Cadastro de esqueletos WBS (etapas/sub-etapas) para novos orçamentos |
| `BudgetPriceBasesPanel` | `frontend/components/BudgetPriceBasesPanel.tsx` | Adicionar/editar bases do orçamento (SINAPI/SICRO) — formulário + listbox |
| `BudgetGantt` | `frontend/components/BudgetGantt.tsx` | Gantt + curvas físico/financeiro (mensal) |
| `BudgetSchedulePanel` | `frontend/components/BudgetSchedulePanel.tsx` | Agente IA cronograma + edição manual CPM |
| `budget-desoneracao.ts` | `frontend/lib/budget-desoneracao.ts` | Totais ComD/SemD, custo sem BDI, valor BDI, total adotado |
| `WorkspacePanel` | `frontend/components/WorkspacePanel.tsx` | Sidebar: projetos, conversas, busca |
| **Design system** | `frontend/app/globals.css`, `tailwind.config.ts` | Tokens `surface`/`brand` (sky #0ea5e9), neutros zinc, `.app-card`, glow ambiente — referência `frontend/landing-reference/` |
| API client | `frontend/services/api.ts` | Cliente HTTP → `localhost:8000` (auth-ready) |

## IA Engine — RAG v2 + Knowledge Layer

| Componente | Path | Status |
|------------|------|--------|
| RAG Engine | `memory/rag_engine.py` | 🟢 Orquestrador + `enrich_route_result` agent-aware |
| Retriever | `memory/retriever.py` | 🟢 FAISS + cache semântico + rerank |
| Semantic cache | `memory/semantic_cache.py` | 🟢 Top-K reutilizado (cosine ≥ 0.92) |
| RAG metrics | `memory/rag_metrics.py` | 🟢 `embedding_time_ms`, `total_rag_latency_ms` |
| Multi-Index Store | `core/knowledge/multi_index_store.py` | 🟢 FAISS por base · 1 embed / N bases |
| Knowledge Base Router | `core/knowledge/knowledge_base_router.py` | 🟢 Multi-index + agent orchestrator |
| **Agent RAG** | `core/knowledge/rag/` | 🟢 Router, scopes, rerank, retriever por agente |
| **Domain classifier** | `core/orchestrator/domain_classifier.py` | 🟢 ENGINEERING \| COST \| DOCUMENTATION |
| **Knowledge router (orch.)** | `core/orchestrator/knowledge_router.py` | 🟢 Regras NBR/SINAPI + rerank por domínio |
| Knowledge resolver | `core/knowledge/resolver.py` | 🟢 Paths flat → `raw/documents/` |
| Knowledge ingestion | `core/knowledge/ingestion.py` | 🟢 Classifier → sidecar + `catalog.jsonl` |
| Knowledge indexer | `core/knowledge/knowledge_indexer.py` | 🟢 PDF/CSV/Excel → índices FAISS |
| Domain Detector | `core/knowledge/domain_detector.py` | 🟢 Heurística domínio (legado multi-base) |
| PDF Indexer | `memory/pdf_indexer.py` | 🟢 Indexação NBR/TDR (ingest only) |
| Script indexação | `scripts/index_knowledge_bases.py` | 🟢 CLI por base |
| **Knowledge API** | `app/routes/knowledge.py` | 🟢 `POST /ingest` · `POST /index` · `GET /catalog` · `GET /stats` |
| **Settings UI** | `frontend/app/settings/page.tsx` | 🟢 Upload em lote NBR/SINAPI/TCPO |

**Storage:** `backend/knowledge/raw/documents/` + `{arquivo}.knowledge.json` + `catalog.jsonl`  
**Cache RAG:** `backend/knowledge/cache/` (semantic + failing queries)  
**Índices FAISS:** `backend/memory/faiss_index/knowledge/{nbr_index,cost_index,…}`  
**Filtragem:** metadata `discipline` + `content_type` — **não** por pasta física

## Workspace + Project RAG (por empreendimento)

| Componente | Path | Status |
|------------|------|--------|
| Project RAG engine | `core/project_rag/project_rag.py` | 🟢 FAISS dedicado por `project_id` |
| Extractors multi-formato | `core/project_rag/project_file_extractors.py` | 🟢 PDF, DOCX, XLSX/XLS, CSV, TXT, MD, JSON, RTF, DXF, IFC, DWG |
| Workspace API | `app/routes/workspace.py` | 🟢 CRUD projetos, arquivos, conversas, busca |
| Workspace service | `app/services/workspace_service.py` | 🟢 Upload, indexação, reindex, search |
| Chat stream + project | `app/services/chat_stream_service.py` | 🟢 `conversation_id`, `project_id`, save async |
| Intent Layer streaming | `core/intent_layer.py` | 🟢 Fases SSE: rag → rag_done → llm_start |
| Stream helpers | `core/stream_events.py` | 🟢 `iter_text_chunks`, keepalive SSE |
| Conversation context | `core/conversation_context.py` | 🟢 Multi-turn thread + append messages |
| RAG merge | `memory/rag_engine.py` | 🟢 `augment_route_with_project_context` |
| DB migration | `core/database/migrate_workspace.py`, `migrate_audit_fks.py` | 🟢 Roda no `init_db` |
| Testes extractors | `tests/test_project_file_extractors.py` | 🟢 txt, csv, json, suffixes |

**Formatos indexáveis:**

| Ext | Tipo | Qualidade RAG |
|-----|------|---------------|
| `.pdf` | Documentos | Completa (por página) |
| `.docx` | Word | Completa (parágrafos + tabelas) |
| `.xlsx` / `.xls` | Excel | Completa (linhas por aba) |
| `.csv` | Planilha | Completa (linhas) |
| `.txt` / `.md` / `.json` / `.rtf` | Texto | Completa |
| `.dxf` | AutoCAD | Boa (camadas + TEXT/MTEXT) |
| `.ifc` | BIM | Metadados (projeto, pavimentos, elementos, Psets) |
| `.dwg` | AutoCAD | **Parcial** — strings ASCII; preferir PDF/DXF |

**Storage arquivos:** `backend/data/projects/{project_id}/`  
**Índice FAISS:** `backend/data/projects/{project_id}/faiss_index/` (gitignored)  
**Integração chat:** `POST /chat` e `/chat/stream` aceitam `conversation_id` + `project_id`; contexto do projeto injetado via `enrich_route_result`

### Separação de conhecimento (orquestrador)

| Tipo | Bases FAISS | Agentes | Bloqueado |
|------|-------------|---------|-----------|
| **ENGINEERING** | `nbr` | estruturas, elétrica, hidráulica… | SINAPI, TCPO |
| **COST** | `sinapi`, `tcpo` | orcamento | NBR |
| **DOCUMENTATION** | `tdr`, `catalogos` | topografia, geoprocessamento… | SINAPI em eng. |

## Persistência (PostgreSQL)

```
projects
  ├── project_files
  └── conversations
        ├── conversation_messages
        ├── orchestrator_logs
        ├── agent_runs
        └── agent_feedback   # Learning Loop v1
```

| Tabela | Campos-chave |
|--------|--------------|
| `projects` | `name`, `description` — workspace por empreendimento |
| `project_files` | `filename`, `storage_path`, `content_type`, `size_bytes` |
| `conversations` | `input_text`, `title`, `mode`, `message_count`, `project_id` |
| `conversation_messages` | `role`, `content`, `meta` — histórico multi-turn |
| `orchestrator_logs` | `disciplines[]`, `final_report`, `synthesis`, `use_rag` |
| `agent_runs` | `agent_name`, `discipline`, `result_text`, `had_context`, `extra` (JSON) |
| `agent_feedback` | `input_text`, `response_text`, `rating`, `feedback_text`, `corrected_answer` |
| `copilot_evaluations` | `intent_accuracy`, `plan_quality`, `execution_completeness`, `response_quality`, `final_score`, `issues` |
| `system_failures` | `failure_type`, `route_decision`, `evaluation_scores`, `suggested_fix` |
| `system_patches` | `patch_key`, `patch_version`, `patch_type`, `content` (JSON), `risk_score` |
| `aed_runs` | `input_text`, `understanding`, `designs`, `simulations`, `comparison`, `selection`, `report`, `use_rag` |
| `model_evaluations` | `task_type`, `discipline`, `primary_model`, `fallback_model`, `winner_model`, scores, latencies |
| `model_performance_profile` | Ranking dinâmico por `task_type` + `discipline` + `model_name` |
| `evolution_signals` | Sinais de execução coletados (modelo, prompt, agente, RAG, qualidade) |
| `evolution_mutations` | Mutações propostas/aplicadas — audit trail obrigatório |
| `agent_proposals` | Propostas de novos agentes (nunca auto-ativadas) |
| `agent_simulations` | Execuções sandbox (20–50 runs) por proposta |

**Docker:** `infra/docker/docker-compose.yml` — porta **5433**  
**Init:** `cd backend && python scripts/init_db.py`

### Learning Loop v2 (arquivos)

```
backend/data/learning_v2/
  profiles/ESTRUTURAL.json
  prompts/estrutural/prompt_estrutural_v1.txt
```

**Job manual:** `cd backend && python scripts/run_auto_tune.py [--discipline ESTRUTURAL]`

### Evolution Loop v1 (arquivos)

```
core/evolution/
  evolution_engine.py      # Orquestrador: sinais → análise → mutações → rollout
  signal_collector.py      # Captura modelo, prompt, agente, RAG, qualidade
  performance_analyzer.py  # win_rate, degradação, best_performer por contexto
  mutation_engine.py       # Propostas MODEL | PROMPT | AGENT | RAG
  rollout_manager.py       # Shadow test + safe rollout (USE_SAFE_ROLLOUT)
  rag_evolution.py         # Boost/penalidade de chunks + cache alto valor
  audit.py                 # Persistência evolution_signals / evolution_mutations

data/evolution/
  rag_chunk_profiles.json  # Boosts dinâmicos de normas/chunks
```

**Feature flags:** `USE_EVOLUTION_LOOP=false` (default), `USE_SAFE_ROLLOUT=true`  
**Integrações:** dispatcher, model eval, copilot, aed, orchestrator, learning v2, chat stream, RAG retriever  
**Safety:** nunca auto-delete agentes/modelos; mutações AGENT só auditáveis

### Agent Generation Loop v1 (controlled)

```
core/agent_generation/
  agent_proposer.py           # Detecta gaps → AgentProposal (nunca ativa)
  agent_simulator.py          # 20–50 runs sandbox (heuristic ou LLM leve + RAG read-only)
  agent_evaluator.py          # quality, consistency, latency, improvement
  agent_registry_candidate.py # Registro versionado de candidatos (≠ dispatcher AGENTS)
  agent_promotion_gate.py     # improvement > 8%, risk < threshold, domínio permitido
  agent_generation_engine.py  # Orquestrador + integração Evolution Loop

data/agent_generation/
  candidates.json             # Candidatos versionados + promotion_log
```

**Feature flag:** `USE_AGENT_GENERATION=false` (default)  
**Limites:** `MAX_AGENTS_TOTAL=25`, `MAX_NEW_AGENTS_PER_WEEK=2`  
**Domínios permitidos:** ARQUITETURA, ESTRUTURAL, HIDROSSANITARIO, GEOTECNIA, DRENAGEM, ELETRICA, INCENDIO, ORCAMENTO, TRANSPORTES, INFRAESTRUTURA  
**CLI:** `cd backend && python scripts/run_agent_generation.py [--discipline ESTRUTURAL] [--runs 30]`  
**Safety:** promoção = registro em candidate registry — dispatcher nunca alterado automaticamente

**Runtime (opt-in):** `USE_TUNED_PROMPTS=true` — agentes inteligentes usam a versão ativa do profile em `build_prompt()`.

## Testes

| Suite | Path | Cobertura |
|-------|------|-----------|
| Router | `tests/test_router.py` | Regras + roteamento |
| Orchestrator | `tests/test_orchestrator.py` | Decompose, execute, synthesize |
| Engineering Orchestrator | `tests/test_engineering_orchestrator.py` | NBR≠SINAPI, domain, rerank |
| Agent RAG | `tests/test_agent_rag.py` | Escopo por agente, anti-contaminação |
| RAG performance | `tests/test_rag_performance.py` | Cache, latência, no PDF I/O |
| Knowledge | `tests/test_knowledge_*.py` | Router, activation, discipline |
| API | `tests/test_api.py` | Endpoints HTTP |
| RAG/Memory | `tests/test_memory.py` | FAISS, chunker, retriever |
| Database | `tests/test_database.py` | Persistência |
| Learning Loop | `tests/test_learning_loop.py` | Feedback, low-quality, dispatcher |
| Learning Loop v2 | `tests/test_learning_loop_v2.py` | Profiles, versionamento, auto-tune |
| Evolution Loop v1 | `tests/test_evolution_loop.py` | Sinais, mutações, rollout, RAG evolution |
| Agent Generation v1 | `tests/test_agent_generation.py` | Proposta, sandbox, promotion gate, limites |
| Copilot v1 | `tests/test_copilot.py` | Intent, plan, execução, avaliação |
| Evaluation Loop v2 | `tests/test_evaluation_loop_v2.py` | Scores, pipeline, persistência |
| Self-Improving Loop | `tests/test_self_improving_loop.py` | Meta-análise, patches, persistência |
| AED v1 | `tests/test_aed.py` | Pipeline completo, ≥2 designs/disciplina, persistência |
| Structural Selector | `backend/tests/test_structural_selector.py` | Heurísticas, normas, integração AED |
| SIE v1 | `backend/tests/test_structural_intelligence.py` | Classificação, dispatch adapter |
| Model Router | `backend/tests/test_model_router.py` | Roteamento por task_type |
| Model Evaluation | `backend/tests/test_model_evaluation_loop.py` | Scorer, perfis PostgreSQL |
| Project file extractors | `tests/test_project_file_extractors.py` | txt, csv, json, suffixes indexáveis |
| Geotecnia agent | `tests/test_geotecnia_intelligent.py` | Agente dedicado + prompts NBR |
| Agent Registry | `backend/tests/test_agent_registry.py` | Mapeamento disciplinas |
| BaseAgentIntelligent | `tests/test_base_agent_intelligent.py` | Pipeline inteligente (mock LLM) |

---

# 🟡 2. INTELIGÊNCIA DO SISTEMA (EM EVOLUÇÃO)

## Agentes — matriz de disciplinas

Todos os 15 agentes especializados existem em **dois modos**:

| Disciplina | Agent name | NBRs base | Modo inteligente | Modo legado |
|------------|------------|-----------|-------------------|-------------|
| ARQUITETURA | `arquitetura_agent` | NBR 9050, 15575 | 🟢 | 🟡 simulado |
| ESTRUTURAL | `estruturas_agent` | NBR 6118, 8681 | 🟢 | 🟡 simulado |
| HIDROSSANITÁRIO | `hidrossanitario_agent` | NBR 5626, 8160 | 🟢 | 🟡 simulado |
| DRENAGEM | `drenagem_agent` | NBR 10844, 9575 | 🟢 | 🟡 simulado |
| ELÉTRICA | `eletrica_agent` | NBR 5410, 14039 | 🟢 | 🟡 simulado |
| TELECOM | `telecom_agent` | NBR 14567, ISO/IEC 11801 | 🟢 | 🟡 simulado |
| INCÊNDIO | `incendio_agent` | NBR 17240, 10898 | 🟢 | 🟡 simulado |
| GEOTECNIA | `geotecnia_agent` | NBR 6122, 7185 | 🟢 | 🟡 simulado |
| TRANSPORTES | `transportes_agent` | NBR 7188, 7200 | 🟢 | 🟡 simulado |
| INFRAESTRUTURA | `infraestrutura_agent` | NBR 6118, 7188 | 🟢 | 🟡 simulado |
| SANEAMENTO | `saneamento_agent` | NBR 9649, 9814 | 🟢 | 🟡 simulado |
| GEOPROCESSAMENTO | `geoprocessamento_agent` | ISO 19115, OGC | 🟢 | 🟡 simulado |
| TOPOGRAFIA | `topografia_agent` | NBR 13133 | 🟢 | 🟡 simulado |
| ORÇAMENTO | `orcamento_agent` | SINAPI, NBR ISO 12006 | 🟢 | 🟡 simulado |
| MEIO AMBIENTE | `meio_ambiente_agent` | ISO 14001, CONAMA | 🟢 | 🟡 simulado |

### Pipeline inteligente (padrão)

```
handle(text)
  → retrieve_context (RAG v2, filtro por disciplina)
  → build_prompt (NBRs + contexto normativo + instruções engenharia)
  → call_llm (Ollama: qwen3:14b → fallback qwen3-coder)
  → build_response (extra.intelligent=true, extra.llm_model)
```

| Arquivo | Papel |
|---------|-------|
| `core/agents/base_agent_intelligent.py` | Classe base RAG + LLM |
| `core/agents/intelligent_factory.py` | Factory padrão do dispatcher |
| `core/agents/legacy_factory.py` | Rollback para agentes simulados |
| `core/agents/estruturas_intelligent.py` | Exemplo de agente customizado |
| `core/agents/geotecnia_intelligent.py` | Agente geotécnico dedicado (NBR 6122/7185) |
| `models/ollama_client.py` | Cliente Ollama com fallback de modelo |
| `agents/*.py` | Agentes legados (`BaseAgent`) — mantidos, não usados por padrão |

### Gaps conhecidos da inteligência

- [x] **NBR indexada** — force reindex + **manutenção** (`scripts/knowledge_maintenance.py`, `POST /knowledge/maintenance`) · extrator PyMuPDF+OCR · compact FAISS · purge órfãos
- [ ] **~230 PDFs sem texto extraível** (14833 scans) — instalar `tesseract-ocr-por` para OCR completo
- [ ] **SINAPI/TCPO não indexados no RAG** — orçamento determinístico via **Pricing Engine v1** (`backend/pricing/`) com CSV de exemplo; bases completas ainda pendentes
- [ ] **Prompts genéricos** — um template único por disciplina; falta especialização fina (exc. geotecnia)
- [ ] **Validação normativa** — LLM pode confundir nomenclaturas (ex.: classes I–IV vs A–D na NBR 6118)
- [ ] **Latência alta** — inferência local ~2–5 min por request em CPU
- [ ] **Agentes customizados** — `estruturas_intelligent.py` e `geotecnia_intelligent.py`; demais usam factory genérica
- [ ] **Remoção legado** — agentes simulados ainda existem para rollback/testes

## Orchestrator

| Versão | Status | Capacidades |
|--------|--------|-------------|
| **v1** | 🟢 Concluído | `decompose_problem` → `execute_agents` → `synthesize_results` |
| **v2** | 🟡 Em progresso | ContextGraph ✅ · Execution Planner 🔴 · dependências 🔴 |

**v1 — fluxo atual:**
1. Decomposição por keywords (+ LLM quando disponível)
2. Execução independente de cada agente (sem compartilhamento de contexto)
3. Síntese textual agregando respostas por disciplina

## Pricing Engine v1 + Budget Engine v2

| Status | 🟢 Implementado |
|--------|-----------------|
| **Path** | `backend/pricing/` |
| **Regra** | LLM interpreta intenção; **Pricing Engine resolve preço** (determinístico) |

### Componentes

| Módulo | Função |
|--------|--------|
| `core/pricing_engine.py` | Fallback entre providers, ranking por similaridade + preço |
| `core/price_matcher.py` | Match lexical + fuzzy (sem LLM) |
| `core/price_cache.py` | Cache em memória com TTL |
| `providers/*` | SINAPI, ORSE, TCPO, CICRO, Excel (plugin) |
| `registry/provider_registry.py` | Registro plug-and-play |
| `quantity/quantity_engine.py` | Cálculo técnico de quantitativos (área, volume, perda 5%) |
| `orchestrator/budget_orchestrator.py` | Pipeline texto → intent → qty → pricing → budget |
| `orchestrator/intent_parser.py` | LLM + fallback regex (sem preços) |
| `budget/structure_engine.py` | Árvore de itemização (grupo → composição → insumo) |
| `budget/budget_builder.py` | Monta orçamento com `source_trace` por item |
| `budget/budget_engine_v2.py` | Sessão editável, recálculo, export Excel |
| `budget/budget_structure.py` | WBS manual + **`renumber_wbs`** (numeração sequencial 1, 1.1, 1.1.1…) |
| `budget/budget_calculator.py` | Memória de cálculo por célula |
| `schedule/schedule_builder.py` | Sync orçamento → tarefas + CPM |
| `schedule/cpm_engine.py` | Cálculo caminho crítico (FS/SS/FF/SF + lag) |
| `schedule/schedule_agent.py` | Agente IA: catálogo WBS, intent, resolução código/nome, enriquecimento de plano |
| `schedule/schedule_models.py` | `ProjectSchedule`, `ScheduleTask`, `ScheduleLink` |

### API

| Endpoint | Descrição |
|----------|-----------|
| `GET /pricing/providers` | Lista bases carregadas |
| `POST /pricing/resolve` | Resolve melhor preço para query |
| `POST /pricing/budget/build` | Gera orçamento hierárquico a partir de `intent` |
| `POST /pricing/budget/generate` | **Pipeline completo** (LLM → qty → preço → planilha) |
| `GET /pricing/budget/{id}` | Sessão editável |
| `PATCH /pricing/budget/{id}/cell` | Edição de célula + recálculo |
| `DELETE /pricing/budget/{id}/rows/{row_id}` | Exclui linha + **renumera WBS** automaticamente |
| `POST /pricing/budget/{id}/itemization/renumber` | Organiza numeração WBS (botão na toolbar) |
| `GET /pricing/budget/{id}/export` | Download Excel legado (workbook 5 abas) |
| `GET /pricing/budget/{id}/export/xlsx/{doc}` | Download Excel por documento (layout alinhado ao PDF) — inclui `curva_abc`, `curva_s`, `histograma` |
| `GET /pricing/budget/{id}/export/pdf/{doc}` | Download PDF por documento — inclui analíticas ABC/S/Histograma |
| `GET /pricing/budget/{id}/schedule` | Cronograma da sessão |
| `POST /pricing/budget/{id}/schedule/sync` | Sincroniza tarefas com orçamento |
| `POST /pricing/budget/{id}/schedule/recalculate` | Recalcula CPM |
| `PATCH /pricing/budget/{id}/schedule/settings` | Data de início da obra |
| `PATCH /pricing/budget/{id}/schedule/tasks/{task_id}` | Duração / início manual |
| `POST /pricing/budget/{id}/schedule/links` | Vínculo predecessor/successor |
| `DELETE /pricing/budget/{id}/schedule/links/{link_id}` | Remove vínculo |
| `POST /pricing/budget/{id}/schedule/compose` | Agente IA organiza cronograma via prompt |
| `POST /pricing/budget/{id}/tech-spec/compose/stream` | SSE — gera Especificação Técnica a partir do orçamento |
| `GET/PUT /pricing/budget/{id}/tech-spec` | Lê/atualiza documento (markdown + HTML editável) |
| `GET /pricing/budget/{id}/tech-spec/export` | Download DOCX (layout técnico ABNT) |
| `GET /pricing/budget/{id}/tech-spec/export/pdf` | Download PDF (ReportLab) |
| `POST /pricing/providers/{name}/upload` | Upload base CSV/Excel |
| `POST /pricing/bases/reload` | Recarrega bases do disco |

### Frontend `/budget`

| Área | Path | Descrição |
|------|------|-----------|
| Abas | `BudgetEtapasPanel`, `BudgetSpreadsheet`, `BudgetMemoryPanel`, `BudgetSchedulePanel` | Etapas, planilha, memória de cálculo, cronograma |
| ComD / SemD | `lib/budget-desoneracao.ts`, `BudgetTotalsSummary.tsx` | Colunas paralelas (azul ComD · verde SemD); rodapé: custo sem BDI, valor BDI, total com BDI, **total adotado (menor)** |
| Gantt | `BudgetGantt.tsx`, `lib/schedule-curves.ts` | Cabeçalho mês/semana, curvas físico/desembolso/financeiro, visão etapas/completo |
| WBS | `BudgetToolbar` | Botão **Organizar numeração** + renumeração automática ao excluir linha |
| Export | `BudgetToolbar` | Select tipo de documento + **Gerar PDF** + **Baixar Excel** (mesmo tipo selecionado) |
| Histórico | `BudgetHistoricoTab` | Esquerda: lista completa ou resumo por etapas; direita: lista com valor, selecionar, editar (lápis), excluir (lixeira) |
| Cronograma IA | `BudgetSchedulePanel` | Prompt + `ModelSelector`; auto `replace_links` em reorganização completa |
| Persistência | `budget_db_service.py` | Sessão inclui `schedule` no payload salvo |

### Bases reais

- `backend/pricing/data/sinapi.csv` ou `data/sinapi/*.csv` (múltiplos mesclados)
- `PRICING_DATA_DIR` para diretório customizado

### Regra SINAPI — fórmula Caixa (Analítico com Custo)

Espelha a fórmula Excel da aba **Analítico com Custo**:

| Tipo | Encargo | Abas | Lógica |
|------|---------|------|--------|
| **INSUMO** | Sem desoneração | ISD | `preco_uf` → `preco_regional_as` (col. M) → `preco_sp` |
| **INSUMO** | Com desoneração | ICD | idem (col. N) |
| **INSUMO** | Sem encargos sociais | ISE | idem (col. L) |
| **COMPOSICAO** | Sem / Com / Sem enc. | CSD / CCD / CSE | PROCX na UF — **sem fallback SP** |

**Onde vale:** prévia CPU, agente de orçamento, exportações analíticas.

**Código:** `sinapi_caixa_pricing.py` · `price_bank_regional.py` · `sinapi_parser.py` (`regional_as` no import).

**Exemplo:** CPU **95995 / AM / 03/2026 SemD** — 96464 **94,96** · 1518 **512,50** · total **1.469,59**.

### Pendências orçamento

- [x] Export Excel por documento com layout alinhado ao PDF (`budget_export_tables.py` + `export_budget_document_xlsx`)
- [x] Export analíticas Curva ABC / Curva S / Histograma (PDF + Excel + gráficos no PDF)
- [x] Relatórios **Insumos e Materiais** e **Mão de Obra** (PDF/Excel) — agregação por código/unidade a partir das CPUs; rodapé TOTAL SEM BDI · VALOR BDI · TOTAL COM BDI
- [x] Cache histograma + prefetch CPUs (reabertura instantânea da aba)
- [x] **B1** — `user_id` + filtros em `budget_documents` (ownership multi-usuário)
- [x] **B2** — Versionamento / lock otimista ao salvar (`expected_version`, HTTP 409)
- [x] **B3** — BDI configurável por edital + decomposição TCU (perfis + UI Dados)
- [x] **B4** — UI import PPD + pipeline LLM (`BudgetPipelinePanel` / `budgetGenerateStream` na aba Histórico)
- [x] **B5** — Expor TCPO/ORSE na UI do orçamento (Busca CPU)
- [x] **B6** — Fluxo aditivo (baseline congelada + revisão / aditivo contratual)
- [x] **B7** — Trilha auditoria completa (B7+B16) — `cell_edit`, `bdi_change`, `add_service`, `replace_service`, `compose_etapa`, `apply_group_quantity`, cronograma → `budget_audit_log`
- [x] **B8** — Curva S com cenário adotado explícito na exportação (ComD vs SemD documentado)
- [x] **B10** — Testes E2E Playwright orçamento (`make test-budget-e2e` — **14** testes mock + `make test-budget-e2e-live`)
- [x] **B12** — Piloto obra real automatizado (`test_budget_pilot_flow` + `make validate-budget-pilot`)
- [x] **B14** — CI GitHub Actions (`make test-ci` = `test-ci-backend` + `test-budget-e2e`)
- [x] **B15** — Piloto campo §4 (`validate_budget_pilot.sh` expandido + `test_pilot_section4_field_checklist` + CI export/ABC)
- [x] **B16** — Auditoria completa CPU/serviço/cronograma (`budget_audit.py` + persistência rotas + `test_budget_audit_b16.py`)
- [x] **B17** — Piloto UI manual §4.U — script `make validate-budget-pilot-ui` + checklist 4.U1–4.U7
- [x] **B18** — Snapshot `SESSION_STORE` PostgreSQL (`budget_session_snapshots` + restore automático em `get()`)
- [x] **B19** — Export `.xlsm` oficial SEMINF (`GET /budget/{id}/export/xlsm` + `POST .../workbook/sync`)
- [x] **B20** — Testes export ampliados (pytest `proposta_comercial`/`compliance-pack` + Playwright export PDF/XLSX na toolbar)
- [x] **B21** — CPQ margem comercial (`commercial_margin_pct` + UI `BudgetCommercialPanel` na aba Dados + export `proposta_comercial` PDF/XLSX)
- [x] **B22** — Pacote compliance licitação (`GET .../export/compliance-pack.json` + checklist Lei 14.133)
- [x] **B23** — UI licitação: toolbar PPD `.xlsm` + pacote compliance + painel checklist na aba Dados
- [x] **B24** — Piloto ampliado: `validate_budget_pilot.sh` cobre 4.U5/4.U6 + pytest xlsm/compliance/BDI
- [x] **B25** — Playwright API real (`e2e/budget-live.spec.ts` + `make test-budget-e2e-live`)
- [x] **B26** — Validador BDI vs edital (`bdi_edital_validator.py` + `GET /bdi/validation` + alertas UI)
- [x] **B27** — Tenant multi-empresa — `empresa_id` em `budget_documents` + header `X-Tenant-Id` + `BudgetTenantSelector` + MinIO `tenants/{id}/budgets/…`
- [x] **B28** — Lock sessão concorrente — `BudgetSessionLock` TTL 300s + rotas lock/renew/release + guard PATCH cell/saved + heartbeat frontend
- [x] **B29** — **Lançar Preços** — módulo independente `/budget/lancar-precos` (menu Orçamento) · import Excel/PDF · matching SEMINF→SINAPI→SICRO→ORSE · gera orçamento PPD completo (sintético, analítico, cronograma, curvas)
- [x] **B30** — **Lançar Preços hierárquico** — import Excel · bases/períodos selecionáveis · sync preços · **histórico** · **busca manual** · matching reforçado (código importado · fallback relaxado · LLM · 2ª passagem) · export Excel/PDF hierárquico (PU/total s/ e c/ BDI · fórmulas BDI% + índice)
- [x] **B31** — **Snapshot CPUs analítico** — tabela `budget_composition_snapshots` · persistência no save/`generate-budget` · `GET /budget/{id}/compositions/batch` + backfill · aba analítico/histograma/curvas via 1 request · export analítico lê snapshot
- [x] **B32** — **Cache global CPUs** — tabela `composition_open_cache` (chave `code+reference+uf`, deduplicado) · migração lazy do legado B31 · `from_cache` na API batch · backfill lazy (`POST /compositions/backfill`) · save sem sync eager · benchmark real: **194 CPUs — cold ~299s (price_bank) vs warm ~60ms (cache)** · script `backend/scripts/bench_composition_cache.py`
- [x] **B17+** — UI checklist §4.U — `BudgetPilotChecklist` (4.U1–4.U7) na aba Dados + export JSON assinatura
- [ ] Piloto UI §4.U — **conferência humana** na `/budget` (marcar checklist + export assinatura; ver `docs/e2e_validation_checklist.md`)

### 8.1 Análise enterprise — módulo Orçamento (revisão 2026-06-29, pós B1–B22)

> Revisão ponta a ponta: UI `/budget` · backend `pricing/budget/` · export · bases · cronograma · auth · persistência.  
> Objetivo: avaliar prontidão para **empresa de grande porte** com obras **privadas** e **públicas (licitações)**.

#### Escopo analisado

| Camada | Componentes |
|--------|-------------|
| **Frontend** | 12 abas (`BudgetEtapasPanel`, `BudgetSpreadsheet`, analítico, busca CPU, memória, cronograma/Gantt, ABC/S/Histograma, especificação, histórico, WBS models) |
| **Backend** | `budget_engine.py`, `budget_db_service.py`, `budget_export_tables.py`, `budget_pdf_export.py`, `budget_pdf_charts.py`, `schedule_curves.py`, `budget_analytics.py`, rotas em `pricing.py` |
| **Bases** | SINAPI (Caixa, ComD/SemD), SICRO/DNIT, DP/SEMINF, TCPO/ORSE (indexados + filtros na Busca CPU — B5) |
| **Export** | PDF/Excel nativo (**11** tipos incl. `proposta_comercial`) + **`.xlsm` oficial** (B19) + `compliance-pack.json` (B22) |
| **Auth** | JWT + permissões por módulo; conversas e orçamentos isolados por `user_id` (B1) e **`empresa_id`/tenant** (B27); lock sessão concorrente (B28) |

#### Pontos positivos

| # | Capacidade | Relevância enterprise |
|---|------------|----------------------|
| 1 | **PPD MC/OR completo** — ComD/SemD paralelo, total adotado (menor), BDI SEMINF (8 tipos) | Atende fluxo interno SEMINF/SEINFRA e obras públicas estaduais similares |
| 2 | **WBS hierárquico** — etapas/sub-etapas/serviços, renumeração, esqueletos | Escala para obras grandes com dezenas de etapas |
| 3 | **CPU analítica** — expansão insumos, fórmula Caixa, variação mês anterior, busca ao vivo | Conferência técnica e defesa de preços unitários |
| 4 | **Multi-base** — SINAPI + SICRO + SEMINF no mesmo orçamento | Obras rodoviárias (SICRO) + edificações (SINAPI) + padrão estadual |
| 5 | **Cronograma CPM + Gantt** — sync orçamento→tarefas, curvas físico/financeiro, agente IA | Planejamento físico-financeiro exigido em licitações e contratos |
| 6 | **Analíticas** — Curva ABC, Curva S, Histograma MO+EQ por item (tabela + gráfico empilhado), cache CPUs | Gestão de custo, desembolso e controle gerencial |
| 7 | **Export institucional** — PDF paisagem/retrato, Excel com fórmulas, gráficos no PDF | Entrega a cliente/contratante sem depender de template externo |
| 8 | **Especificação técnica IA** — serviço a serviço, DOCX/PDF ABNT | Memorial descritivo automatizado para propostas |
| 9 | **Histórico + modelos WBS** — reuso entre obras | Ganho de produtividade em escritório grande |
| 10 | **Integração price_bank** — sync SINAPI/SICRO/SEMINF, prévia CPU, encargos MO por UF | Operação autônoma de bases sem planilha manual |

#### Pontos negativos / gaps

> **Revisão pós B1–B26:** **14/14 gaps fechados** no escopo técnico §8.1. Itens **estritamente institucionais** (publicação PNCP, assinatura humana §4.U) permanecem operacionais fora do código.

| # | Gap | Status | Impacto | Perfil afetado |
|---|-----|--------|---------|----------------|
| 1 | **Compliance licitação formal** — Lei 14.133, IN SEGES, PNCP, prestação de contas | ✅ Fechado (B22+B23) | — | Checklist L1–L7 + UI + JSON; L6/L7 PNCP/TCU **manual** por lei |
| 2 | **BDI fixo SEMINF** — perfis edital TCU + custom (B3) | ✅ Fechado (B3+B26) | — | Validador item a item vs perfil + alertas UI |
| 3 | ~~**Export nativo ≠ `.xlsm` oficial**~~ — **Resolvido (B19+B23)** | ✅ Fechado | — | Bridge + botão toolbar + piloto 4.U5 |
| 4 | ~~**TCPO/ORSE na UI**~~ — **Resolvido (B5)** | ✅ Fechado | — | Busca CPU multi-base |
| 5 | ~~**Sem `user_id`**~~ — **Resolvido (B1)** | ✅ Fechado | — | Ownership por usuário |
| 6 | ~~**Sem versionamento/lock**~~ — **Resolvido (B2)** | ✅ Fechado | — | Lock otimista |
| 7 | ~~**Sessão in-memory**~~ — **Resolvido (B11+B18)** | ✅ Fechado | — | Auto-save cliente + snapshot PostgreSQL + restore em `get()` |
| 8 | ~~**Pipeline LLM sem UI**~~ — **Resolvido (B4)** | ✅ Fechado | — | Produtividade IA |
| 9 | ~~**God file `pricing.py`**~~ — **Resolvido (B9/M6)** | ✅ Fechado | — | Sub-routers |
| 10 | ~~**Zero testes frontend**~~ — **Resolvido (B10/B14/B20/B25)** | ✅ Fechado | — | ~95 pytest + **14** Playwright mock + live API opcional |
| 11 | ~~**Curva S implícita**~~ — **Resolvido (B8)** | ✅ Fechado | — | Cenário adotado explícito |
| 12 | ~~**Auditoria incompleta**~~ — **Resolvido (B7+B16)** | ✅ Fechado | — | CPU, serviço, compose, qty, cronograma |
| 13 | ~~**CPQ comercial ausente**~~ — **Resolvido (B21)** | ✅ Fechado | — | Painel CPQ na aba Dados + margem % + `proposta_comercial` |
| 14 | ~~**Piloto obra real**~~ — **Resolvido (B12/B15/B17/B24)** | ✅ Fechado | — | API + script §4.U + automação 4.U5/4.U6; assinatura humana opcional |

#### Resumo cobertura gaps (pós B1–B26)

| Categoria | Gaps (#) | % aprox. |
|-----------|----------|----------|
| ✅ **Resolvidos** | 1–14 (todos) | **14/14 (100%)** |
| 🟡 **Mitigados** | — | **0/14** |
| 🔴 **Abertos (técnicos)** | — | **0/14** |

**Veredito:** ciclo **B1–B28** fecha **100%** dos gaps técnicos §8.1 + melhorias SaaS orçamento (tenant + lock). Pendências restantes: **assinatura humana** §4.U (processo) e **PNCP** (publicação manual).

#### Matriz de prontidão

| Perfil de uso | Nível | Comentário |
|---------------|-------|------------|
| **Obra pública SEMINF/SEINFRA-like** (produção interna) | 🟢 **Muito alta** | Fluxo completo + auditoria + snapshot + export `.xlsm` |
| **Licitação / compliance formal** (14.133, TCU, PNCP) | 🟢 **Alta** | B22+B23 checklist/UI + B26 BDI; PNCP publicação manual |
| **Obra privada / CPQ comercial** | 🟢 **Alta** | B21 painel CPQ + margem + export `proposta_comercial` |
| **SaaS multi-equipe enterprise** | 🟢 **Alta** | B1/B2/B16/B18/B27 tenant + B28 lock sessão; membership formal user↔company opcional |

#### Roadmap de melhorias — Orçamento (B1–B15 concluído · B16+ próximo)

| # | Melhoria | Prioridade | Esforço | Benefício |
|---|----------|------------|---------|-----------|
| **B1** | `user_id` + filtros em `budget_documents` | Alta | Médio | ✅ ownership + filtro por usuário |
| **B2** | Versionamento + lock otimista (`version`, `expected_version`) | Alta | Médio | ✅ HTTP 409 em conflito |
| **B3** | BDI configurável por edital + decomposição TCU | Alta | Alto | ✅ perfis edital + painel Dados |
| **B4** | UI import PPD + pipeline LLM (`BudgetPipelinePanel`) | Média | Médio | ✅ import PPD + pipeline SSE na aba Histórico |
| **B5** | Expor TCPO/ORSE na UI (busca CPU + lançamento) | Média | Baixo | ✅ filtros TCPO/ORSE na Busca CPU |
| **B6** | Fluxo aditivo — baseline congelada + revisão N | Alta | Alto | ✅ congelar + aditivo + compare |
| **B7** | Auditoria célula/BDI/CPU/cronograma (`budget_audit_log`) | Alta | Médio | ✅ B7+B16 completo |
| **B8** | Curva S export — cenário adotado explícito | Baixa | Baixo | ✅ UI + PDF/Excel (ComD/SemD, totais, BDI) |
| **B9** | Split `pricing.py` → sub-routers (alias M6) | Média | Médio | ✅ `app/routes/pricing/` (providers, sync, budget, tech_spec, export) |
| **B10** | Testes E2E frontend orçamento (Playwright) | Média | Médio | ✅ **12** testes (`make test-budget-e2e`) |
| **B11** | Persistência sessão — auto-save periódico + heartbeat restore | Média | Médio | ✅ hook 60s/180s + indicador toolbar |
| **B12** | Piloto obra real + checklist validação | Alta | Baixo (processo) | ✅ `test_budget_pilot_flow` + `make validate-budget-pilot` + esqueleto `sk-b12-piloto-passarela` |
| **B13** | Lançar CPU da Busca CPU direto na etapa | Média | Baixo | ✅ painel etapa/qtd + `pricingAddService` + E2E |
| **B14** | CI GitHub Actions — pytest orçamento + Playwright `/budget` | Média | Baixo | ✅ `.github/workflows/ci.yml` + `make test-ci` |
| **B15** | Piloto campo §4 — script live + pytest exports (sintético, analítico, ABC, MCQ, cronograma) | Alta | Médio | ✅ `validate-budget-pilot` + `test_pilot_section4_field_checklist` · CI +`test_budget_export` / `test_budget_analytics` |

**Ciclo B27–B28 concluído.** Próximo: **assinatura humana** §4.U · M10 `project.user_id` (transversal).

#### Ciclo B27–B28 (concluído)

| # | Melhoria | Status | Fecha gap / benefício |
|---|----------|--------|------------------------|
| **B27** | Tenant multi-empresa — `empresa_id`, `X-Tenant-Id`, selector UI, paths MinIO | ✅ | SaaS multi-equipe · isolamento orçamentos |
| **B28** | Lock sessão concorrente — TTL, renew, guard edição, UI heartbeat | ✅ | Edição paralela segura |

#### Ciclo B23–B26 (concluído)

| # | Melhoria | Status | Fecha gap |
|---|----------|--------|-----------|
| **B23** | UI licitação — `.xlsm` + compliance toolbar + painel Dados | ✅ | #1, #3 |
| **B24** | Piloto API ampliado (4.U5/4.U6 + BDI validation) | ✅ | #14 |
| **B25** | Playwright export API real (`budget-live.spec.ts`) | ✅ | #10 |
| **B26** | Validador BDI vs edital TCU | ✅ | #2 |

#### Ciclo B16–B22 (concluído)

| # | Melhoria | Status | Fecha gap |
|---|----------|--------|-----------|
| **B16** | Auditoria completa CPU/serviço/cronograma | ✅ | #12 |
| **B17** | Piloto UI §4.U — `make validate-budget-pilot-ui` | ✅ script | #14 |
| **B18** | Snapshot `SESSION_STORE` PostgreSQL | ✅ | #7 |
| **B19** | Export `.xlsm` oficial + workbook sync | ✅ | #3 |
| **B20** | Testes export ampliados (pytest + Playwright toolbar) | ✅ | #10 |
| **B21** | CPQ — UI `BudgetCommercialPanel` + margem + `proposta_comercial` | ✅ | #13 |
| **B22** | Pacote compliance `compliance-pack.json` | ✅ | #1 |

#### Fluxo atual vs ideal (enterprise)

```txt
HOJE (produção — pós B1–B28)
  novo orçamento → WBS/esqueleto → lançamento CPUs (B13) → ComD/SemD → cronograma
  → analíticas → export PDF/Excel (11 docs) + .xlsm oficial (B19) + compliance-pack (B22)
  → ownership (B1) · versionamento (B2) · BDI configurável (B3) · auditoria completa (B16)
  → snapshot PostgreSQL (B18) · auto-save (B11) · CI pytest + Playwright (B14/B20/B25)
  → CPQ painel Dados + proposta comercial com margem (B21)
  → tenant empresa (B27) · lock sessão concorrente (B28) · checklist §4.U na UI (B17+)
  ⚠ §4.U conferência humana (marcar + export JSON) · PNCP publicação manual

IDEAL (enterprise licitação + privado)
  projeto vinculado → orçamento baseline (lock) → equipe paralela (tenant + lock sessão) ✅
  → BDI validado por edital → revisões/aditivos versionados → auditoria completa por operação
  → export edital (.xlsm ou nativo certificado) + PNCP/TCU pack
  → proposta comercial (obra privada) com margem
```

#### Conclusão

O módulo orçamento atinge **maturidade técnica enterprise** para operação SEMINF/SEINFRA-like, defesa contratual e SaaS multi-equipe: ciclo **B1–B28** fecha gaps §8.1 e melhorias de produto (tenant, lock). Pendências são **operacionais** (validação humana §4.U, publicação PNCP).

### 8.2 Análise enterprise — módulo Laudos de Vistoria (2026-07-24)

> Revisão baseada em código: `backend/core/inspection_report/*`, `app/routes/inspection_reports.py`, `frontend/app/inspection-reports/`, `InspectionPartyList`, testes e decision log.

#### Snapshot (o que está entregue)

| Capacidade | Status | Evidência |
|------------|--------|-----------|
| Templates tipología (9 slugs) + capítulos SEMINF/Bariri 1–16 | 🟢 | `migrate.py` · `constants.DEFAULT_CHAPTERS` |
| Gemini multimodal 2 passagens (diagnóstico ≤16 imgs + legendas lote 8) | 🟢 | `gemini_client.generate_laudo_content` · modelo `GEMINI_MODEL` |
| SSE geração + modal % | 🟢 | `generate/stream` · UI `GENERATE_STAGES` |
| Solicitante / RT+ART / responsáveis fotos | 🟢 | PATCH `content` · sobrevivem à regeneração |
| Georref EXIF → ficha + imagem sob tabela + preview UI | 🟢 | `geo_utils` · kind `georef` · `GET …/file` |
| Export Word/PDF institucional (logo, watermark 16,5 cm, analytics, 1 foto/página, assinaturas) | 🟢 | `docx_export` · `pdf_export` |
| Progresso visual na exportação | 🟢 | modal círculo + `downloadApiFile` |
| Correção profissional | 🟢 | SSE `/correct/stream` + resumo JSON ≤6k (L2) |
| Isolamento por usuário | 🟢 | `user_id` no create + filtro list + 403 em get/export (L1) |
| Capítulos por tipología | 🟢 | `CHAPTERS_BY_SLUG` / `PROMPT_EXTRAS_BY_SLUG` (L3) |
| Georref no Gemini | 🟢 | Passagem 1 inclui imagem + coords (L4) |
| Limites / cancel | 🟢 | 25 MB · 80 fotos · cancel generation (L6) |
| Edição humana | 🟢 | PATCH chapters / photographic_report / caption asset (L7) |
| Vínculo projeto | 🟢 | `project_id` + `record_activity` (L8) |
| Checklist oficial | 🟢 | CNPJ/CREA/ART + export `?strict=1` (L9) |
| Testes | 🟢 | georef→DOCX · PDF · parties · isolamento · tipología · checklist (L5) |

#### Pontos positivos

1. **Laudo institucional utilizável** — branding empresa, watermark, capítulos numerados, fotográfico 1/página, analytics de patologias, assinaturas tipográficas dos RT.
2. **Pipeline multimodal pragmático** — amostragem + lotes evita estourar contexto/custo com dezenas de fotos.
3. **Metadados humanos sobrevivem ao Gemini** — solicitante, RT/ART, fotógrafos e georref são reaplicados após a geração.
4. **UX operacional** — SSE na geração, preview georref, confirmação ao editar/excluir responsáveis, loading na exportação.
5. **Hardening útil** — repair JSON truncado, strip NUL de PDF, replace de georef único, fallback de legendas pedindo revisão humana.

#### Pontos negativos / riscos

| # | Problema | Impacto |
|---|----------|---------|
| 1 | Assinatura tipográfica (sem ICP-Brasil) | Não substitui assinatura digital legal |
| 2 | ~~Diagnóstico limitado a ≤16 fotos na passagem 1~~ | Mitigado L14 — estratificação + ondas de cobertura |
| 3 | ~~Laudos legados com `user_id` NULL~~ | Mitigado — órfãos só admin + claim/backfill |

#### Melhorias sugeridas (backlog L) — ciclo L1–L9 ✅ 2026-07-24

| ID | Prioridade | Melhoria | Status |
|----|------------|----------|--------|
| **L1** | P0 | Isolamento `user_id` + 403 | ✅ |
| **L2** | P0 | SSE correção + truncar prompt | ✅ |
| **L3** | P1 | Capítulos/prompt por tipología | ✅ |
| **L4** | P1 | Georref na passagem 1 Gemini | ✅ |
| **L5** | P1 | Testes georef/PDF/parties/isolamento | ✅ |
| **L6** | P1 | Limites upload + cancel geração | ✅ |
| **L7** | P2 | Edição humana capítulos/legendas | ✅ |
| **L8** | P2 | `project_id` + activity | ✅ |
| **L9** | P2 | Validação CNPJ/CREA/ART + checklist | ✅ |

#### Conclusão

O módulo Laudos atingiu **maturidade enterprise técnica** no ciclo **L1–L9**: isolamento multi-usuário, correção com progresso, tipologías diferenciadas, georref multimodal, limites/cancel, edição humana, vínculo a projeto e checklist pré-export oficial. Pendência residual: assinatura digital ICP-Brasil (fora de escopo curto).

### 8.2.1 Revisão plenária de engenharia — Laudos (2026-07-25)

> Ótica: engenheiro civil pleno em vistorias/laudos (OAE, erosão, edificação, geotécnica).  
> Entrega visual: canvas `laudos-analise-engenharia.canvas.tsx`.

#### Veredito

| Dimensão | Nível | Comentário |
|----------|-------|------------|
| Operação / SaaS | 🟢 Alto | L1–L9, SSE, export, checklist |
| Forma institucional | 🟢 Alto | Capa, sumário, RT/ART, fotográfico |
| Precisão normativa | 🟢 Médio–alto | Motor L10: notas DNIT 1–5 + classificação global (pior governa) |
| Metrologia / evidência | 🟢 Médio | L12: campos tipados + extração de texto; ensaios = sugestão |
| Ato de interdição | 🟢 Médio | L13: capítulo tipado (tipo, prazo, autoridade, liberação, sinalização) |
| Assinatura legal | 🟡 Mitigado | L19 hash + PAdES opcional (cert A1); TSA/A3 futuro |

#### Backlog engenharia L10–L19 (novo)

| ID | Pri | Melhoria |
|----|-----|----------|
| **L10** | P0 | ✅ Motor classificação NBR 9452 / DNIT (`classification.py` + enrichment) |
| **L11** | P0 | ✅ Inventário estruturado de elementos (`elements.py` · catálogos por slug) |
| **L12** | P0 | ✅ Campos metrológicos tipados (`metrology.py` · fissura/seção/espessura/…) |
| **L13** | P1 | ✅ Ato de interdição tipado (`interdiction.py` · total/parcial · liberação) |
| **L14** | P1 | ✅ Cobertura fotográfica estratificada (`photo_coverage.py` · soft 24 + ondas) |
| **L15** | P1 | ✅ RAG normativo por tipología + citação rastreável (`normative_rag.py`) |
| **L16** | P1 | ✅ Resultados de ensaio medidos (`assay_results.py` · API · UI L16) |
| **L17** | P2 | ✅ Memória visual croqui/overlay cotado (`visual_memory.py` · canvas UI) |
| **L18** | P2 | ✅ ART rastreável — PDF `kind=art` + protocolo/URL + tabela export |
| **L19** | P2 | ✅ Evidência assinatura — imagem firma + SHA-256 PDF (PAdES futuro) |

#### Sequência sugerida

1. ~~**L10 + L11 + L12**~~ ✅ — classificação DNIT · inventário · metrologia  
2. ~~**L13 + L14**~~ ✅ — interdição · cobertura fotográfica estratificada/ondas  
3. ~~**L15**~~ ✅ — RAG normativo por tipología + citações rastreáveis  
4. ~~**L16**~~ ✅ — ensaios medidos · ~~**L17–L19 MVP**~~ ✅ — croqui · ART anexo · evidência hash/firma (PAdES/SICAR live = follow-up)

##### Protocolo CREA/perícia (2026-07-25)

Pacote P0–P2 no export: `protocol_order.py` (TOC/ordem/dedupe) · governing = pior elemento · metrologia sem `measured` falso · ensaios top-8 · ART/CREA em linhas na capa · índice fotográfico · georref só com GPS · marca d’água 6%.

##### L14 — cobertura fotográfica (2026-07-25)

- `photo_coverage.py`: amostra estratificada (extremos + legendadas + orientação) até soft_cap 24  
- Ondas de cobertura (batches) sobre fotos restantes → `pathologies_delta` merge  
- Stats em `content.photo_coverage` · progresso SSE “L14 cobertura…”  
- Tie-break governante: prioridade estrutural (longarina > tabuleiro em empate de nota)  
- Índice foto: `pathology_refs` só códigos P0N (ignora texto livre)

##### Mapa de localização satélite (2026-07-25)

- `location_map.py`: PNG satélite + marcador a partir do GPS da foto georref/capa
- Provedores: Google Static Maps (opcional `GOOGLE_MAPS_STATIC_API_KEY`) → Esri World Imagery (sem chave) → fallback esquemático
- Cache em `{report_dir}/location_map.png` · inserção Word/PDF abaixo da imagem georref na ficha técnica
- Quadro fixo 5,9×3,7" (borda cinza + letterbox) · legendas sem coordenadas duplicadas
- Mapa norte no topo + seta N (letra acima, ponta para cima) · cache `location_map_v3.png`
- Fallback de coordenadas: `content.georreferencia` ou EXIF de outra foto `image`/`georef`
- Export Word/PDF aplica `ImageOps.exif_transpose` (`open_image_upright` / `image_bytes_for_export`) — fotos retrato não saem deitadas

##### L15 — RAG normativo por tipología (2026-07-26)

- `normative_rag.py`: queries/NBRs por slug · `retrieve_for_agent` · `content.normative_citations`
- Geração: modo `attachments_and_kb` injeta `context_text` L15 no Gemini + enrichment
- Capítulo Referências: tabela Norma | Item | Trecho | Fonte | Score (Word/PDF)
- Prompt L15: citar preferencialmente trechos do contexto RAG (sem inventar cláusulas)

##### L16 — resultados medidos de ensaios (2026-07-27)

- `assay_results.py`: schema `instrumented_test_results` · validação · tabela export L16
- API: `GET/PUT /inspection-reports/{id}/assay-results`
- UI: `InspectionAssayResultsPanel` — cadastro pós-campo/lab · pré-preenchimento dos ensaios sugeridos
- Enrichment: `apply_assay_results_to_content` no capítulo ensaios + nota em conclusões
- Metrologia: `pathology_refs_with_executed_results` vincula patologia a ensaio executado

##### L17 — croqui cotado (2026-07-27)

- `visual_memory.py`: overlays normalizados 0–1 · render Pillow · API `GET/PUT …/visual-memory`
- UI `InspectionVisualMemoryEditor` — linha/seta/retângulo/círculo/rótulo sobre a foto
- Estilo por overlay: `color` · `stroke` (1–12) · `font_size` · `filled` · painel de caneta + edição do selecionado
- Export Word/PDF usa foto com overlay quando houver croqui
- **2026-07-27 fix:** export JPEG max 1400px/q80 (antes PNG full-res → PDF ~89 MB / timeout proxy); hash L19 não bloqueia download se commit falhar; `/system/benchmark` público + backoff no painel quando API cai

##### L18 — ART rastreável (2026-07-27)

- Party: `art_asset_id` · `art_protocolo` · `art_url` · upload `kind=art` (PDF)
- Checklist: warning só se sem ART textual **e** sem anexo
- Tabela “ART e documentos técnicos” no export

##### L19 — evidência de assinatura (2026-07-27)

- Upload `kind=signature` (imagem de firma) vinculada ao RT
- Export PDF grava `signature_evidence.pdf_sha256` (SHA-256) + header `X-Laudo-PDF-SHA256`
- Bloco de assinatura usa imagem quando disponível
- **PAdES (follow-up):** `pades_sign.py` + `LAUDO_PADES_ENABLED` / `LAUDO_PADES_P12_PATH` / senha · pyhanko assina no export quando ready · method=`pades` · header `X-Laudo-PDF-Sign-Method`

##### Follow-up pós L19 (2026-07-27)

- **Órfãos:** `user_id` NULL só admin vê/acessa · `POST …/claim` · `POST …/assign` · `POST …/orphans/backfill` · UI admin
- **ART/SICAR live:** `art_lookup.py` monta URL CREA por UF + link SICAR público · sonda HTTP · UI “Consultar ART / SICAR”
- Risco residual: PAdES exige certificado A1 real em produção (sem cert = L19 hash)

## Intent Layer v2

| Status | 🟢 Ativo em `/chat` (`USE_INTENT_LAYER=true`) |
|--------|------------------------------------------------|
| **Path** | `core/intent_layer.py` |
| **Modos** | `chat_only` \| `engineering_only` \| `mixed` |
| **Mixed** | Separa saudação + técnica → ChatAgent + agente especializado |

### Fluxo

```txt
input → analyze_intent()
          ├─ chat_only        → ChatAgent
          ├─ engineering_only → route_engineering_only → agente
          └─ mixed            → plano 2 passos → merge resposta
```

### Payload (`intent` no response)

```json
{
  "mode": "mixed",
  "confidence": 0.93,
  "chat_segment": "oi",
  "technical_segment": "preciso dimensionar viga",
  "technical_discipline": "ESTRUTURAL",
  "execution_plan": [
    {"step": 1, "domain": "chat", "discipline": "CHAT", "agent": "chat_agent"},
    {"step": 2, "domain": "engineering", "discipline": "ESTRUTURAL", "agent": "estruturas_agent"}
  ]
}
```

---

| Status | 🟡 Módulo implementado — integração Orchestrator v2 pendente |
|--------|--------------------------------------------------------------|
| **Path** | `core/context_graph.py` |
| **Objetivo** | Grafo de contexto compartilhado entre disciplinas durante orquestração |
| **Problema que resolve** | Hoje cada agente opera isolado; estrutural não "sabe" o que hidráulico decidiu |

### API principal

| Método | Descrição |
|--------|-----------|
| `add_result(discipline, data, depends_on?)` | Registra resultado + histórico incremental |
| `get(discipline)` | Nó mais recente da disciplina |
| `get_related(discipline)` | Consulta cruzada (disciplina + dependências) |
| `query(disciplines)` | Consulta por lista explícita |
| `merge_contexts(disciplines?, other?)` | Consolida dados entre disciplinas |
| `build_global_context()` | Texto para injeção em prompts |
| `to_dict()` / `from_dict()` / `to_json()` / `from_json()` | Serialização PostgreSQL futuro |

**Testes:** `tests/test_context_graph.py`

---

## AED v1 (Autonomous Engineering Designer)

| Status | 🟢 Implementado — pipeline paralelo ao Copilot/Orchestrator |
|--------|--------------------------------------------------------------|
| **Path** | `core/aed/` |
| **Endpoint** | `POST /aed` |
| **Restrição** | Não altera agentes, RAG v2, router, dispatcher nem orchestrator |

### Pipeline

```txt
input → project_understanding → design_generator (≥2 opções/disciplina)
      → engineering_simulator (RAG v2 read-only + heurísticas + histórico PG)
      → comparison_engine (segurança, custo, execução, manutenção, compliance)
      → selection_engine (weighted scoring + penalidades de risco)
      → report_generator (solução escolhida, alternativas, normas, riscos)
      → audit (aed_runs, opcional persist=true)
```

### Módulos

| Arquivo | Responsabilidade |
|---------|------------------|
| `project_understanding.py` | Intent, disciplinas, objetivos, restrições (reusa Copilot intent/planner) |
| `design_generator.py` | Gera opções técnicas (conservative / optimized / …) por disciplina |
| `engineering_simulator.py` | Scores via RAG v2, heurísticas, regras e histórico PostgreSQL |
| `comparison_engine.py` | Ranking multi-critério entre alternativas |
| `selection_engine.py` | Seleção final com pesos e penalidades de risco |
| `report_generator.py` | Relatório técnico markdown estruturado |
| `aed_orchestrator.py` | Orquestra pipeline `run_aed()` |
| `audit.py` | Persistência auditável em `aed_runs` |

**Testes:** `tests/test_aed.py`

---

## Structural System Selector v1

| Status | 🟢 Implementado — plugável no pipeline AED |
|--------|---------------------------------------------|
| **Path** | `core/structural_selector/` |
| **Integração** | Roda após design generation, antes do `engineering_simulator` |
| **Restrição** | Não altera RAG v2, router, agentes nem orchestrator |

### Sistemas suportados

`CONCRETE_ARMED` · `CONCRETE_PRESTRESSED` · `PRECAST_CONCRETE` · `STEEL_STRUCTURE` · `TIMBER_STRUCTURE` · `MIXED_SYSTEMS`

### Módulos

| Arquivo | Responsabilidade |
|---------|------------------|
| `system_registry.py` | Enum de sistemas + metadados (`simulation_module`) |
| `norms_mapper.py` | Mapeamento automático NBR por sistema |
| `rules_based_selector.py` | Heurísticas determinísticas (vão, tipologia, leveza) |
| `llm_fallback_selector.py` | Fallback Ollama quando confiança < 0.55 |
| `system_classifier.py` | Entrada `select_structural_system()` → `StructuralSelection` |

### Heurísticas iniciais

| Sinal | Sistema tendencial |
|-------|-------------------|
| Grandes vãos | `STEEL_STRUCTURE` |
| Residencial / baixa altura | `CONCRETE_ARMED` |
| Industrial | `STEEL_STRUCTURE` / `PRECAST_CONCRETE` |
| Leveza estrutural | `STEEL_STRUCTURE` / `TIMBER_STRUCTURE` |

### Normas por sistema

| Sistema | Normas |
|---------|--------|
| Concreto armado / protendido | NBR 6118, NBR 8681 |
| Pré-moldado | NBR 9062, NBR 6118 |
| Aço | NBR 8800 |
| Madeira | NBR 7190 |

**Saída:** `structural_system`, `norm_set`, `simulation_module`, `confidence`, `method`, `rationale`

**Testes:** `tests/test_structural_selector.py`

---

# 🔴 3. ROADMAP TÉCNICO — ROTEIRO DE TAREFAS

> Legenda: ✅ concluído · 🟡 em progresso · 🔴 pendente · ⏸ bloqueado

---

## Fase 0 — Core Infraestrutura ✅ CONCLUÍDA

- [x] FastAPI gateway + CORS + OpenAPI
- [x] Router v2 (regras → LLM → GERAL)
- [x] Agent Registry (fonte única de nomes)
- [x] Dispatcher + persistência `agent_runs`
- [x] Orchestrator v1 (decompose → execute → synthesize)
- [x] PostgreSQL (conversations, logs, runs, feedback)
- [x] Frontend base (`/chat`, `/orchestrate`, `/history`)
- [x] RAG v2 pipeline (FAISS, chunker, retriever, indexer)
- [x] 15 agentes inteligentes (`BaseAgentIntelligent`)
- [x] Cliente Ollama com fallback de modelo
- [x] Intent Layer v2 (`/chat` + `/chat/stream` SSE)
- [x] ChatAgent (disciplina CHAT)

---

## Fase 1 — Inteligência de Agentes 🟡 85%

- [x] `BaseAgentIntelligent` (RAG + LLM)
- [x] Integração no dispatcher (`USE_INTELLIGENT_AGENTS`)
- [x] Factory inteligente para 15 disciplinas
- [x] Propagação `use_rag` (chat + orchestrator)
- [x] Streaming SSE no chat (`POST /chat/stream`)
- [x] Streaming UX instantâneo (evento `connected` + render ~60fps)
- [x] Metadata de modelo ativo no health + frontend
- [x] **Indexar NBRs** — 68 PDFs · 636+ chunks via `/settings`
- [x] Agente geotécnico dedicado (`GeotecniaIntelligentAgent`)
- [ ] **Indexar SINAPI/TCPO** ← bloqueio orçamento
- [ ] Prompts especializados por disciplina (Learning v2 parcial — só ESTRUTURAL)
- [ ] Ativar `USE_TUNED_PROMPTS=true` após validação
- [ ] Validação pós-LLM de tabelas/nomenclaturas normativas
- [ ] Agentes customizados além de `estruturas_intelligent.py`
- [ ] Remover/desativar agentes legados simulados

---

## Fase 1b — Loops de Evolução ✅ CONCLUÍDA

- [x] Learning Loop v1 — `agent_feedback` + `POST /feedback`
- [x] Learning Loop v2 — profiles + prompts versionados + `run_auto_tune.py`
- [x] Copilot v1 — intent → plan → execute → synthesize → evaluate
- [x] Evaluation Loop v2 — autoavaliação 4 níveis + `copilot_evaluations`
- [x] Self-Improving Loop v1 — meta-análise + patches propostos (sem auto-apply)
- [x] Integração background no `/copilot` (evaluation + self-improving)
- [x] Evolution Loop v1 — sinais + mutações + rollout seguro + RAG evolution
- [x] Agent Generation Loop v1 — proposta + sandbox + promotion gate (controlled)
- [x] Model Router v1 — roteamento LLM por `task_type` + `GET /models/status`
- [x] Model Evaluation Loop v1 — comparação primary/fallback + `model_performance_profile`
- [x] SIE v1 — Structural Intelligence Engine (ESTRUTURAL only)
- [x] Monorepo `backend/` + `frontend/`

---

## Fase 2 — Orquestração + Engenharia Autônoma 🟡 90% ← ESTAMOS AQUI

### Knowledge + RAG (concluído nesta fase)

- [x] Storage flat (`knowledge/raw/documents/` + sidecars + `catalog.jsonl`)
- [x] RAG agent-aware (`core/knowledge/rag/`) — escopo por agente
- [x] Engineering Orchestrator — NBR ≠ SINAPI/TCPO
- [x] RAG performance (cache semântico, métricas, index-first)
- [x] **Popular PDFs e indexar** — 68 NBRs via `/settings` (636+ chunks FAISS)

### Workspace + Project RAG ✅

- [x] Modelos DB: `Project`, `ProjectFile`, `ConversationMessage` + migração
- [x] API workspace: projetos, arquivos, conversas, busca, reindex
- [x] Chat multi-turn (`conversation_id`, `project_id`, thread context)
- [x] Project RAG — FAISS isolado por projeto
- [x] Extractors multi-formato (PDF, Office, CSV, TXT, DXF, IFC, DWG parcial)
- [x] Frontend: `/projects`, painel workspace no `/chat`, upload multi-formato
- [ ] Validar qualidade RAG com arquivos reais de empreendimento
- [ ] Reindexar projetos existentes após deploy de novos formatos

### Orchestrator v2 (parcial)

- [x] ContextGraph (módulo + serialização JSON)
- [x] Integrar ContextGraph em `execute_agents` / Copilot
- [ ] Execution Planner (ordem e dependências entre disciplinas)
- [ ] Propagação de premissas entre agentes
- [ ] Fluxo estruturado (briefing → análise → síntese → revisão)

### AED — Autonomous Engineering Designer ✅

- [x] `core/aed/` — pipeline completo (7 módulos)
- [x] `POST /aed` + schema + service
- [x] Persistência auditável (`aed_runs`)
- [x] ≥2 opções técnicas por disciplina
- [x] Comparação multi-critério + seleção weighted
- [x] Relatório técnico estruturado
- [ ] Frontend `/aed`
- [ ] Integração Copilot → AED (disparo automático)

### Structural System Selector ✅

- [x] `core/structural_selector/` — 5 módulos
- [x] 6 sistemas estruturais + mapeamento NBR
- [x] Heurísticas + LLM fallback
- [x] Integração no AED (pré-simulação)
- [ ] Simuladores dedicados por `simulation_module` (hoje só roteamento/metadata)
- [ ] Expandir heurísticas (spans numéricos, cargas, seismic zone)

### SIE v1 — Structural Intelligence Engine ✅

- [x] `core/structural_intelligence/` — classificação + normas + prompt + LLM
- [x] Integração via `dispatch_adapter` só para ESTRUTURAL
- [x] Fallback seguro para fluxo padrão do agente
- [ ] Expandir para outras disciplinas (futuro)

### Model Router + Evaluation ✅ (opt-in)

- [x] `core/models/model_router.py` — mapa por task_type (phi3, mistral, gemma4, deepseek-r1, gemma3, qwen2.5-coder, etc.)
- [x] `core/models/model_evaluation_loop.py` — primary vs fallback + PostgreSQL
- [x] `GET /models/status`
- [ ] Ativar `USE_MODEL_ROUTER=true` após validação em staging

### Orçamento + Cronograma ✅ (Jun/26)

- [x] Budget Engine v2 — sessão editável, BDI ComD/SemD, memória de cálculo
- [x] Import/export PPD MC/OR (.xlsm)
- [x] UI ComD/SemD — colunas paralelas, custo sem BDI, valor BDI, total adotado (menor)
- [x] Renumeração WBS (`renumber_wbs`) — automática ao excluir + botão toolbar
- [x] Cronograma CPM — sync orçamento, vínculos FS/SS/FF/SF, recálculo
- [x] Gantt frontend — curvas mensais, datas dd/mm/aaaa, visão etapas/completo
- [x] Agente IA cronograma — catálogo WBS, intent, fallback heurístico
- [x] Persistência cronograma em sessão salva (`budget_db_service`)
- [ ] Export Excel alinhado ao layout ComD/SemD da UI
- [ ] Curva financeira do cronograma usando cenário adotado (ComD vs SemD) de forma explícita

### Laudos de Vistoria 🟢 (Jul/25) — §8.2 L1–L19 MVP ✅

- [x] CRUD + templates seed (9 tipologías) + anexos PDF/fotos
- [x] Gemini 2 passagens + SSE geração + RAG opcional
- [x] Solicitante · RT/ART · responsáveis fotos · georref EXIF
- [x] Export Word/PDF institucional + analytics + assinaturas + progresso export
- [x] Sumário na página 2 (Word/PDF) + `ensure_sumario_chapter`
- [x] **Capa 1ª folha** em blocos/tabelas KV (identificação · solicitante · RT) — rótulos em negrito
- [x] **Ensaios instrumentados** — checkbox UI + catálogo por tipología/gravidade + capítulo no laudo
- [x] **L10–L12** Classificação NBR/DNIT · inventário elementos · metrologia tipada (§8.2.1)
- [x] **L13** Ato de interdição tipado + pacote protocolo (TOC · ordem · top-N ensaios · índice foto)
- [x] **L14** Cobertura fotográfica estratificada + ondas (sem teto cego ≤16)
- [x] Mapa satélite de localização (GPS georref → Word/PDF abaixo da capa)
- [x] **L15** RAG normativo por tipología + citação rastreável (`normative_citations`)
- [x] **L16** Resultados medidos de ensaios (`instrumented_test_results` · API · UI · tabela export)
- [x] **L17** Croqui cotado (`visual_memory` · canvas · overlay no Word/PDF)
- [x] **L18** ART PDF rastreável (`kind=art` · protocolo/URL · tabela export)
- [x] **L19** Evidência assinatura (imagem firma + SHA-256 PDF; PAdES futuro)
- [x] Follow-up: ART/SICAR live (`art_lookup` · botão consulta) · órfãos só admin + claim/backfill · PAdES opcional (pyHanko + `LAUDO_PADES_*`)
- [x] **L1** Isolamento `user_id` (R-25 mitigado)
- [x] **L2** SSE na correção + prompt truncado (R-26)
- [x] **L3** Capítulos/prompt por tipología (R-27)
- [x] **L4** Georref na passagem 1 Gemini
- [x] **L5** Testes georef/PDF/parties/isolamento/tipología
- [x] **L6** Limites upload + cancel geração
- [x] **L7** Edição humana capítulos/legendas
- [x] **L8** `project_id` + activity timeline
- [x] **L9** Checklist CNPJ/CREA/ART + export strict

---

## Fase 3 — RAG Avançado 🟡 EM PROGRESSO (~50%)

- [x] RAG por agente com isolamento (escopo + hard block SINAPI/NBR)
- [x] Orquestrador engenharia vs orçamento (`engineering_orchestrator`)
- [x] Cache semântico + métricas de latência
- [x] Rerank por domínio (+NBR oficial, +SINAPI, penalties cross-domain)
- [x] Storage flat metadata-driven (`raw/documents/`)
- [x] **Project RAG** — contexto por empreendimento (FAISS dedicado, multi-formato)
- [ ] Indexação TDRs além de NBRs (pipeline pronto, falta PDFs)
- [ ] Indexação SINAPI/TCPO (pipeline pronto, falta arquivos)
- [ ] Re-ranking cross-encoder ou LLM reranker (opcional)
- [ ] Métricas recall/precisão por disciplina com dados reais

---

## Fase 4 — SaaS Real 🟡 EM ANDAMENTO

- [x] JWT Authentication (`AUTH_ENABLED`, middleware, `/auth/*`)
- [x] Multiusuário (admin + dev_user; seed + CRUD em `/settings/users`)
- [x] **Conversas isoladas por usuário** (`conversations.user_id`, filtros em chat/workspace/history/orchestrate)
- [x] Workspace local (projetos + conversas + arquivos) — projetos ainda compartilhados entre usuários
- [x] Painel de acesso rede interna + Cloudflare (`/settings/access`)
- [x] Quick Tunnel temporário no painel (`POST /system/network-access/quick-tunnel/start|stop`)
- [x] Proxy same-origin `/api-backend` (LAN + trycloudflare sem porta 8000 no cliente)
- [ ] Projetos por usuário / tenant (SaaS multi-tenant)
- [ ] Isolamento de contexto RAG por tenant
- [ ] Billing / planos
- [ ] Deploy produção (Netlify ou VPS + Docker)

---

## Backlog transversal (qualquer fase)

| Tarefa | Fase | Prioridade |
|--------|------|------------|
| Validar Project RAG (`/chat?project=`) com DOCX/XLSX/IFC | 2 | 🔴 Crítica |
| Indexar SINAPI/TCPO em `knowledge/raw/documents/` | 1 | 🔴 Crítica |
| Export Excel PPD alinhado ComD/SemD | 2 | Média |
| Validar agente cronograma em obra real | 2 | Média |
| Página frontend `/aed` | 2 | Alta |
| Página frontend `/copilot` | 1b | Alta |
| `concrete_armed_simulator` (primeiro simulador real) | 2 | Alta |
| Execution Planner no Orchestrator | 2 | Alta |
| Validação normativa pós-LLM | 1 | Média |
| GPU / otimização de latência | 1 | Baixa (keep_alive, cache Ollama, fix CPU por VRAM) |
| Auth JWT | 4 | ~~Baixa~~ Concluído (equipe local) |
| Testes smoke E2E (auth + chat + upload LAN) | 4 | Alta |
| `pytest-cov` + CI mínima (`make test`) | 4 | Alta |
| Modularizar `pricing.py` e `api.ts` | transversal | Média |
| Hardening exposição externa (JWT, CORS, senhas seed) | 4 | Alta |
| Desbloquear `test_workflow_projetos` (PostgreSQL test) | 2 | Média |
| Consolidar/remover `backend/experimental/` duplicado | transversal | Baixa |

---

# 🧠 4. ARQUITETURA ATUAL

## Fluxo single-domain (chat)

```txt
Frontend (Next.js) — ?c= / ?project=
    ↓ POST /chat ou /chat/stream { conversation_id?, project_id? }
FastAPI Gateway
    ↓
ChatService / ChatStreamService
    ↓ ensure_conversation + append messages (background)
    ↓ build_thread_context (multi-turn)
Router v2 (rules → LLM → GERAL)
    ↓
Engineering Orchestrator (domínio → agente → knowledge type)
    ↓
RAG agent-aware enrich (use_rag=true)
    ↓
Project RAG augment (se project_id) — FAISS do empreendimento
    ↓
Dispatcher → BaseAgentIntelligent
    ↓                    ↓
RAG v2 (FAISS global)  Ollama LLM
    ↓
PostgreSQL (conversations, conversation_messages, agent_runs)
    ↓
Resposta JSON/SSE → Frontend
```

## Fluxo Copilot v1

```txt
Frontend / API client
    ↓ POST /copilot
CopilotEngine
    ↓ intent_analyzer (structural | hydraulic | … | multi_discipline)
    ↓ task_planner (etapas + dependências)
    ↓ execution_graph → dispatch (N agentes) + ContextGraph
    ↓ response_synthesizer (relatório por disciplina)
    ↓ quality_evaluator (score 0–1)
    ↓ evaluation_v2 (intent/plan/exec/response → PostgreSQL background)
Resposta JSON → Frontend
```

## Fluxo AED v1

```txt
Frontend / API client
    ↓ POST /aed { text, use_rag?, persist? }
AedService → run_aed()
    ↓ understand_project (Copilot intent/planner, read-only)
    ↓ generate_designs (≥2 opções por disciplina)
    ↓ select_structural_system (sistema + normas + simulation_module)
    ↓ simulate_designs (RAG v2 build_context + heurísticas + histórico PG)
    ↓ compare_solutions → select_best_solution → generate_report
    ↓ save_aed_run (opcional, persist=true)
Resposta JSON (understanding, designs, simulations, comparison, selection, report)
```

## Fluxo multi-domain (orchestrate)

```txt
Frontend
    ↓ POST /orchestrate
Orchestrator v1 (`core/orchestrator/`)
    ↓ decompose_problem (keywords + LLM + filtro domínio)
    ↓ prepare_agent_execution (NBR ≠ SINAPI por disciplina)
    ↓ execute_agents (N × dispatch + ContextGraph.add_result)
    ↓ build_global_context → synthesize_results(context=...)
PostgreSQL (orchestrator_logs + agent_runs + agent_feedback)
    ↓
Resposta JSON → Frontend
```

## Mapa de diretórios (ownership)

```txt
ia-server-santos/
├── backend/                # Python / FastAPI
│   ├── app/                # API REST (routes, services, schemas)
│   ├── agents/             # Agentes legados (BaseAgent simulado)
│   ├── core/
│   │   ├── agents/         # Agentes inteligentes + factories
│   │   ├── database/       # PostgreSQL ORM + service
│   │   ├── learning/       # Learning Loop v1 (feedback_service)
│   │   ├── learning_v2/    # Learning Loop v2 (auto-tuning prompts)
│   │   ├── evolution/      # Evolution Loop v1 (auto-otimização contínua)
│   │   ├── agent_generation/  # Agent Generation Loop v1 (controlled)
│   │   ├── models/         # Model Router + Evaluation Loop
│   │   ├── copilot/        # Copilot v1 (plan + evaluate)
│   │   ├── evaluation_v2/  # Evaluation Loop v2 (autoavaliação Copilot)
│   │   ├── self_improving/ # Self-Improving Loop v1 (patches propostos)
│   │   ├── aed/            # AED v1 (design autônomo)
│   │   ├── structural_selector/  # Classificação de sistema estrutural
│   │   ├── structural_intelligence/  # SIE v1 (ESTRUTURAL)
│   │   ├── orchestrator/       # multi_domain + engineering_orchestrator
│   │   │   ├── multi_domain.py
│   │   │   ├── domain_classifier.py
│   │   │   ├── engineering_orchestrator.py
│   │   │   └── knowledge_router.py
│   │   ├── knowledge/
│   │   │   ├── rag/              # agent_router, scopes, rerank, retriever
│   │   │   └── …                 # ingestion, indexer, resolver
│   │   ├── project_rag/          # FAISS por projeto + extractors multi-formato
│   │   ├── conversation_context.py  # Multi-turn chat
│   │   ├── intent_layer.py       # Intent + streaming SSE
│   │   ├── stream_events.py      # Chunks SSE + keepalive
│   │   ├── agent_registry.py
│   │   ├── router.py       # Router v2
│   │   ├── dispatcher.py   # Dispatch + persistência
│   │   └── context_graph.py
│   ├── knowledge/          # raw/documents/ + catalog.jsonl + cache/
│   ├── data/               # Estado runtime loops + data/projects/{id}/ (gitignored)
│   ├── memory/             # RAG v2 (FAISS, embeddings, chunker)
│   ├── models/             # Ollama client
│   ├── config/             # Settings centralizadas
│   ├── scripts/            # init_db, index_knowledge_bases, run_auto_tune
│   └── tests/              # Test suites
├── frontend/               # Next.js SaaS UI
├── infra/docker/           # PostgreSQL compose
├── docs/                   # Documentação (este arquivo)
├── Makefile                # atalhos (make api, make test, …)
└── pyproject.toml          # pytest → backend/
```

---

# ⚙️ 5. RUNBOOK — COMO SUBIR O SISTEMA

## Pré-requisitos

- Python 3.11+
- Node.js 18+
- Docker (PostgreSQL)
- Ollama com modelos instalados no WSL (mínimo: `qwen3:8b`, `qwen3:14b`, `qwen3-coder`, `nomic-embed-text`)

## Subir stack completa

```bash
# 1. PostgreSQL
cd infra/docker && docker compose up -d

# 2. Banco
cd backend && python scripts/init_db.py
# ou na raiz: make db-init

# 3. Ollama (se não estiver rodando)
ollama pull qwen3:8b
ollama pull qwen3:14b
ollama pull qwen3-coder
ollama pull nomic-embed-text
# opcionais já usados pelo Model Router:
# ollama pull gemma4:latest deepseek-r1:14b gemma3:12b mistral:7b phi3:mini qwen2.5-coder deepseek-coder

# 4. Indexar bases técnicas (recomendado)
# Colocar PDFs em backend/knowledge/ e executar:
cd backend && python scripts/index_knowledge_bases.py
# ou só NBR: python scripts/index_knowledge_bases.py --base nbr

# 5. Backend
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# ou na raiz: make api

# 6. Frontend
cd frontend && npm run dev
```

## Acesso em rede — LAN (escritório) e externo (internet)

> **Painel de configuração:** `/settings/access` (admin) · persistência em `backend/data/system/network_access.json`  
> **Validação LAN:** `make validate-lan` ou `./scripts/validate_lan_access.sh [ip_windows]`

### Visão geral dos modos

| Modo | Quem acessa | URL típica | API no browser | Quando usar |
|------|-------------|------------|----------------|-------------|
| **Localhost** | Dev no próprio WSL/PC | `http://localhost:3000` | `http://localhost:8000` | Desenvolvimento diário |
| **LAN SEMINF** | Colegas na rede corporativa | `http://172.22.3.234:3000` | Proxy same-origin `/api-backend` | Equipe no escritório |
| **Quick Tunnel** | Qualquer internet (temporário) | `https://*.trycloudflare.com` | Proxy `/api-backend` no mesmo host | Demo sem domínio |
| **Cloudflare permanente** | Internet com domínio próprio | `https://ia.suaempresa.com` | Hostname público da API ou proxy | Produção externa |

**Regra importante (LAN + Quick Tunnel):** o frontend resolve a API via **proxy same-origin** (`frontend/lib/api-base.ts` + rewrite em `frontend/next.config.mjs`). O navegador chama `https://<host>:3000/api-backend/...` ou `http://<ip>:3000/api-backend/...`; o Next.js encaminha para `127.0.0.1:8000` no servidor. **A equipe não precisa abrir a porta 8000 no firewall do cliente** — só `:3000` (e portproxy no Windows→WSL).

### Topologia WSL2 + Windows (SEMINF)

```
Colega (LAN) ──► Windows 172.22.3.234:3000 ──portproxy──► WSL :3000 (Next.js)
                                                      └──► /api-backend ──► WSL :8000 (FastAPI)
```

| Endereço | Uso |
|----------|-----|
| `172.22.3.234` | IP Windows na **Ethernet 2** (rede SEMINF) — **usar na LAN** |
| `192.168.143.111` | IP Windows no **Wi-Fi** alternativo |
| `172.30.x.x` | IP interno do **WSL** — **não** compartilhar com colegas |

O IP do WSL muda após reboot; o script Windows reconfigura o portproxy automaticamente.

### 1) Rede local (LAN) — passo a passo

#### No servidor (WSL) — uma vez por sessão de trabalho

```bash
# Terminal 1 — API (escuta em todas as interfaces)
make api

# Terminal 2 — Frontend (0.0.0.0:3000)
cd frontend && npm run dev
```

#### No Windows — após cada boot (PowerShell **como Administrador**)

```powershell
# Na raiz do repo (ou via scripts\setup_wsl_lan_access.bat)
.\scripts\setup_wsl_lan_access.ps1
```

O script configura:
- **Portproxy** `0.0.0.0:3000` e `:8000` → IP atual do WSL
- **Firewall** inbound TCP 3000 e 8000

#### Frontend — `.env.local`

```bash
cp frontend/.env.lan.example frontend/.env.local
# Conteúdo recomendado:
# NEXT_PUBLIC_API_URL=http://localhost:8000
```

Na LAN, esse valor **só afeta** quem abre `localhost:3000` no próprio servidor. Colegas em `http://172.22.3.234:3000` usam automaticamente `/api-backend`.

Reinicie o frontend após alterar `.env.local` ou `next.config.mjs`.

#### Colega na rede — como conectar

1. Abrir no navegador: **http://172.22.3.234:3000/login** (ou Wi-Fi: `http://192.168.143.111:3000`)
2. Login (usuários seed — trocar senha em produção):

| Usuário | Senha padrão | Papel |
|---------|--------------|-------|
| `admin` | `Admin@2026!` | Administrador |
| `dev_user1` | `Dev@2026!` | Desenvolvedor |
| `dev_user2` | `Dev@2026!` | Desenvolvedor |

3. Após login → `/chat` (sem erro de rede no upload/importação)

#### Validar LAN (no WSL ou outro PC da rede)

```bash
make validate-lan
# ou IP customizado:
./scripts/validate_lan_access.sh 172.22.3.234
```

Checks: `GET :8000/health` · `GET :3000/api-backend/health` · `GET :3000/login` · `GET :8000/auth/status`

#### Painel **Configurações → Acesso e rede**

- Seção **Rede interna:** IP host, portas, CIDRs, URLs sugeridas
- **Modo efetivo** ex.: `internal` ou `quick-tunnel+internal`
- Campo **API em uso** na LAN deve mostrar `http://172.22.3.234:3000/api-backend` (não `:8000`)

### 2) Acesso externo — Quick Tunnel (temporário, sem domínio)

Ideal para demonstração rápida. URLs `*.trycloudflare.com` **mudam** a cada reinício do túnel.

#### Pré-requisitos

- `make api` e `npm run dev` rodando no WSL
- `cloudflared` instalado no WSL (`/usr/local/bin/cloudflared`)

#### Opção A — Painel (recomendado)

1. Login como **admin** → **Configurações → Acesso e rede**
2. Seção **Acesso temporário — Quick Tunnel** → **Iniciar túnel temporário** (~30 s)
3. Copiar **URL do frontend** e compartilhar com a equipe
4. Reiniciar `npm run dev` se o painel pedir (proxy/CORS)
5. **Parar túnel** quando não precisar mais

Com o proxy `/api-backend`, **não é necessário** configurar `NEXT_PUBLIC_API_URL` com a URL trycloudflare da API — basta a URL do frontend.

#### Opção B — CLI

```bash
make cloudflare-quick
# ou painel: POST /system/network-access/quick-tunnel/start (admin)
```

Logs: `backend/data/system/cloudflared-*.log` · estado: `quick_tunnel_state.json`

#### API (admin)

| Método | Rota |
|--------|------|
| `GET` | `/system/network-access/quick-tunnel` |
| `POST` | `/system/network-access/quick-tunnel/start` |
| `POST` | `/system/network-access/quick-tunnel/stop` |

### 3) Acesso externo — Cloudflare Tunnel permanente

Para domínio próprio (`ia.suaempresa.com`) com token de túnel e (opcional) Cloudflare Access.

#### Configuração

1. Criar túnel no [Cloudflare Zero Trust](https://one.dash.cloudflare.com/)
2. **Configurações → Acesso e rede** → colar **token**, tunnel ID, hostnames públicos
3. Public Hostnames no Cloudflare: frontend → `:3000`, API → `:8000` (se não usar só proxy)
4. CLI auxiliar:

```bash
make cloudflare-setup   # configura token/ingress
make cloudflare-run     # executa túnel nomeado
make cloudflare-service # systemd user (opcional)
```

#### Frontend com API em hostname separado (HTTPS)

```bash
cp frontend/.env.cloudflare.example frontend/.env.local
# NEXT_PUBLIC_API_URL=https://api-ia.SEU-DOMINIO.gov.br
npm run dev
```

Se o frontend público usar o **mesmo host** com proxy `/api-backend`, mantenha `NEXT_PUBLIC_API_URL=http://localhost:8000` como na LAN.

### Proxy técnico (`/api-backend`)

| Arquivo | Função |
|---------|--------|
| `frontend/lib/api-base.ts` | `getApiBaseUrl()` → `/api-backend` fora de localhost |
| `frontend/next.config.mjs` | Rewrite → `http://127.0.0.1:8000` · `allowedDevOrigins` para LAN e `*.trycloudflare.com` |
| `frontend/package.json` | `next dev -H 0.0.0.0 -p 3000` |

Variável opcional: `API_BACKEND_ORIGIN` (default `http://127.0.0.1:8000`) se a API não estiver no loopback padrão.

### Troubleshooting — conexão

| Sintoma | Causa provável | Ação |
|---------|----------------|------|
| Erro de rede apontando `:8000` na LAN | Portproxy/firewall ou `.env` antigo | Rodar `setup_wsl_lan_access.ps1` · reiniciar `npm run dev` · acessar só `:3000` |
| `api-backend/health` falha | API parada | `make api` |
| Login OK, upload falha | Bug backend (corrigido) | Atualizar código · `workspace_service.py` sem import local de `Path` |
| Quick Tunnel: auth trava | Frontend sem reinício pós-túnel | `npm run dev` · usar URL frontend trycloudflare |
| WSL reboot | IP WSL mudou | Reexecutar `setup_wsl_lan_access.ps1` no Windows |
| CORS após novo domínio | Origem não listada | Salvar em `/settings/access` · reiniciar API |

`AUTH_ENABLED=false` no `.env` do backend desliga JWT (apenas dev isolado).

## Variáveis de ambiente relevantes

| Variável | Default | Efeito |
|----------|---------|--------|
| `USE_INTELLIGENT_AGENTS` | `true` | `true` = RAG+LLM; `false` = agentes simulados |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Endpoint Ollama |
| `OLLAMA_KEEP_ALIVE` | `15m` | Mantém modelos na VRAM entre requisições |
| `OLLAMA_NUM_CTX` | `8192` | Tamanho de contexto LLM (menor = mais rápido) |
| `OLLAMA_WARMUP_ON_STARTUP` | `false` | Pré-carrega chat+eng no startup da API |
| `OLLAMA_LLM_MODEL` | `qwen3:14b` | Modelo primário |
| `OLLAMA_CHAT_MODEL` | `qwen3:8b` | LLM leve para chat conversacional |
| `USE_INTENT_LAYER` | `true` | Intent Layer v2 no chat (`false` = router legado) |
| `USE_MODEL_ROUTER` | `false` | Roteamento centralizado de modelos LLM por task_type |
| `USE_MODEL_EVALUATION` | `false` | Comparação primary vs fallback + perfis PostgreSQL |
| `USE_EVOLUTION_LOOP` | `false` | Evolution Loop v1 — auto-otimização contínua |
| `USE_SAFE_ROLLOUT` | `true` | Shadow test antes de aplicar mutações do Evolution Loop |
| `USE_AGENT_GENERATION` | `false` | Agent Generation Loop v1 — proposta controlada de agentes |
| `USE_KNOWLEDGE_ROUTER` | `false` | Multi-index FAISS explícito |
| `USE_AGENT_SCOPED_RAG` | `true` | RAG isolado por agente |
| `USE_ENGINEERING_ORCHESTRATOR` | `true` | Separação NBR / SINAPI |
| `USE_RAG_SEMANTIC_CACHE` | `true` | Cache semântico de queries |
| `CHAT_USE_LLM` | `true` | `false` = só templates (testes/offline) |
| `AUTH_ENABLED` | `true` | `false` desliga JWT globalmente |
| `AUTH_SEED_ADMIN_PASSWORD` | `Admin@2026!` | Senha seed do usuário `admin` |
| `AUTH_SEED_DEV_PASSWORD` | `Dev@2026!` | Senha seed `dev_user1` / `dev_user2` |
| `CORS_ALLOWED_ORIGINS` | localhost 3000/3001 | Origens extras + painel `/settings/access` |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Só localhost; LAN/trycloudflare usam `/api-backend` |
| `API_BACKEND_ORIGIN` | `http://127.0.0.1:8000` | Destino do proxy Next.js (opcional) |

**Streaming:** `POST /chat/stream` (SSE) — evento `connected` imediato; fases `rag` → `rag_done` → `llm_start`; tokens em tempo real (~60fps no UI).

Settings completas: `backend/config/settings.py`

---

# ⚠️ 6. RISCOS E ISSUES CONHECIDOS

| ID | Severidade | Descrição | Mitigação |
|----|------------|-----------|-----------|
| R-01 | Alta | SINAPI/TCPO legado em `cost_index` (RAG) vazio — orçamento usa `price_bank` + `composition_index` | `make index-price-bases` · sync em `/settings/price-bases` |
| R-02 | Alta | LLM pode alucinar tabelas/nomenclaturas normativas | RAG + validação pós-resposta; prompts com restrições |
| R-03 | Média | Latência 2–5 min por request (CPU local) | GPU; modelo menor; streaming ✅ no chat |
| R-09 | Média | DWG indexa só strings ASCII (extração parcial) | Exportar para PDF/DXF antes do upload |
| R-10 | Baixa | Project RAG não validado com arquivos reais de obra | `make test-project-rag` (pytest mock embed) · `make validate-project-rag` (API+Ollama) · checklist §2 |
| R-11 | Média | Agente cronograma com LLM pequeno pode gerar ações inválidas | Modelos maiores (`qwen3:14b`); enriquecimento heurístico + resolução código/nome |
| R-04 | Média | Orchestrator v1 executa agentes com contexto limitado | Orchestrator v2: Execution Planner + dependências |
| R-07 | Média | AED simula via heurísticas — simuladores dedicados ainda não existem | Implementar `*_simulator` por sistema estrutural |
| R-08 | Baixa | ~~Frontend sem `/aed` e `/copilot`~~ | ✅ Páginas implementadas (M3) |
| R-05 | Baixa | CORS amplo em dev | Origens via `/settings/access` + `CORS_ALLOWED_ORIGINS`; restringir em produção |
| R-06 | Baixa | Senhas seed em dev | Trocar `AUTH_SEED_*` antes de expor na internet |
| R-13 | Média | ~230 PDFs normativos sem texto (scan/OCR) + 367 chunks metadata≠FAISS | Pipeline OCR futuro; rebuild FAISS se delta crescer |
| R-14 | Média | Zero testes frontend | Smoke E2E mínimo; Playwright ou script curl+auth |
| R-15 | Média | God files (`pricing.py`, `api.ts`) | Sub-routers + módulos API por domínio |
| R-16 | Média | `make test-backend` pode segfault (FAISS/extensões nativas) | Subset de testes estável para CI; investigar ordem/isolamento |
| R-17 | Baixa | ~~Sem CI/CD visível~~ — **Mitigado (M8/B14)** | GitHub Actions em push/PR `main` |
| R-18 | Alta | Multi-tenant ausente — todos os projetos visíveis | `user_id` em projetos + filtros antes de expor fora da LAN |
| R-19 | Alta | Testes pytest sem `monkeypatch` em `PRICE_BANK_ROOT` corromperam `knowledge/price_bank/` (index SEMINF/SICRO + `compositions_closed` AM) | Isolar testes (`test_sicro_parser`, `test_seminf_refresh_prices_fixture`); `reconcile_with_disk` cobre `BR-SICRO-*`/`BR-DP-SEMINF-*`; `prune_orphan_references()` para órfãos |
| R-20 | ~~Alta~~ Mitigado | Orçamentos isolados por `user_id` quando auth ativo (B1) |
| R-21 | ~~Alta~~ Mitigado | Lock otimista com `version` + `expected_version` (B2) |
| R-22 | ~~Média~~ Mitigado | BDI edital (B3) · auditoria completa (B7+B16) · compliance-pack (B22) |
| R-23 | ~~Média~~ Mitigado | Sessão orçamento — B11 auto-save + B18 snapshot PostgreSQL + restore em `get()` |
| R-24 | ~~Baixa~~ Mitigado | TCPO/ORSE na Busca CPU (B5) |
| R-25 | ~~Alta~~ Mitigado | Laudos — isolamento multi-usuário (L1) |
| R-26 | ~~Média~~ Mitigado | Laudos — correção sem SSE (L2) |
| R-27 | ~~Média~~ Mitigado | Laudos — tipologías outline idêntico (L3) |
| R-28 | ~~Baixa~~ Mitigado | Laudos — testes rasos (L5) |

---

# 📋 7. DECISION LOG

| Data | Decisão | Motivo |
|------|---------|--------|
| 2026-06-20 | **B12 — piloto orçamento** | Esqueleto `sk-b12-piloto-passarela` · `test_budget_pilot_flow.py` · `validate_budget_pilot.sh` |
| 2026-06-20 | **M6 — split pricing.py** | Pacote `app/routes/pricing/` (providers, sync, budget, tech_spec, export) — 99 rotas |
| 2026-06-20 | **Orçamento B11 — auto-save** | Heartbeat `restore` 60s · persist DB silencioso 3min · `sessionStorage` + indicador toolbar |
| 2026-06-27 | **Relatórios insumos/MO (PDF/Excel)** | `rel_insumos` e `rel_mao_obra` — agregação de CPUs por código/unidade; total por linha (sem BDI); rodapé TOTAL SEM BDI · VALOR BDI · TOTAL COM BDI; cenário ComD/SemD adotado; toolbar `/budget` |
| 2026-06-20 | **Orçamento B23–B26 — 100% gaps §8.1** | UI `.xlsm`/compliance · validador BDI · piloto 4.U5/4.U6 · Playwright API real |
| 2026-07-04 | **Export analítico — performance** | `PriceBankStore` cache em memória (open/closed/insumos) · export usa `resolve_composition_detail` sem variação de período · pré-carga paralela de CPUs antes de Excel/PDF analítico |
| 2026-07-04 | **Lançar Preços — polimento UX + matching** | Botão «Abrir módulo de orçamento» no histórico (`/budget?open=`) · scroll nas abas PPD/analítico/curvas · `description_match_score` semântico (tokens + unidade + senioridade) |
| 2026-07-04 | **Lançar Preços — fix loading infinito ao abrir histórico** | `GET …/session?sync_prices=false` por default (evita re-sync de 244 linhas + lookup banco) · abertura em 2 fases: `getJob` imediato + sessão em background · `_unit_costs` usa `valor_unitario_base` da linha antes de varrer price_bank |
| 2026-07-04 | **Lançar Preços — fix abrir do histórico** | Carregamento centralizado no workspace (`getSession` + `getJob` em paralelo) · sync explícito ao painel via `panelSyncToken` · backend re-fetch job com `rows` após persistir bases |
| 2026-07-03 | **Orçamento — bases dinâmicas + auto-add na Busca CPU** | `BudgetPriceBasesPanel` lista fontes do `price_bank` (ORSE, TCPO, etc.) · `upsertPriceBaseSelection` ao lançar CPU |
| 2026-07-04 | **Lançar Preços — cobertura + precisão matching** | Dois níveis: auto ≥80% · sugestão ≥52% com preço (review) · `is_hard_mismatch` bloqueia pares errados · sinônimos (perfuração/furo/espera/epoxi) · busca dupla com/sem filtro de unidade |
| 2026-07-03 | **ORSE — conector portal CEHOP** | `OrsePortalScraper` · `portal_sync` no sync ORSE · botão UI “Importar via portal CEHOP” · ~2k composições + CPUs + insumos sem ORSE 2 |
| 2026-07-03 | **ORSE — fix detecção/validação import** | Rejeita planilhas SEMINF/SINAPI/PPD por engano · exige Composições+Insumos+Analítico · `ORSE_EXPORT_DIR` só lê subpasta `BR-ORSE-YYYY-MM` |
| 2026-07-24 | **Módulo Laudos de Vistoria** | `/inspection-reports` · Gemini 3.6 Flash multimodal · templates por tipología · anexos PDF/fotos · RAG opcional · correção profissional · DOCX/PDF (logo, rodapé redes, 1 foto/página, recuo 1,5 cm) · `GEMINI_API_KEY` · módulo `inspection_reports` em permissões · testes `test_inspection_reports.py` |
| 2026-07-24 | **Laudos — progresso SSE** | `POST /inspection-reports/{id}/generate/stream` · etapas prepare→attachments→knowledge→gemini→structure→persist · UI modal com % e checklist · JSON Gemini hardened (`_repair_truncated_json`, max_output_tokens 16384) |
| 2026-07-24 | **Laudos — template Bariri** | Adotado layout do `LAUDO TECNICO N05 - PONTE DO BARIRI`: cabeçalho logo/brasão + linha institucional · rodapé endereço + Página X de Y · capítulos 1–16 SEMINF · Gemini 2 passagens (amostra + legendas detalhadas por lote) · campos legend/score/indicators |
| 2026-07-24 | **Laudos — formatação Word/PDF** | Cabeçalho: logo esq. + empresa · dados/data-hora dir. · 2 linhas azul/cinza · rodapé com 2 linhas · brasão na capa · texto justificado · capítulos numerados · tabelas com wrap · indicadores legíveis (sem dict Python) · PDF≡DOCX |
| 2026-07-24 | **Laudos — watermark + analytics** | Cabeçalho compacto · brasão marca d'água central (Word/PDF) · fotos com fit anti-página-em-branco · cards + tabelas ranking + gráficos barra/pizza de patologias |
| 2026-07-24 | **Laudos — RT / imagens / brasão corpo** | UI lista+popup (incluir/alterar/excluir c/ confirmação) p/ `responsaveis_tecnicos` e `responsaveis_imagens` · PATCH persiste no `content` e sobrevive à regeneração Gemini · assinaturas RT antes do fotográfico · apresentação do laudo sob o título fotográfico (sem linha Fonte/imagem anexo) · brasão marca d'água na largura útil 16,5 cm (DOCX/PDF) |
| 2026-07-24 | **Laudos — ART + capa + fonte foto** | Campo ART no RT · capa com RT (CREA/ART) e responsável pelas fotos abaixo da data · assinaturas 100% centralizadas · títulos das fotos centralizados · Fonte: autor + mês/ano |
| 2026-07-24 | **Laudos — solicitante + georref** | Campos solicitante (empresa/CNPJ/endereço/contato) na capa e seção própria · upload `georef` com EXIF GPS · coordenadas na ficha técnica · imagem abaixo da tabela de dados do objeto (Word/PDF) |
| 2026-07-24 | **Laudos — preview georref + export UX** | `GET …/assets/{id}/file` com auth · preview blob na UI · modal círculo % ao exportar Word/PDF (`downloadApiFile`) |
| 2026-07-24 | **Análise enterprise · Laudos (§8.2)** | Revisão código: fortes (2 passagens, metadados sobrevivem Gemini, export institucional) · fracos (R-25/26/27/28) · backlog L1–L3 · passagem 1 usa `max_output_tokens=24576` (doc SSE antigo citava 16384) |
| 2026-07-24 | **Fix preview logo/brasão Empresa** | `<img src={API}>` sem JWT → 401 · preview via `systemFetchCompanyLogo/Brasao` + blob URL + auth (`ExportBrandingSettingsPanel`) |
| 2026-07-24 | **Fix redes sociais Empresa** | `CompanyProfileUpdateRequest` omitia `social_*` — Pydantic descartava no PATCH · campos agora no schema + teste de persistência |
| 2026-07-26 | **Laudos L15 RAG normativo** | `normative_rag.py` · queries por tipología · `retrieve_for_agent` · `normative_citations` + tabela Referências · prompt L15 · testes |
| 2026-07-27 | **Laudos L16 ensaios medidos** | `assay_results.py` · `instrumented_test_results` · API GET/PUT · UI cadastro · tabela export · metrologia vinculada |
| 2026-07-27 | **Laudos L17–L19 MVP** | croqui `visual_memory` · ART `kind=art` · firma `kind=signature` + SHA-256 PDF · UI canvas/parties · testes |
| 2026-07-27 | **Fix PDF laudos + flood benchmark** | fotos export 1400px JPEG · croqui sem PNG full-res · `export/pdf` try/except · hash não derruba download · `/system/benchmark` público · backoff UI |
| 2026-07-27 | **L17 croqui — estilo avançado** | cor/espessura/fonte/`filled` · ferramenta círculo · painel caneta + editar selecionado · duplicar · export Pillow respeita estilo |
| 2026-07-27 | **Laudos follow-up órfãos · ART live · PAdES** | ACL órfãos admin-only · claim/assign/backfill · `art_lookup` CREA+SICAR · pyhanko + `LAUDO_PADES_*` no export PDF |
| 2026-07-26 | **Laudos — EXIF Orientation no export** | `open_image_upright` / `image_bytes_for_export` · Word/PDF/georref/`_image_meta` respeitam retrato vs paisagem |
| 2026-07-25 | **Laudos — mapa satélite de localização** | `location_map.py` (Esri/Google/fallback) · marcador no GPS da georref · Word/PDF abaixo da capa · cache por laudo · env `GOOGLE_MAPS_STATIC_API_KEY` opcional |
| 2026-07-25 | **Laudos L14 cobertura fotográfica** | `photo_coverage.py` amostra estratificada (soft 24) + ondas de cobertura · merge pathologies_delta · tie-break governante estrutural · índice foto só P0N · stats `photo_coverage` |
| 2026-07-25 | **Laudos protocolo CREA/perícia** | TOC único · ordem L10–L13 · governing coerente · metrologia honesta · ensaios top-8 · L13 interdição · índice fotográfico · ART capa · georref só c/ GPS · watermark 6% |
| 2026-07-25 | **Laudos L10–L12** | Motor DNIT (`classification.py`) · inventário por tipología (`elements.py`) · metrologia tipada (`metrology.py`) · `engineering_enrichment` no generate/export · card UI · testes |
| 2026-07-25 | **Laudos — export só Word/PDF** | UI reduzida a 2 botões (Word/PDF); checklist informativo sem botões “oficial” |
| 2026-07-24 | **Laudos L1–L9 backlog §8.2** | Isolamento user_id · SSE correção · tipologías · georref Gemini · limites/cancel · edição humana · project_id+activity · checklist CNPJ/CREA/ART · 13 testes verdes |
| 2026-07-24 | **Laudos — sumário no export** | Sumário era pulado em `build_body_sections` · agora `build_sumario_entries` + página Sumário em Word/PDF · `ensure_sumario_chapter` na geração |
| 2026-07-24 | **Laudos — capa 1ª folha** | Capa deixou de ser lista centralizada · `build_cover_layout` + tabelas rótulo|valor (negrito + fundo azul claro) em Word/PDF · blocos Identificação / Solicitante / Responsabilidade técnica / Conformidade |
| 2026-07-24 | **Laudos — ensaios instrumentados** | Checkbox ao lado de RAG · flag `suggest_instrumented_tests` · catálogo por tipología (pontes/viadutos/erosão/…) e gravidade · Gemini + pós-processamento · capítulo `ensaios_instrumentados` |
| 2026-07-19 | **P0 sticky discipline + NBR 8160** | Follow-ups curtos (“itens do projeto/desenho”) herdam disciplina do histórico (`infer_sticky_discipline`) — não caem mais no ChatAgent · NBR 8160 corrigida (esgoto, não água quente) + NBR 7198 · prompt hidrossanitário anti-confusão 5626/8160/7198 · keywords barrilete/caixa inspeção · `tests/test_sticky_discipline.py` |
| 2026-07-19 | **Fix multi-turn — contexto compacto p/ LLM** | Histórico prioriza **dados do usuário** (dims/cargas) e corta respostas longas do assistente (~500 chars) — evita estouro de context window que fazia o modelo “esquecer” o 1º prompt · instrução explícita “não peça de novo” · RAG usa só a mensagem atual · `list_thread_turns` |
| 2026-07-19 | **Fix multi-turn chat — histórico no prompt** | `build_thread_context` materializa msgs **dentro** da sessão (antes: `DetachedInstanceError` → histórico vazio silencioso) · `list_messages` pega as **últimas** N · plano mixed reanexa prefixo · ChatAgent não usa template quando há thread · `tests/test_thread_context.py` |
| 2026-07-19 | **Chat SSE mobile — keepalive + recover** | Heartbeat SSE a cada 12s durante espera LLM · `conversation_id` cedo no status · persistência em thread mesmo se o cliente cair · UI faz poll da conversa se o stream terminar sem `done` (Cloudflare/mobile cortavam idle ~100s) |
| 2026-07-05 | **Orçamento B32 — cache global CPUs** | `composition_open_cache` deduplicado `(code, reference, uf)` · migração do legado B31 · batch analítico lê cache global · save sem sync eager · benchmark 194 CPUs: cold ~299s vs warm ~60ms |
| 2026-07-02 | **ORSE — sync UI + price_bank** | `/settings/price-bases` · download CEHOP `.ORSE` · import pasta Excel (composições+insumos+analítico) · `POST /sync/orse/upload/bundle/stream` · parser `orse_export_parser` · ref `BR-ORSE-YYYY-MM` |
| 2026-07-02 | **Orçamento B27–B28 — tenant + lock sessão** | `empresa_id` + `X-Tenant-Id` + `BudgetTenantSelector` · `BudgetSessionLock` TTL + guard PATCH · `BudgetPilotChecklist` §4.U · pytest tenant/lock/pilot **11 passed** · fix middleware `SessionLocal` lazy + export filename ASCII |
| 2026-07-02 | **Template `ppd_seminf_abril_2026.xlsm`** | Gerado de `00_MOD_MC_OR…v8.1.xlsm` via `make build-ppd-seminf-2026` — abas MCQ + ORC_SINTETICO + ORC_ANALITICO + CRONOGRAMA + ESP_TECNICA + Base Abril/2026; `make validate-budget-pilot` **23 OK** (4.U5 xlsm incluído) |
| 2026-06-29 | **Orçamento B16–B22 — fechamento gaps técnicos** | Auditoria completa · snapshot PostgreSQL · export `.xlsm` · CPQ margem · compliance-pack · CI ampliado (~88 pytest) |
| 2026-06-20 | **§8.1 sync pós B1–B15** | Revisão orçamentista sênior: 6/14 gaps resolvidos · 5/14 mitigados · 3/14 abertos; matriz prontidão atualizada; B7 parcial; roadmap B16+ |
| 2026-06-27 | **Análise enterprise módulo Orçamento** | Revisão inicial §8.1 (pré-B15); substituída pela revisão 2026-06-20 acima |
| 2026-06-20 | **R10 Project RAG — testes E2E automatizados** | `test_project_rag_e2e.py` (upload→FAISS→chat com mock embed) · `scripts/validate_project_rag.sh` · `make test-project-rag` / `validate-project-rag` |
| 2026-06-20 | **Fix testes price_bank + recuperação SEMINF/SICRO** | `test_list_imported_sicro_ufs_filters_period` escrevia no disco real (`index.json` truncado, AM `closed=[]`); isolamento com `tmp_path`; `reconcile_with_disk` indexa `BR-*` com manifest e atualiza contagens; `BR-SICRO-AM-2026-01` restaurado da amostra `am-01-2026` |
| 2026-06-20 | **ChatAgent platform_evaluation** | Meta-perguntas sobre arquitetura/fortes/fracos usam `project_state.md` + intent dedicada (não pitch genérico) |
| 2026-06-20 | **Fix ContextVar no SSE chat stream** | `llm_model_scope` quebrava no thread pool Starlette (`ValueError: Token was created in a different Context`); modelo passado explicitamente em `/chat/stream` |
| 2026-06-20 | **Fix stream chat com gemma4/deepseek-r1** | Timeout 300s + fallback chain + não força CPU (`num_gpu:0`) quando usuário escolhe modelo pesado; SSE encerra com evento `done` em erro |
| 2026-06-20 | **Orçamento B6 — aditivos** | Baseline congelada · revisões N · compare vs baseline · UI `BudgetRevisionPanel` |
| 2026-06-20 | **Orçamento B4 — pipeline LLM na UI** | Aba Histórico · prompt + `BudgetPipelinePanel` · SSE `budgetGenerateStream` |
| 2026-06-20 | **Orçamento B1/B2 — ownership + versionamento** | `user_id` + filtro por usuário em `budget_documents` · lock otimista (`version`, `expected_version`, 409) · migração `migrate_budget_ownership` |
| 2026-06-20 | **Orçamento B4 — import PPD na UI** | Modal Novo orçamento · upload `.xlsm/.xlsx` via `pricingImportPpd` |
| 2026-06-20 | **Orçamento B8 — Curva S cenário adotado** | UI + export PDF/Excel documentam ComD/SemD adotado |
| 2026-06-20 | **Histograma MO — filtro MO direta** | Exclui EPI, ferramentas, seguro, transporte, locação e encargos coletados Caixa; mantém profissionais · `is_histogram_direct_labor` |
| 2026-06-24 | **Fix qwen3.6 sem resposta no chat** | VRAM fit (23GB→gemma4 em GPU 8GB); stream vazio aciona fallback; recovery generate no agente estrutural |
| 2026-06-20 | **Model Router — qwen3.6 primário** | `engineering_primary` e `aed_simulation` usam `qwen3.6:latest`; `gemma4` como secundário; rótulo WSL ordena qwen3.6 primeiro |
| 2026-06-20 | **Integrar gemma4 + deepseek-r1 no Model Router** | `gemma4:latest` engenharia secundária/visão; `deepseek-r1:14b` raciocínio (MEDIUM); cadeia gemma4 → qwen2.5-coder |
| 2026-06-20 | **Parser CPU SICRO completo** | Seções D/E/F (atividades auxiliares, tempo fixo, transporte, FIC) — códigos 7 dígitos não abrem composição nova · total `custo unitário direto total` |
| 2026-06-20 | **SICRO sync incremental** | `skip_existing_ufs` no lote — pula `BR-SICRO-{UF}-YYYY-MM` já no banco · UI **Sincronizar UFs faltantes (N)** + **Reimportar todas** · CLI `--skip-existing` |
| 2026-06-20 | **Download SICRO resiliente** | `download_archive`: streaming 256KB, timeout leitura 600s, 5 retries com backoff, verificação Content-Length · sync lote continua após falha por UF (`synced_ufs` / `failed_ufs`) |
| 2026-06-20 | **UI SICRO** | `/settings/price-bases`: filtro região/UF, meses trimestrais, botão sync todas UFs · `BudgetPriceBasesPanel`: região + versão por UF · `frontend/lib/sicro-links.ts` |
| 2026-06-20 | **Auth — editar/excluir usuários** | `/settings/users`: modal de edição (e-mail, nome, senha, tipo, módulos) + confirmação de exclusão (desativa via `DELETE /auth/users/{id}`) |
| 2026-06-20 | **Auth — tipos de usuário e módulos** | `/settings/users`: select com **Cadastrar novo…**, tabela de módulos (Oculto / Bloqueado); API `GET/POST /auth/roles`, `GET /auth/modules`; sidebar respeita permissões |
| 2026-06-20 | **Fix histograma vazio na UI** | Frontend usava `item_type` bruto para classificar insumo/MO/equip.; alinhado com `resolve_resource_category` (SINAPI `classificacao`, unidade MES/H, mensalista). Cache do modelo só persiste quando há totais > 0 e chave inclui estado de carregamento das CPUs |
| 2026-06-20 | **Otimização desempenho Ollama/IA** | `keep_alive` 15m · cache list_models/ping · `num_ctx` 8192 · chat não força CPU só por VRAM alta · embed throttle · warmup opcional · defaults centralizados |
| 2026-06-20 | **Anexos no prompt — Orquestrador, Copilot, AED** | `POST /chat/attachments` reutilizado · `attachment_ids` em `/orchestrate`, `/copilot`, `/aed` · `resolve_prompt_with_attachments` no backend · `ChatBox` com anexos habilitados por padrão |
| 2026-06-20 | **Chat — anexos no prompt** | Botão 📎 no `/chat` · `POST /chat/attachments` · extração multi-formato + visão para imagens/PDF · modo Auto escolhe modelo (gemma3/qwen/coder) · contexto injetado no stream |
| 2026-06-20 | **Frontend mobile (telefone)** | Bottom nav (Chat, Orçamentos, CPU, Projetos, Config) · sidebar oculta `< lg` · workspace drawer · `/mobile/budget` (listar + PDF) · `/mobile/cpu` · `/mobile/projects` |
| 2026-06-20 | **Relatório PDF — CPU consultada** | `GET /pricing/sync/bank/composition/export/pdf?code=` · `cpu_pdf_export.py` · botão na aba Busca CPU e painel de consulta |
| 2026-06-20 | **Export PDF/Excel — alinhamento de colunas** | Item/Código/Un/Classe centralizados; Qtd e valores à direita em todos os relatórios; Curva ABC: linhas classe A (negrito) e TOTAL usam alinhamento correto (antes `cell_bold` forçava esquerda no PDF) |
| 2026-06-20 | **PDF analíticas — gráficos** | Curva ABC (Pareto top 20), Curva S (linhas físico/financeiro) e Histograma (barras empilhadas + ref. BDI) renderizados no PDF via `budget_pdf_charts.py` — cores e legenda espelhando o frontend |
| 2026-06-20 | **Orçamento — export analíticas PDF/Excel** | Curva ABC, Curva S e Histograma exportáveis via `/export/pdf|xlsx/{doc}` — layout paisagem institucional (logo, cabeçalho, meta obra); cálculo no backend espelhando UI |
| 2026-06-20 | **Orçamento — analíticas Curva S + Histograma** | Curva S: serviços sem tarefa no cronograma alocados no 1º mês (total financeiro = soma efetiva ABC). Histograma: linha ref. com BDI por serviço (`total_effective ÷ custo CPU`) sobre barras analíticas; painel conferência atualizado |
| 2026-06-20 | **Orçamento — Excel cabeçalho/rodapé mesclados** | Logo A1; linhas 1–4 mescladas A:H; meta obra/bases 2×2 (sintético: A:C \| D:última col.; analítico: A:D \| E:I); rodapé centralizado; Arial Narrow + `#,##0.00` |
| 2026-06-20 | **Orçamento — Excel sintético com fórmulas** | Serviço: `=Qtd×Unit`; etapas: `SUM` dos filhos; rodapé: TOTAL SEM BDI, BDI (%), TOTAL COM BDI; coluna H oculta com custo unitário para cálculo do direto |
| 2026-06-26 | **Orçamento — PDF analítico coluna Tipo + menor custo** | Coluna Tipo (Etapa/Serviço/Material…); exibe só colunas do cenário adotado (ComD ou SemD conforme menor total do orçamento), alinhado ao sintético |
| 2026-06-20 | **Orçamento — template PDF retrato `portrait_budget_v1`** | Módulo `budget_pdf_portrait_template.py` — A4 vertical, MCQ (cabeçalho/rodapé institucional, bloco obra/bases, tabela 5 colunas, larguras Item 7% / Código 18% / Descrição 54% / Un 7% / Qtd 14%) |
| 2026-06-26 | **Orçamento — template PDF paisagem `landscape_budget_v1`** | Módulo `budget_pdf_landscape_template.py` extraído do orç. sintético; aplicado a `orc_sintetico`, `orc_analitico` e `cronograma` (cabeçalho/rodapé, linhas separadoras, bloco obra/bases 2×2, tabela zebrada) |
| 2026-06-20 | **Orçamento — personalização global de exportação** | Cabeçalho/rodapé/logo/brasão em Configurações → Empresa; persistência `data/system/export_branding.json`; aplica a todos os orçamentos; brasão centralizado no corpo (marca d'água); APIs `GET/PATCH /system/export-branding` |
| 2026-06-20 | **Orçamento — exportação nativa (sem template SEMINF xlsm)** | Removido sync/LibreOffice com `ppd_seminf_abril_2026`; geração própria Excel (openpyxl, 5 abas) + PDF (ReportLab); APIs `/export`, `/export/pdf/{doc}` |
| 2026-06-20 | **Orçamento — migração automática v8.1 → ppd_seminf_abril_2026** | _(substituído pela exportação nativa acima)_ |
| 2026-06-25 | **Orçamento — template ppd_seminf_abril_2026 (5 abas)** | Template padrão com MCQ, ORC_SINTETICO, ORC_ANALITICO, CRONOGRAMA, ESP_TECNICA; sync multi-aba; PDF por aba; paisagem ORC_*; preservação logo (&G) via merge zip; Base injetada do v8.1 |
| 2026-06-25 | **Orçamento — PDF SEMINF fix (#NAME? + layout)** | PDF prep **mantém** abas `MCQ` + `Base_*` (ocultas) para VLOOKUP/OFFSET; não deleta dependências; print area H–L (MCQ) / H–R (PLANILHA); fitToWidth=1; última linha via sync (`last_mcq_row`) + ignora células só-fórmula; sync MCQ usa VLOOKUP em J/K para códigos numéricos SINAPI |
| 2026-06-20 | **Orçamento — PDF/ sync SEMINF fix** | PDF exporta só aba MCQ/PLANILHA (remove outras abas + trim print_area); sync MCQ só colunas G–M preservando cabeçalho/rodapé template; wrap+altura linha; recompute totais etapas antes sync/UI |
| 2026-06-20 | **Orçamento — bridge SEMINF workbook (MVP)** | Template `00_MOD_MC_OR…v8.1.xlsm` registrado; clone por orçamento em `budgets/{id}/workbook.xlsm` (MinIO/local); sync sessão→aba MCQ (`keep_vba`); APIs `workbook/init|sync|GET|pdf/planilha`; toolbar: Sincronizar · Baixar .xlsm · Gerar PDF Planilha; compose IA aceita `código qty unidade`; PDF via LibreOffice (503 se LO ausente) |
| 2026-06-20 | **Orçamento — Analítico totais BDI** | Rodapé com custo direto, BDI, total ComD/SemD e total adotado (menor valor) — mesmo cálculo do sintético |
| 2026-06-20 | **Orçamento — Busca CPU ao vivo** | Busca por descrição com debounce 280ms + `AbortSignal`; backend retorna resumo leve (sem expandir CPU por item); clique na linha abre prévia com alerta de variação |
| 2026-06-20 | **Orçamento — Busca CPU = prévia bases** | Painel igual Configurações → Bases de preços; `OpenCompositionPreview` com alerta de variação de preço; busca por descrição opcional |
| 2026-06-20 | **Orçamento — Analítico SEMINF** | CPUs `*.SEMINF` resolvem base DP/SEMINF via `price_bases` ou períodos importados + `base_preco` do PPD |
| 2026-06-20 | **Orçamento — Analítico por etapa/sub-etapa** | Hierarquia WBS (etapa → sub-etapa → serviço); card com itens da CPU aberta abaixo de cada composição; auto-load incremental |
| 2026-06-20 | **Orçamento — Orç. Analítico espelho sintético** | Aba lista só serviços lançados no orçamento (sem filtros período/base/UF); clique abre CPU aberta com bases do projeto; **Busca CPU** mantém catálogo paginado |
| 2026-06-20 | **Orçamento — Orç. Analítico + Busca CPU** | Aba tabela CPUs abertas (paginada) + busca por código/descrição com prévia ComD/SemD; API `GET /pricing/sync/bank/open-compositions`; PPD renomeado Orç. Sintético |
| 2026-06-20 | **Prévia CPU SEMINF — totais por período** | Cabeçalho ComD/SemD usa CPU analítica quando fork SINAPI diverge do sintético regional |
| 2026-06-20 | **DP/SEMINF — import parcial bloqueado** | `BR-DP-SEMINF-2026-04` ficava só fechadas (`import_mode: base_sheet_closed`) quando importava só Tabela_Preco; auto-detect ComD/SemD na pasta; bloqueio reimport destrutivo; teste isolado com `monkeypatch` no price_bank |
| 2026-06-20 | **Bases de preço — sem “ativo”** | Badge removido da UI; import/fork SEMINF não marca `active_reference`; orçamento escolhe período explicitamente (incl. bases antigas para aditivos); `BudgetPriceBasesPanel` inclui DP/SEMINF |
| 2026-06-23 | **CORS upload SEMINF** | `X-Tenant-Id` incluído em `allow_headers` — preflight do upload em lote falhava com erro CORS no browser |
| 2026-06-20 | **DP/SEMINF — coluna tp2 (AS)** | Importa `tp2` da aba Base da Tabela de Preço; propaga para itens das CPUs abertas (SINAPI + SEMINF); exibido na prévia CPU |
| 2026-06-23 | **DP/SEMINF — fork mês SINAPI** | **Gerar base atualizada** cria `BR-DP-SEMINF-YYYY-MM` do mês SINAPI selecionado (ex. 04→05 gera `…-2026-05`); fonte anterior preservada; SINAPI Caixa novo + fechadas/aux. SEMINF da base fonte |
| 2026-06-23 | **DP/SEMINF — detecção pasta + refresh CPUs** | Normaliza acentos (composição/preços); ignora outros arquivos na pasta |
| 2026-06-20 | **Import DP/SEMINF só `*.SEMINF`** | Pasta `DP-SEMINF` (3 arquivos auto-detectados) → `Tabela_Preco` + CPUs ComD/SemD; validação mês/ano; ~719 fechadas + ~725 abertas |
| 2026-06-20 | **Fix PDF especificação técnica — listas** | Marcadores fora da margem: substituído `ListFlowable` (bulletDedent auto) por parágrafos com `•` + recuo; export usa só corpo (`extract_body_html`); negrito preservado em `<strong>` |
| 2026-06-23 | **Retry automático especificação técnica** | Até 3 tentativas/serviço se resposta IA incompleta; modelo fallback na 3ª tentativa |
| 2026-06-23 | **Botão Limpar especificação técnica** | `DELETE /tech-spec` · limpa sessão e preview para regerar do zero |
| 2026-06-20 | **Especificação técnica v2 — serviço a serviço** | Refatoração completa: `tech_spec_generator.py` (IA só no conteúdo) + estrutura Markdown no código; 1 chamada/serviço; preview incremental; fallback por serviço (não documento inteiro) |
| 2026-06-20 | **Formatação via prompt na especificação técnica** | Mesmo prompt aceita diretrizes de layout (fonte, tamanho, entrelinha, margens, alinhamento, numeração esq./dir./centro) + conteúdo; parser `tech_spec_format_parser.py`; preview/export Word/PDF refletem formatação |
| 2026-06-20 | **Fix loop especificação técnica** | Geração **por etapa** (≥6 serviços) · `repeat_penalty` · detector de repetição · capa com dados da obra/bases · numeração inferior esquerda · texto justificado |
| 2026-06-20 | **Importação SICRO DNIT** | Parser `sicro_parser.py` (fechadas/sintéticas, analíticas CPU, insumos M/E/P com ComD/SemD) · portal resolver DNIT `.7z` por UF · `CicroConnector` manual (pasta/zip/7z) + sync automático (`download_all_regions`) |
| 2026-06-26 | **Fórmula Caixa 100% (Analítico com Custo)** | `sinapi_caixa_pricing.py`: insumo UF→regional_as→SP (ISD/ICD/ISE); composição PROCX sem fallback SP; `regional_as` persistido no import |
| 2026-06-26 | **Regra insumo zerado → preço SP (%AS 100%)** | _(detalhada na entrada acima — 3 níveis Caixa)_ |
| 2026-06-20 | **Fix avisos variação CPU (falso +100%)** | Comparação volta ao **mês anterior importado** (não “peak” histórico); `_pct_change` exige ambos preços > 0 — evita +100% quando insumo era 0 na UF (ex. 95995/AM 05/2026 vs 04/2026 sem alerta; 04 vs 03 ~+53% no total) |
| 2026-06-22 | **Avisos variação SINAPI na prévia CPU** | Compara com mês anterior importado; alerta >30% (total + insumos, ex. CBUQ 1518) |
| 2026-06-20 | **Separar banco de preços (SINAPI/TCPO) do catálogo RAG** | Sync grava só `price_bank`; catálogo `/settings/catalog` = NBR/TDR/modelos; purge `cost_index` ao excluir período; UI stats sem SINAPI FAISS |
| 2026-06-21 | Pipeline manutenção knowledge (OCR, órfãos, compact FAISS, index pending) | `pdf_text_extractor`, `knowledge_maintenance.py`, `POST /knowledge/maintenance` |
| 2026-06-20 | Force reindex NBR + fix `pdf_indexer` (`doc_type`) + cobertura por PDF | Indexação falhava silenciosamente; banner reflete path/dedup/código |
| 2026-06-20 | `normalize_nbr_code` + NBR explícita prioriza agente no router | `06122`≠`6122` quebrava boost; hint de disciplina bloqueava geotecnia |
| 2026-06-20 | `search_many` repassa `nbr_boost` + oversample maior | RAG agent-scoped não aplicava boost FAISS nem rerank NBR |
| 2026-06 | Router: regras antes de LLM | Determinismo + latência menor |
| 2026-06 | `agent_registry.py` como fonte única de nomes | Eliminar inconsistências `{disc}_agent` |
| 2026-06 | `BaseAgentIntelligent` separado de `BaseAgent` | Não quebrar agentes legados durante migração |
| 2026-06 | `USE_INTELLIGENT_AGENTS=true` como default | LLM real em produção; legado para rollback |
| 2026-06 | Ollama local (não cloud LLM) | Privacidade, custo zero, controle de modelos |
| 2026-06-19 | Settings com menu lateral (cortina mobile) + subrotas por módulo | `/settings`, `/settings/document-types`, `/settings/imports`, `/settings/catalog`, `/settings/indexing` — extensível via `settings-nav.tsx` |
| 2026-06-19 | Novos `content_type` na listbox de importação | `artigos`, `livros`, `bases_precos`, `memoriais`, `especificacoes`, `laudos` — labels em `content_types.py`; API `/knowledge/options`; escopos RAG atualizados |
| 2026-06 | `project_state.md` como control plane | Memória persistente do sistema; regra Cursor `alwaysApply` |
| 2026-06 | ContextGraph integrado no orchestrator | Memória compartilhada na síntese multi-disciplina |
| 2026-06 | `ChatAgent` (disciplina CHAT) | Fluxo conversacional separado do técnico |
| 2026-06 | Intent Layer v2 (`core/intent_layer.py`) | Decisão central chat / engenharia / mixed no `/chat` |
| 2026-06 | Learning Loop v1 (`core/learning/`, `agent_feedback`) | Coleta feedback para evolução futura de RAG/prompts |
| 2026-06 | Learning Loop v2 (`core/learning_v2/`) | Prompts versionados por disciplina a partir de feedback real |
| 2026-06 | Copilot v1 (`core/copilot/`, `POST /copilot`) | Planejamento + execução multi-agente + score de qualidade |
| 2026-06 | Evaluation Loop v2 (`core/evaluation_v2/`, `copilot_evaluations`) | Autoavaliação intent/plan/exec/response do Copilot |
| 2026-06 | Self-Improving Loop v1 (`core/self_improving/`) | Patches propostos auditáveis — nenhuma auto-modificação |
| 2026-06 | AED v1 (`core/aed/`, `POST /aed`, `aed_runs`) | Design autônomo paralelo — RAG v2 read-only, sem alterar agentes |
| 2026-06 | Structural System Selector (`core/structural_selector/`) | Classificação de sistema estrutural plugável no AED antes da simulação |
| 2026-06 | Evolution Loop v1 (`core/evolution/`) | Auto-otimização modelos/prompts/agentes/RAG com feature flags + audit trail |
| 2026-06 | Agent Generation v1 (`core/agent_generation/`) | Proposta controlada de agentes — sandbox, avaliação, promotion gate auditável |
| 2026-06 | Monorepo `backend/` + `frontend/` | Separação física Python/Next.js; servidor sobe de `backend/` |
| 2026-06 | Health dinâmico (`installed_models` via Ollama) | UI reflete modelos reais do WSL |
| 2026-06 | SIE v1 (`core/structural_intelligence/`) | Pipeline estrutural especializado plugável no dispatcher |
| 2026-06 | Model Router + Evaluation Loop v1 | Roteamento e ranking LLM por task_type (opt-in) |
| 2026-06 | Knowledge flat + metadata sidecar | Escalável; disciplina/tipo só em JSON, não em pastas |
| 2026-06 | RAG agent-aware (`core/knowledge/rag/`) | Cada agente com escopo; SINAPI nunca em estruturas |
| 2026-06 | Engineering Orchestrator | Único ponto de decisão: ENGINEERING vs COST vs DOCUMENTATION |
| 2026-06 | Knowledge upload UI (`/settings`) | Upload em lote via browser + API `/knowledge/*` |
| 2026-06 | Workspace local (projetos + conversas) | Contexto persistente estilo ChatGPT; multi-turn |
| 2026-06 | Project RAG multi-formato | FAISS por empreendimento; PDF/Office/CAD/BIM no upload |
| 2026-06 | Chat streaming UX | SSE `connected` instantâneo + render frontend ~60fps |
| 2026-06 | GeotecniaIntelligentAgent | Prompts NBR 6122/7185, classificação solo, A_min |
| 2026-06 | Cronograma CPM + Gantt no `/budget` | Sync orçamento → tarefas; curvas físico/financeiro; edição manual + agente IA |
| 2026-06 | Agente IA de cronograma enriquecido | Catálogo WBS JSON, detecção de intent, resolução código/nome, pós-processamento admin/obras |
| 2026-06 | Renumeração WBS automática | `renumber_wbs` após delete; endpoint `/itemization/renumber`; sync cronograma |
| 2026-06 | UI ComD/SemD no orçamento | Colunas paralelas (azul/verde); rodapé custo sem BDI + BDI + total adotado (menor valor) |
| 2026-06 | Vision Analysis Engine (`core/vision_engine/`) | Pipeline OCR→Gemma3→Qwen3; analisadores PDF/Image/Plant/PCI/Structural; workspace-status |
| 2026-06 | PCI CBMAM — RAG + checklist IT-11/NT-03 | Modo `pci` injeta Knowledge Layer (agente incendio) antes do Gemma3; prompt exige E-5/rotas tracejadas; `GET /vision/pci-checklist` cruza 9 arquivos; audit `rag_sources` |
| 2026-06 | Operational Transparency Layer (Fases 1–2) | ActivityPanel + Console + timeline; `project_activity_events`/`project_decisions`; auto-capture sem rewrite Agent-first |
| 2026-06 | Workflow Projetos Fase 2 | MinIO/local storage · PDF ReportLab · ZIP entrega · Celery+Redis · workflow_jobs · upload async · download artefatos |
| 2026-06 | Workflow classificação prancha/documento | PDFs com prefixo ARQ/PPCI+Rxx → pipeline completo; memorial/parecer/MD/memória de cálculo → indexação only; evita 9× pranchas falsas |
| 2026-06 | Workflow Fase 3 Wizard GRD | Pacote de entrega com seleção manual, templates A0–A4, nomenclatura padrão escritório, GRD PDF, ZIP 01_PRANCHAS/02_MEMORIAIS/… |
| 2026-06 | Norm Pack Studio (compliance ABNT) | Gap analysis + indexação em lote sem IA reescrever normas; `legal_source`: `abnt_licensed_pdf` \| `public_legislation`; produto comercializável multi-tenant |
| 2026-06 | Importação em lote NBR/NR (~900 PDFs) | Classificação em cascata (filename → pypdf 1ª página → LLM leve só ambíguos); **não** usar agente completo por arquivo; index FAISS único ao final; `edition_outdated` para acervo histórico |
| 2026-06 | Carimbo workflow — filtro legal NBR | RAG normativo + carimbo citam só `abnt_licensed_pdf`; legislação pública excluída do carimbo; metadado na ingestão e indexação PDF |
| 2026-06 | Norm gaps Wizard + export CSV | Alertas de NBR crítica pendente no Wizard de Entrega; `norm_gaps` em get_package; CSV em Pacotes NBR e wizard |
| 2026-06-20 | Auth JWT + usuários + rede | JWT HS256 + bcrypt; papéis `admin`/`dev_user`; seed admin/dev_user1/dev_user2; `/settings/users` e `/settings/access` (LAN + Cloudflare Tunnel); `AUTH_ENABLED` desliga proteção |
| 2026-06-20 | Quick Tunnel no painel de acesso | `quick_tunnel_service.py` inicia/para `cloudflared tunnel --url` (API :8000 + frontend :3000); URLs `*.trycloudflare.com`; sync CORS em `network_access.json`; UI em Configurações → Acesso e rede |
| 2026-06-20 | Conversas por usuário (`conversations.user_id`) | Filtro em list/get/chat/history/orchestrate; backfill legado → admin; `AUTH_ENABLED=false` mantém modo sem filtro |
| 2026-06-20 | M1–M5 curto prazo | Hardening JWT startup · smoke E2E · `/copilot`+`/aed` · `make test-cov` · `docs/e2e_validation_checklist.md` |
| 2026-06-26 | Proxy `/api-backend` para LAN e trycloudflare | `getApiBaseUrl()` + rewrite Next.js; equipe só precisa `:3000`; upload/importação sem expor `:8000` na LAN |
| 2026-06-26 | Fix upload projeto na LAN | Removido `from pathlib import Path` local em `upload_project_files` (UnboundLocalError) |
| 2026-06-26 | Análise geral do sistema | Seção 8: pontos fortes/fracos, melhorias M1–M15, métricas 618 testes / 223 endpoints, Fase 4 → 30% |
| 2026-06-21 | SINAPI formato nacional 2025+ | ZIP único `SINAPI-AAAA-MM-formato-xlsx.zip`; planilha Referência multi-UF; parser CSD/CCD+Analítico; ComD e SemD no banco |
| 2026-06-21 | Links SINAPI Caixa (upload manual) | `default.aspx` entra em redirect loop; UI/API usam `caixa.gov.br/sinapi` + `downloads.aspx#categoria_{UF}`; espelho sumário como fallback |
| 2026-06-21 | Import SINAPI com barra de progresso SSE | Endpoints `/pricing/sync/{source}/stream` e `/upload/stream`; UI `PriceImportProgressBar`; fases download→parse→bank→ingest→FAISS |
| 2026-06-21 | ComD + SemD sempre (sem checkbox) | `dual_desoneracao` no manifest; campos `price_sem_desoneracao` / `unit_price_sem` no banco |
| 2026-06-21 | CORS dev porta 3001 | Next.js fallback quando :3000 ocupado; `CORS_ALLOWED_ORIGINS` inclui 3001 |
| 2026-06-22 | Embed batch Ollama + indexação parcial na importação normas | HTTP 500 sob carga em lotes SICRO; `/api/embed` em batch de 4, throttle 150ms, backoff maior em 5xx, chunks falhos ignorados (não abortam PDF inteiro); classificador IN SICRO → ORÇAMENTO |
| 2026-06-22 | Save atômico FAISS (`chunks.json`) | `JSONDecodeError` ao importar DNIT/SICRO: UI fazia `reload_from_disk` enquanto `save()` gravava 50MB; escrita temp+`os.replace`, backup `.bak`, reload só se mtime mudou e sem job `knowledge`/`norm_bulk` ativo |
| 2026-06-22 | Importação web em background + Console | `KnowledgeWebImportContext` + banner global; job `knowledge_import` no Operations Console; fetch sem AbortSignal — navegar para `/console` não cancela importação DNIT/SICRO |
| 2026-06-20 | SINAPI colunas Grupo/Classificação/Origem/%AS | Parser nacional 2025+ persiste `grupo`, `classificacao`, `origem_preco`, `pct_as_comd`/`pct_as_semd` por UF; prévia CPU em `/settings/price-bases` e markdown do agente de orçamento |
| 2026-06-20 | tp2 unificado + encargos MO por UF | `tp2=AS` quando %AS>0 (SINAPI) ou coluna tp2 SEMINF; SEMINF cruza códigos SINAPI do mesmo mês; `labor_charges.json` com Horista/Mensalista ComD/SemD por UF |
| 2026-06-20 | Tema visual frontend (landing-reference) | Tokens `surface`/`brand` em `globals.css` + Tailwind; `cyan`→sky e `slate`→zinc; shell (Sidebar, chat, workspace, orçamento) com cards `border-white/5` e glow ambiente |
| 2026-06-20 | Esqueletos WBS + menu Orçamento expansível | `budget_skeletons.json` + API CRUD; `/budget/models`; modal novo orçamento escolhe esqueleto; sidebar com seta expandindo ações |

---

# 🔍 8. ANÁLISE GERAL DO SISTEMA (2026-06-26)

> Revisão transversal: arquitetura, qualidade, segurança, operação e débito técnico.  
> Base: código atual + `618` testes coletados + uso real LAN/Quick Tunnel.

## Resumo executivo

O **IA Server Santos** é um monorepo **maduro em domínio** (engenharia civil multiagente, orçamento SINAPI/SICRO, RAG normativo, workflow de projetos) com backend FastAPI bem estruturado (`routes → services → core/pricing`) e frontend Next.js cobrindo os fluxos principais. A equipe já opera em **LAN** e **Quick Tunnel** com auth JWT.

O principal gap não é “falta de features”, e sim **consolidação para produção**: hardening de segurança, testes de integração/frontend, modularização de arquivos gigantes e fechamento de UI para APIs já existentes (`/copilot`, `/aed`).

## Pontos positivos

| # | Área | Evidência |
|---|------|-----------|
| 1 | **Amplitude funcional** | Chat SSE, orquestração multi-disciplina, orçamento PPD completo, vision PCI, workflow entrega, norm packs, sync SINAPI/SICRO — tudo com API REST |
| 2 | **Arquitetura em camadas** | 22 módulos de rota, 18 services, ~38 domínios em `core/` — separação clara de responsabilidades |
| 3 | **Testes backend extensos** | 618 testes em 99 arquivos — orçamento, RAG, agentes, auth, workflow, manutenção |
| 4 | **Control plane** | Este documento + feature flags + decision log — rastreabilidade de decisões |
| 5 | **Separação NBR ≠ SINAPI** | Engineering Orchestrator + testes anti-contaminação — regra de negócio crítica preservada |
| 6 | **Auth + rede operacionais** | JWT middleware, papéis, `/settings/users`, proxy `/api-backend`, Quick Tunnel no painel |
| 7 | **Transparência operacional** | Operations Console, jobs SSE, backup/restore, painel de serviços DevOps |
| 8 | **Infra local reproduzível** | `Makefile`, Docker (PG/Redis/MinIO), scripts ingestão/sync, `validate-lan` |

## Pontos negativos

| # | Área | Evidência | Impacto |
|---|------|-----------|---------|
| 1 | **Zero testes frontend** | Nenhum `*.test.ts(x)` | Regressões UI/API client sem rede de segurança |
| 2 | **God files** | `pricing.py` (~92 rotas), `api.ts` (~2.7k linhas), `price-bases/page.tsx` (~1.6k) | Manutenção, review e onboarding difíceis |
| 3 | **APIs sem UI** | `POST /copilot`, `POST /aed` sem páginas dedicadas | Valor oculto para usuários finais |
| 4 | **Sem cobertura medida** | `pytest-cov` ausente; sem CI visível | Lacunas de teste invisíveis |
| 5 | **Suite completa instável** | `make test-backend` pode segfault (FAISS/extensões nativas) | CI local não confiável em 100% dos casos |
| 6 | **Integração workflow skipada** | `test_workflow_projetos.py` com skip permanente | Risco em pipeline de entrega |
| 7 | **Defaults inseguros p/ internet** | `JWT_SECRET=change-me…`, senhas seed, credenciais Docker exemplo | Risco se exposto sem hardening |
| 8 | **Código experimental duplicado** | `backend/experimental/` espelha módulos em `core/` | Drift e confusão de “fonte da verdade” |
| 9 | **Multi-tenant parcial** | Projetos ainda compartilhados; conversas já isoladas por `user_id` | M10 — `project.user_id` |
| 10 | **Latência LLM local** | 2–5 min/request em CPU (R-03) | UX em cargas pesadas |

## Melhorias sugeridas (priorizadas)

### Curto prazo (1–2 sprints)

| # | Melhoria | Benefício |
|---|----------|-----------|
| M1 | **Hardening exposição externa** — `core/auth/security_hardening.py` no startup · `AUTH_HARDENING_STRICT` · `.env.example` | ✅ Implementado |
| M2 | **Smoke tests E2E** — `test_smoke_e2e.py` · `make smoke-e2e` · `make validate-lan` | ✅ Implementado |
| M3 | **Páginas `/copilot` e `/aed`** — UI + `api.copilot()` / `api.aed()` + Sidebar | ✅ Implementado |
| M4 | **`pytest-cov` no Makefile** — `make test-cov` · HTML em `backend/htmlcov/` | ✅ Implementado |
| M5 | **Validação end-to-end documentada** — `docs/e2e_validation_checklist.md` | ✅ Checklist criado (execução manual pendente) |

### Médio prazo (1–2 meses)

| # | Melhoria | Benefício |
|---|----------|-----------|
| M6 | **Quebrar `pricing.py`** em sub-routers (`providers`, `sync`, `budget`, `export`, `tech_spec`) | ✅ Manutenibilidade |
| M7 | **Modularizar `api.ts`** — `http.ts`, `budget-session.ts`, `budget-api.ts`, `sse.ts` | ✅ Frontend escalável (pricing* extraído) |
| M8 | **CI GitHub Actions** — subset orçamento + export/ABC + Playwright `/budget` | ✅ ~74 pytest + 12 Playwright (`make test-ci`) |
| M9 | **Desbloquear testes workflow** — PostgreSQL de teste via `docker compose` profile | Integração entrega confiável |
| M10 | **Isolamento por usuário** — `project.user_id`, filtros em listagens | Conversas ✅ · orçamentos ✅ (B1) · projetos pendente |

### Longo prazo (roadmap)

| # | Melhoria | Benefício |
|---|----------|-----------|
| M11 | **Deploy produção** — Docker API+frontend ou VPS | SaaS real |
| M12 | **GPU / fila Ollama** — quotas por usuário no Console | Latência e fairness |
| M13 | **Consolidar `experimental/`** — migrar ou arquivar duplicatas | Menos débito |
| M14 | **Simuladores AED reais** — `concrete_armed_simulator` primeiro | AED deixa heurísticas |
| M15 | **OCR em lote** — ~230 PDFs scan (R-13) | Cobertura normativa |
| **B1–B15** | **Orçamento enterprise (ciclo 1)** — ver §8.1: ownership, versionamento, BDI, auditoria parcial, TCPO UI, E2E, CI, piloto | ✅ Produção interna · 🟡 licitação/CPQ pendente |
| **B16+** | Auditoria completa, piloto §4.U, `SESSION_STORE` servidor, paridade `.xlsm`, E2E real | Fechar gaps #7, #10, #12, #14, #3 |

## Matriz força × prioridade

```
                    IMPACTO ALTO
                         │
    M3 Copilot/AED UI    │    M1 Hardening JWT/senhas
    M5 Validação E2E     │    M6 Split pricing.py
                         │
    M13 experimental     │    M2 Smoke E2E + M4 pytest-cov
                         │    M10 Multi-user projects
                         │
                    IMPACTO BAIXO
              ESFORÇO BAIXO ──────── ESFORÇO ALTO
```

## Saúde por camada

| Camada | Nota | Comentário |
|--------|------|------------|
| Domínio / produto | **A** | Escopo rico e diferenciado para escritório de engenharia |
| Backend / API | **B+** | Sólido; god files e flags off reduzem nota |
| Frontend / UX | **B** | Fluxos principais OK; faltam páginas e testes |
| Testes / QA | **B** | ~82 pytest orçamento + 12 Playwright (`make test-ci`); E2E export mockado |
| Segurança | **B−** | Auth OK; defaults dev e CORS exigem hardening externo |
| DevOps / operação | **B+** | Backup, console, LAN, Quick Tunnel — falta deploy prod |
| Documentação | **A−** | Control plane maduro; manter sincronizado |

**Nota geral estimada: B** — sistema **operacional e avançado** para uso interno; **não production-ready** para internet pública sem M1, M8 e M11.

---

# 📌 9. COMO ATUALIZAR ESTE DOCUMENTO

## Workflow (início de sessão)

1. Usuário ou agente: **"atualiza project_state.md"**
2. Ler este arquivo inteiro
3. Verificar código vs snapshot (grep, health, testes se necessário)
4. Corrigir divergências
5. Identificar próximo passo no roadmap
6. Executar a tarefa pedida

## Workflow (fim de sessão / marco concluído)

1. Atualizar **Snapshot operacional** se status mudou
2. Marcar `[x]` no **Roadmap** (seção 3)
3. Registrar decisão na **seção 7** se aplicável
4. Adicionar risco na **seção 6** se aplicável
5. Revisar **seção 8 (Análise geral)** e **§8.1 (Orçamento enterprise)** se mudou arquitetura, testes, segurança ou módulo orçamento
6. Atualizar **Última atualização** no topo

**Regra:** se o código mudou e este doc não reflete, o doc está errado — corrigir antes do próximo deploy.
