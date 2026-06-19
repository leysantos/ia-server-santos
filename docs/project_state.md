# 🧠 IA SERVER SANTOS — PROJECT STATE (CONTROL PLANE)

> **Painel de controle de engenharia do sistema** — fonte única de verdade sobre arquitetura, status, riscos e roadmap.  
> Atualizar este documento a cada marco relevante (feature merge, mudança de infra, decisão arquitetural).

| Campo | Valor |
|-------|-------|
| **Versão do sistema** | 1.0.0 |
| **Última atualização** | 2026-06-18 |
| **Marco atual** | Fase 2 — Engenharia autônoma (AED + Structural Selector) ✅ |
| **Próximo foco** | Indexar RAG + simuladores por sistema estrutural + UI `/aed` |
| **Repositório** | [github.com/leysantos/ia-server-santos](https://github.com/leysantos/ia-server-santos) |
| **Branch principal** | `main` |
| **Modo padrão de agentes** | Inteligente (`USE_INTELLIGENT_AGENTS=true`) |

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
| FastAPI (`:8000`) | 🟢 | Gateway REST ativo |
| PostgreSQL (`:5433`) | 🟢 | `conversations`, `agent_runs`, `orchestrator_logs`, `agent_feedback`, `aed_runs` |
| Ollama (`:11434`) | 🟢 | LLM + embeddings locais |
| RAG v2 (FAISS) | 🟡 | Pipeline pronto; **índice vazio** (0 chunks) |
| Agentes inteligentes | 🟢 | 15 disciplinas via `BaseAgentIntelligent` |
| ChatAgent (CHAT) | 🟢 | Intent layer + system prompt fixo + `qwen3:8b` + metadata SaaS |
| Agentes legados | 🟡 | Disponíveis via `USE_INTELLIGENT_AGENTS=false` |
| Frontend Next.js | 🟢 | `/chat`, `/orchestrate`, `/history` — falta `/copilot` e `/aed` |
| Copilot v1 | 🟢 | `POST /copilot` + Evaluation v2 + Self-Improving (background) |
| AED v1 | 🟢 | `POST /aed` — pipeline completo + persistência `aed_runs` |
| Structural Selector | 🟢 | Integrado no AED antes da simulação |
| Learning Loops | 🟢 | v1 (feedback) + v2 (auto-tune prompts, opt-in) |
| Autenticação SaaS | 🔴 | Não implementada |
| Orchestrator v2 | 🟡 | ContextGraph ✅ · Execution Planner 🔴 · dependências 🔴 |
| ContextGraph | 🟢 | Ativo no orchestrator e Copilot |

**Health check:** `GET /health` → `{ status, database, rag_version, rag_indexed_chunks, ollama, models }`

---

## 📍 ONDE ESTAMOS AGORA

```
Fase 0  Core Infra          ████████████████████  100%  ✅
Fase 1  Agentes + RAG       ████████████░░░░░░░░   62%  🟡  ← bloqueio: índice RAG vazio
Fase 1b Loops de evolução    ████████████████████  100%  ✅
Fase 2  Orquestração + AED   ██████████████░░░░░░   70%  🟡  ← estamos aqui
Fase 3  RAG avançado         ░░░░░░░░░░░░░░░░░░░░    0%  🔴
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
| Jun/26 | **Structural System Selector v1** — classificação pré-simulação | ✅ ← último marco |

### O que falta para fechar a Fase 2

| # | Tarefa | Prioridade | Esforço |
|---|--------|------------|---------|
| 1 | **Indexar NBRs** (`python scripts/index_nbrs.py`) | 🔴 Crítica | Baixo |
| 2 | Simuladores por sistema estrutural (`concrete_armed_simulator`, etc.) | Alta | Médio |
| 3 | Execution Planner (ordem + dependências entre disciplinas) | Alta | Alto |
| 4 | Frontend `/aed` e `/copilot` | Média | Médio |
| 5 | Integrar Copilot → AED (disparo automático p/ projetos estruturais) | Média | Baixo |
| 6 | Propagação de premissas entre agentes (Orchestrator v2 completo) | Média | Alto |

### Próximo passo recomendado

> **1.** Colocar PDFs em `data/nbrs/` e rodar `python scripts/index_nbrs.py`  
> **2.** Implementar simulador dedicado `concrete_armed_simulator` (primeiro do registry)  
> **3.** Criar página frontend `/aed` consumindo `POST /aed`

---

# 🟢 1. CORE INFRAESTRUTURA (CONCLUÍDO)

## Backend

| Módulo | Path | Responsabilidade |
|--------|------|------------------|
| API Gateway | `app/main.py` | FastAPI, CORS, lifespan, rotas |
| Router v2 | `core/router.py` | Saudação → regras (keywords) → LLM fallback → GERAL |
| Agent Registry | `core/agent_registry.py` | Fonte única: disciplina → `{modulo}_agent` |
| Dispatcher | `core/dispatcher.py` | Roteia para agente; persiste `agent_runs` + Learning Loop |
| Orchestrator v1 | `core/orchestrator.py` | Decomposição multi-disciplina + síntese + feedback orchestrator |
| Learning Loop v1 | `core/learning/` | Coleta `agent_feedback` (execução + rating) |
| Learning Loop v2 | `core/learning_v2/` | Auto-tuning de prompts por disciplina (rule-based) |
| Copilot v1 | `core/copilot/` | Intent → plan → execute → synthesize → evaluate |
| Evaluation Loop v2 | `core/evaluation_v2/` | Autoavaliação do Copilot (4 níveis + PostgreSQL) |
| Self-Improving Loop v1 | `core/self_improving/` | Meta-análise + patches propostos (sem auto-apply) |
| AED v1 | `core/aed/` | Design autônomo: gerar → simular → comparar → selecionar → relatório |
| Structural Selector | `core/structural_selector/` | Classificação de sistema estrutural antes da simulação AED |
| PostgreSQL | `core/database/` | Models, repository, service, connection |
| Settings | `config/settings.py` | Ollama, RAG, DB, feature flags |

### Endpoints REST

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/health` | Status DB, RAG, Ollama |
| `POST` | `/chat` | Single-domain: router → RAG → agente |
| `POST` | `/orchestrate` | Multi-domain: decompose → N agentes → síntese |
| `POST` | `/copilot` | Copilot v1: plan → multi-agente → síntese → score |
| `POST` | `/aed` | AED v1: understanding → designs → simulação → seleção → relatório |
| `POST` | `/chat/stream` | Chat SSE (Intent Layer + tokens) |
| `POST` | `/feedback` | Rating/comentário sobre resposta (Learning Loop) |
| `GET` | `/history` | Histórico de conversas e execuções |
| `GET` | `/docs` | OpenAPI Swagger |

## Frontend

| Rota | Path | Descrição |
|------|------|-----------|
| `/chat` | `frontend/app/chat/page.tsx` | Interface de chat single-agent |
| `/orchestrate` | `frontend/app/orchestrate/page.tsx` | Orquestração multi-disciplina |
| `/history` | `frontend/app/history/page.tsx` | Histórico de execuções |
| API client | `frontend/services/api.ts` | Cliente HTTP → `localhost:8000` (auth-ready) |

## IA Engine — RAG v2

| Componente | Path | Status |
|------------|------|--------|
| RAG Engine | `memory/rag_engine.py` | 🟢 Orquestrador RAG |
| FAISS Store | `memory/faiss_store.py` | 🟢 Índice vetorial persistente |
| Embeddings | `memory/embeddings.py` | 🟢 `nomic-embed-text` via Ollama |
| Retriever | `memory/retriever.py` | 🟢 Hybrid search + ranking |
| Chunker | `memory/chunker.py` | 🟢 600–1200 tokens, overlap |
| PDF Indexer | `memory/pdf_indexer.py` | 🟢 Indexação NBR/TDR |
| Embedding cache | `memory/embedding_cache.py` | 🟢 SQLite cache |
| Script indexação | `scripts/index_nbrs.py` | 🟢 CLI para popular índice |

**Dados:** PDFs em `data/nbrs/` e `data/tdrs/` → índice em `memory/faiss_index/`

## Persistência (PostgreSQL)

```
conversations
  ├── orchestrator_logs
  ├── agent_runs
  └── agent_feedback   # Learning Loop v1 (execução + rating)
```

| Tabela | Campos-chave |
|--------|--------------|
| `conversations` | `input_text`, `mode` (single \| orchestrate) |
| `orchestrator_logs` | `disciplines[]`, `final_report`, `synthesis`, `use_rag` |
| `agent_runs` | `agent_name`, `discipline`, `result_text`, `had_context`, `extra` (JSON) |
| `agent_feedback` | `input_text`, `response_text`, `rating`, `feedback_text`, `corrected_answer` |
| `copilot_evaluations` | `intent_accuracy`, `plan_quality`, `execution_completeness`, `response_quality`, `final_score`, `issues` |
| `system_failures` | `failure_type`, `route_decision`, `evaluation_scores`, `suggested_fix` |
| `system_patches` | `patch_key`, `patch_version`, `patch_type`, `content` (JSON), `risk_score` |
| `aed_runs` | `input_text`, `understanding`, `designs`, `simulations`, `comparison`, `selection`, `report`, `use_rag` |

**Docker:** `infra/docker/docker-compose.yml` — porta **5433**  
**Init:** `python scripts/init_db.py`

### Learning Loop v2 (arquivos)

```
data/learning_v2/
  profiles/ESTRUTURAL.json    # discipline profile
  prompts/estrutural/prompt_estrutural_v1.txt   # versionamento imutável
```

**Job manual:** `python scripts/run_auto_tune.py [--discipline ESTRUTURAL]`

**Runtime (opt-in):** `USE_TUNED_PROMPTS=true` — agentes inteligentes usam a versão ativa do profile em `build_prompt()`.

## Testes

| Suite | Path | Cobertura |
|-------|------|-----------|
| Router | `tests/test_router.py` | Regras + roteamento |
| Orchestrator | `tests/test_orchestrator.py` | Decompose, execute, synthesize |
| API | `tests/test_api.py` | Endpoints HTTP |
| RAG/Memory | `tests/test_memory.py` | FAISS, chunker, retriever |
| Database | `tests/test_database.py` | Persistência |
| Learning Loop | `tests/test_learning_loop.py` | Feedback, low-quality, dispatcher |
| Learning Loop v2 | `tests/test_learning_loop_v2.py` | Profiles, versionamento, auto-tune |
| Copilot v1 | `tests/test_copilot.py` | Intent, plan, execução, avaliação |
| Evaluation Loop v2 | `tests/test_evaluation_loop_v2.py` | Scores, pipeline, persistência |
| Self-Improving Loop | `tests/test_self_improving_loop.py` | Meta-análise, patches, persistência |
| AED v1 | `tests/test_aed.py` | Pipeline completo, ≥2 designs/disciplina, persistência |
| Structural Selector | `tests/test_structural_selector.py` | Heurísticas, normas, integração AED |
| Agent Registry | `tests/test_agent_registry.py` | Mapeamento disciplinas |
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
| `models/ollama_client.py` | Cliente Ollama com fallback de modelo |
| `agents/*.py` | Agentes legados (`BaseAgent`) — mantidos, não usados por padrão |

### Gaps conhecidos da inteligência

- [ ] **Índice RAG vazio** — PDFs não indexados; respostas dependem só do LLM
- [ ] **Prompts genéricos** — um template único por disciplina; falta especialização fina
- [ ] **Validação normativa** — LLM pode confundir nomenclaturas (ex.: classes I–IV vs A–D na NBR 6118)
- [ ] **Latência alta** — inferência local ~2–5 min por request em CPU
- [ ] **Agentes customizados** — só `estruturas_intelligent.py`; demais usam factory genérica
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

## Fase 1 — Inteligência de Agentes 🟡 62%

- [x] `BaseAgentIntelligent` (RAG + LLM)
- [x] Integração no dispatcher (`USE_INTELLIGENT_AGENTS`)
- [x] Factory inteligente para 15 disciplinas
- [x] Propagação `use_rag` (chat + orchestrator)
- [x] Streaming SSE no chat (`POST /chat/stream`)
- [x] Metadata de modelo ativo no health + frontend
- [ ] **Indexar NBRs em produção** ← bloqueio principal
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

---

## Fase 2 — Orquestração + Engenharia Autônoma 🟡 70% ← ESTAMOS AQUI

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

---

## Fase 3 — RAG Avançado 🔴 NÃO INICIADA

- [ ] RAG por disciplina com isolamento forte (namespaces FAISS)
- [ ] Ranking técnico de normas (boost por relevância + versão)
- [ ] Indexação TDRs além de NBRs
- [ ] Re-ranking com cross-encoder ou LLM reranker
- [ ] Métricas de recall/precisão por disciplina

---

## Fase 4 — SaaS Real 🔴 NÃO INICIADA

- [ ] JWT Authentication
- [ ] Multiusuário
- [ ] Projetos por usuário (workspace)
- [ ] Isolamento de contexto RAG por tenant
- [ ] Billing / planos
- [ ] Deploy produção (Netlify ou VPS + Docker)

---

## Backlog transversal (qualquer fase)

| Tarefa | Fase | Prioridade |
|--------|------|------------|
| Indexar PDFs NBR em `data/nbrs/` | 1 | 🔴 Crítica |
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
Frontend (Next.js)
    ↓ POST /chat
FastAPI Gateway
    ↓
ChatService
    ↓
Router v2 (rules → LLM → GERAL)
    ↓
RAG v2 enrich (opcional, use_rag=true)
    ↓
Dispatcher → BaseAgentIntelligent
    ↓                    ↓
RAG v2 (FAISS)      Ollama LLM
    ↓
PostgreSQL (agent_runs + agent_feedback)
    ↓
Resposta JSON → Frontend
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
Orchestrator v1
    ↓ decompose_problem (keywords + LLM)
    ↓ execute_agents (N × dispatch + ContextGraph.add_result)
    ↓ build_global_context → synthesize_results(context=...)
PostgreSQL (orchestrator_logs + agent_runs + agent_feedback)
    ↓
Resposta JSON → Frontend
```

## Mapa de diretórios (ownership)

```txt
ia-server-santos/
├── app/                    # API REST (routes, services, schemas)
├── agents/                 # Agentes legados (BaseAgent simulado)
├── core/
│   ├── agents/             # Agentes inteligentes + factories
│   ├── database/           # PostgreSQL ORM + service
│   ├── learning/           # Learning Loop v1 (feedback_service)
│   ├── learning_v2/        # Learning Loop v2 (auto-tuning prompts)
│   ├── copilot/            # Copilot v1 (plan + evaluate)
│   ├── evaluation_v2/      # Evaluation Loop v2 (autoavaliação Copilot)
│   ├── self_improving/     # Self-Improving Loop v1 (patches propostos)
│   ├── aed/                # AED v1 (design autônomo)
│   ├── structural_selector/  # Classificação de sistema estrutural
│   ├── agent_registry.py   # Fonte única nomes de agentes
│   ├── router.py           # Router v2
│   ├── dispatcher.py       # Dispatch + persistência
│   ├── orchestrator.py     # Orchestrator v1
│   └── context_graph.py    # ContextGraph (Orchestrator v2)
├── memory/                 # RAG v2 (FAISS, embeddings, chunker)
├── models/                 # Ollama client
├── config/                 # Settings centralizadas
├── data/nbrs/              # PDFs normativos (input RAG)
├── data/tdrs/              # TDRs (input RAG)
├── frontend/               # Next.js SaaS UI
├── infra/docker/           # PostgreSQL compose
├── scripts/                # init_db, index_nbrs
├── tests/                  # Test suites
└── docs/                   # Documentação (este arquivo)
```

---

# ⚙️ 5. RUNBOOK — COMO SUBIR O SISTEMA

## Pré-requisitos

- Python 3.11+
- Node.js 18+
- Docker (PostgreSQL)
- Ollama com modelos: `qwen3:14b`, `qwen3-coder`, `nomic-embed-text`

## Subir stack completa

```bash
# 1. PostgreSQL
cd infra/docker && docker compose up -d

# 2. Banco
python scripts/init_db.py

# 3. Ollama (se não estiver rodando)
ollama pull qwen3:14b
ollama pull qwen3-coder
ollama pull nomic-embed-text

# 4. Indexar NBRs (recomendado)
# Colocar PDFs em data/nbrs/ e executar:
python scripts/index_nbrs.py

# 5. Backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

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
| `CHAT_USE_LLM` | `true` | `false` = só templates (testes/offline) |

**Streaming:** `POST /chat/stream` (SSE) — tokens em tempo real + status por agente/modelo.

Settings completas: `config/settings.py`

---

# ⚠️ 6. RISCOS E ISSUES CONHECIDOS

| ID | Severidade | Descrição | Mitigação |
|----|------------|-----------|-----------|
| R-01 | Alta | Índice RAG vazio → respostas sem base normativa indexada | **Próximo passo #1:** indexar PDFs; monitorar `rag_indexed_chunks` |
| R-02 | Alta | LLM pode alucinar tabelas/nomenclaturas normativas | RAG + validação pós-resposta; prompts com restrições |
| R-03 | Média | Latência 2–5 min por request (CPU local) | GPU; modelo menor; streaming ✅ no chat |
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
