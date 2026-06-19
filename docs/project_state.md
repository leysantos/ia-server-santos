# 🧠 IA SERVER SANTOS — PROJECT STATE (CONTROL PLANE)

> **Painel de controle de engenharia do sistema** — fonte única de verdade sobre arquitetura, status, riscos e roadmap.  
> Atualizar este documento a cada marco relevante (feature merge, mudança de infra, decisão arquitetural).

| Campo | Valor |
|-------|-------|
| **Versão do sistema** | 1.0.0 |
| **Última atualização** | 2026-06-18 |
| **Marco atual** | Fase 2 (88%) — 68 NBRs (636 chunks) ✅ · Workspace + Project RAG multi-formato ✅ |
| **Próximo foco** | Validar RAG de projeto no `/chat?project=` · upload SINAPI/TCPO |
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
| RAG v2 pipeline | 🟢 636+ chunks NBR indexados — validar consultas no `/chat` |
| Knowledge Layer multi-base | 🟢 FAISS por base (NBR, SINAPI, TCPO, TDR…) — `USE_KNOWLEDGE_ROUTER=false` |
| Knowledge storage flat | 🟢 `knowledge/raw/documents/` + metadata sidecar + `catalog.jsonl` |
| RAG agent-aware | 🟢 15 agentes com escopo isolado — `USE_AGENT_SCOPED_RAG=true` |
| Engineering Orchestrator | 🟢 Separação NBR ↔ SINAPI — `USE_ENGINEERING_ORCHESTRATOR=true` |
| RAG performance | 🟢 Cache semântico, rerank leve, métricas latência — default ON |
| **Workspace (projetos + conversas)** | 🟢 CRUD projetos/conversas · busca · multi-turn · painel lateral no `/chat` |
| **Project RAG multi-formato** | 🟢 FAISS por projeto — PDF, Office, CSV, TXT, DXF, IFC, DWG (parcial) |
| Chat streaming UX | 🟢 SSE instantâneo (`connected`) + tokens ~60fps (`flushSync` + rAF) |
| Agente Geotecnia dedicado | 🟢 `GeotecniaIntelligentAgent` — NBR 6122/7185, classificação solo, A_min |
| Frontend | 🟢 `/chat`, `/projects`, `/orchestrate`, `/history`, `/settings` — falta `/copilot`, `/aed` |
| Auth SaaS | 🔴 não implementado |

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

`qwen3:8b` · `qwen3:14b` · `qwen3-coder` · `gemma3:12b` · `mistral:7b` · `phi3:mini` · `qwen2.5-coder` · `deepseek-coder` · `nomic-embed-text`

Config padrão: chat=`qwen3:8b`, eng=`qwen3:14b`, fallback=`qwen3-coder`, embed=`nomic-embed-text`.  
`GET /health` retorna lista dinâmica via Ollama; frontend exibe badge **WSL:** no `/chat`.

## Bloqueio principal

**Bases de custo ainda não indexadas** — NBRs já estão no FAISS (636+ chunks). Falta popular SINAPI/TCPO em `backend/knowledge/raw/documents/`:

| Metadata (`discipline`) | Exemplo de conteúdo |
|-------------------------|---------------------|
| `estruturas` | NBRs |
| `orcamento` | SINAPI, TCPO |
| `geral` | TDRs, projetos |
| `arquitetura` | Catálogos |
| `meio_ambiente` | Dados regionais |

Disciplina e tipo (`content_type`) ficam no sidecar `{arquivo}.knowledge.json` e em `catalog.jsonl` — **sem subpastas por disciplina ou tipo**.

```bash
cd backend && python3 scripts/index_knowledge_bases.py
# Ou via UI: http://localhost:3000/settings → Upload em lote / Indexar NBR
```

Dependências de indexação (knowledge): `pip install pypdf python-multipart openpyxl python-docx xlrd`  
Dependências de indexação (project RAG): `ezdxf ifcopenshell` (opcional CAD/BIM)

Ativar multi-index explícito (opcional): `USE_KNOWLEDGE_ROUTER=true`

**Regra arquitetural:** SINAPI/TCPO = **somente orçamento**. NBR = **somente engenharia**. Orquestrador garante separação mesmo com flags ON.

## Próximos passos (ordem recomendada)

