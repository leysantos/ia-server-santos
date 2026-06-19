# backend/data — estado mutável local

**Não coloque PDFs, normas ou conhecimento técnico aqui.**  
Use `backend/knowledge/` para documentos e `backend/memory/faiss_index/` para índices FAISS.

Esta pasta guarda JSON/arquivos gerados em runtime pelos loops de otimização (feature flags desligadas por padrão):

| Subpasta | Flag | Conteúdo |
|----------|------|----------|
| `learning_v2/profiles/` | `USE_TUNED_PROMPTS` | Perfis por disciplina (`ESTRUTURAL.json`, …) |
| `learning_v2/prompts/` | `USE_TUNED_PROMPTS` | Prompts otimizados por disciplina |
| `evolution/` | `USE_EVOLUTION_LOOP` | `rag_chunk_profiles.json` — boosts RAG aprendidos |
| `agent_generation/` | `USE_AGENT_GENERATION` | `candidates.json` — agentes candidatos (nunca auto-ativados) |

Pastas são criadas sob demanda pelos módulos em `core/learning_v2/`, `core/evolution/` e `core/agent_generation/`.

## Onde vai cada coisa

```
backend/knowledge/          ← PDFs, CSVs, TDRs (fonte técnica)
backend/memory/faiss_index/ ← índices vetoriais (gerados por scripts)
backend/data/               ← estado de loops (JSON local)
PostgreSQL                  ← conversas, runs, feedback, evolution audit
```

## Comandos relacionados

```bash
python3 scripts/run_auto_tune.py              # popula learning_v2/
python3 scripts/index_knowledge_bases.py      # popula memory/faiss_index/
python3 scripts/ingest_knowledge_document.py  # popula knowledge/
```
