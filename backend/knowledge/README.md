# Knowledge Layer — storage flat + metadata

## Filesystem (único)

```
backend/knowledge/raw/documents/     ← todos os PDFs, CSVs, planilhas
backend/knowledge/catalog.jsonl    ← registro central de ingestão
backend/memory/faiss_index/        ← índices vetoriais (RAG)
backend/data/                      ← estado de loops
```

## Disciplinas = metadata (não pastas)

Cada arquivo pode ter sidecar `{nome}.knowledge.json`:

```json
{
  "id": "uuid",
  "filename": "NBR-6118.pdf",
  "discipline": ["estruturas"],
  "content_type": "nbrs",
  "source": "nbr_catalog",
  "confidence": 0.92,
  "tags": []
}
```

## Ingestão

```bash
python3 scripts/ingest_knowledge_document.py --file NBR-6118.pdf --discipline ESTRUTURAL
python3 scripts/index_knowledge_bases.py
```

## Compatibilidade

APIs legadas (`get_path("nbr")`, `NBR_DIR`, `index_nbrs.py`) apontam para `raw/documents/`.
Índices FAISS por domínio (nbr, sinapi…) permanecem — filtragem por `content_type` no metadata.

## Migração layout antigo

```bash
python3 scripts/scaffold_discipline_knowledge.py --migrate --prune
```

Código: `core/knowledge/resolver.py` · `core/knowledge/metadata.py`