1. Validar Project RAG end-to-end: upload DOCX/XLSX/IFC → reindex → `/chat?project=<id>`
2. Popular e indexar SINAPI/TCPO — desbloqueia orçamento real no orquestrador
3. Validar RAG normativo end-to-end: ingest → index → `/chat` e `/orchestrate` com chunks NBR
4. Simulador real `concrete_armed_simulator` (AED hoje usa heurísticas)
5. Frontend `/aed` consumindo `POST /aed`
6. Execution Planner (Orchestrator v2 — dependências entre disciplinas)
7. Frontend `/copilot`

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

| Componente | Status | Observação |
|------------|--------|------------|
| FastAPI (`:8000`) | 🟢 | Gateway REST — rodar de `backend/` |
| PostgreSQL (`:5433`) | 🟢 | conversations, messages, projects, project_files, agent_runs, orchestrator_logs, … |
| Ollama (`:11434`) | 🟢 | 9 modelos no WSL (ver handoff) |
| RAG v2 pipeline | 🟢 | **636 chunks NBR** indexados · SINAPI/TCPO pendentes |
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
| Frontend Next.js | 🟢 | `/chat`, `/projects`, `/orchestrate`, `/history`, `/settings` — falta `/copilot`, `/aed` |
| **Workspace** | 🟢 | Projetos, conversas multi-turn, busca, painel lateral — `WorkspacePanel` |
| **Project RAG** | 🟢 | FAISS isolado por projeto · 12 formatos · `GET /projects/formats` |
| Agente Geotecnia | 🟢 | `geotecnia_intelligent.py` — prompts NBR 6122/7185 |
| Copilot v1 | 🟢 | `POST /copilot` + Evaluation v2 + Self-Improving (background) |
| AED v1 | 🟢 | `POST /aed` + Structural Selector + `aed_runs` |
| Learning Loops | 🟢 | v1 (feedback) + v2 (auto-tune, `USE_TUNED_PROMPTS=false`) |
| Autenticação SaaS | 🔴 | Não implementada |
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
Fase 2  Orquestração + AED   █████████████████░░░   88%  🟡  ← estamos aqui (+ workspace)
Fase 3  RAG avançado         ██████████░░░░░░░░░░   50%  🟡  ← agent-scoped OK; project RAG OK; falta TDRs/custo
Fase 4  SaaS produção        ░░░░░░░░░░░░░░░░░░░░    0%  🔴
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
| Jun/26 | **GeotecniaIntelligentAgent** — prompts geotécnicos especializados | ✅ ← último marco |

### O que falta para fechar a Fase 2

| # | Tarefa | Prioridade | Esforço |
|---|--------|------------|---------|
| 1 | **Validar Project RAG** — upload multi-formato → `/chat?project=` | 🔴 Crítica | Baixo |
| 2 | **Indexar SINAPI/TCPO** (`index_knowledge_bases.py --base sinapi`) | 🔴 Crítica | Baixo |
| 3 | Simuladores por sistema estrutural (`concrete_armed_simulator`, etc.) | Alta | Médio |
| 4 | Execution Planner (ordem + dependências entre disciplinas) | Alta | Alto |
| 5 | Frontend `/aed` e `/copilot` | Média | Médio |
| 6 | Integrar Copilot → AED (disparo automático p/ projetos estruturais) | Média | Baixo |
| 7 | Propagação de premissas entre agentes (Orchestrator v2 completo) | Média | Alto |

### Próximo passo recomendado

> **1.** Criar projeto em `/projects`, fazer upload de memorial/planilha/IFC e testar `/chat?project=<id>`  
> **2.** Indexar SINAPI/TCPO em `knowledge/raw/documents/`  
> **3.** Implementar simulador dedicado `concrete_armed_simulator` (primeiro do registry)

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
| PostgreSQL | `core/database/` | Models, repository, service, connection, `migrate_workspace.py` |
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
| `WorkspacePanel` | `frontend/components/WorkspacePanel.tsx` | Sidebar: projetos, conversas, busca |
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
| DB migration | `core/database/migrate_workspace.py` | 🟢 Roda no `init_db` |
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

- [x] **NBR indexada** — 68 PDFs · 636+ chunks FAISS (validar qualidade das respostas)
- [ ] **SINAPI/TCPO não indexados** — orçamento ainda depende só do LLM
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

## Fase 2 — Orquestração + Engenharia Autônoma 🟡 88% ← ESTAMOS AQUI

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

- [x] `core/models/model_router.py` — mapa por task_type (phi3, mistral, qwen3, gemma3, etc.)
- [x] `core/models/model_evaluation_loop.py` — primary vs fallback + PostgreSQL
- [x] `GET /models/status`
- [ ] Ativar `USE_MODEL_ROUTER=true` após validação em staging

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

## Fase 4 — SaaS Real 🔴 NÃO INICIADA

- [ ] JWT Authentication
- [ ] Multiusuário
- [x] Workspace local (projetos + conversas + arquivos) — **sem isolamento por tenant**
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
| Página frontend `/aed` | 2 | Alta |
| Página frontend `/copilot` | 1b | Alta |
| `concrete_armed_simulator` (primeiro simulador real) | 2 | Alta |
| Execution Planner no Orchestrator | 2 | Alta |
| Validação normativa pós-LLM | 1 | Média |
| GPU / otimização de latência | 1 | Média |
| Auth JWT | 4 | Baixa (até MVP SaaS) |

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
# ollama pull gemma3:12b mistral:7b phi3:mini qwen2.5-coder deepseek-coder

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

## Variáveis de ambiente relevantes

| Variável | Default | Efeito |
|----------|---------|--------|
| `USE_INTELLIGENT_AGENTS` | `true` | `true` = RAG+LLM; `false` = agentes simulados |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Endpoint Ollama |
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

**Streaming:** `POST /chat/stream` (SSE) — evento `connected` imediato; fases `rag` → `rag_done` → `llm_start`; tokens em tempo real (~60fps no UI).

Settings completas: `backend/config/settings.py`

---

# ⚠️ 6. RISCOS E ISSUES CONHECIDOS

| ID | Severidade | Descrição | Mitigação |
|----|------------|-----------|-----------|
| R-01 | Alta | SINAPI/TCPO ainda não indexados | Upload via `/settings` · `index_knowledge_bases.py` |
| R-02 | Alta | LLM pode alucinar tabelas/nomenclaturas normativas | RAG + validação pós-resposta; prompts com restrições |
| R-03 | Média | Latência 2–5 min por request (CPU local) | GPU; modelo menor; streaming ✅ no chat |
| R-09 | Média | DWG indexa só strings ASCII (extração parcial) | Exportar para PDF/DXF antes do upload |
| R-10 | Baixa | Project RAG não validado com arquivos reais de obra | Testar upload + `/chat?project=` end-to-end |
| R-04 | Média | Orchestrator v1 executa agentes com contexto limitado | Orchestrator v2: Execution Planner + dependências |
| R-07 | Média | AED simula via heurísticas — simuladores dedicados ainda não existem | Implementar `*_simulator` por sistema estrutural |
| R-08 | Baixa | Frontend sem `/aed` e `/copilot` | Criar páginas consumindo endpoints existentes |
| R-05 | Baixa | CORS `allow_origins=["*"]` | Restringir em produção |
| R-06 | Baixa | Sem autenticação | Fase 4 SaaS |

---

# 📋 7. DECISION LOG

| Data | Decisão | Motivo |
|------|---------|--------|
| 2026-06 | RAG v2 com FAISS substitui JSON vector store | Performance e persistência |
| 2026-06 | Router: regras antes de LLM | Determinismo + latência menor |
| 2026-06 | `agent_registry.py` como fonte única de nomes | Eliminar inconsistências `{disc}_agent` |
| 2026-06 | `BaseAgentIntelligent` separado de `BaseAgent` | Não quebrar agentes legados durante migração |
| 2026-06 | `USE_INTELLIGENT_AGENTS=true` como default | LLM real em produção; legado para rollback |
| 2026-06 | Ollama local (não cloud LLM) | Privacidade, custo zero, controle de modelos |
| 2026-06 | PostgreSQL para audit trail | Histórico de conversas e execuções de agentes |
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

---

# 📌 8. COMO ATUALIZAR ESTE DOCUMENTO

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
5. Atualizar **Última atualização** no topo

**Regra:** se o código mudou e este doc não reflete, o doc está errado — corrigir antes do próximo deploy.
