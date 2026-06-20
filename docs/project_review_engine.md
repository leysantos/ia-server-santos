# Project Review Engine — Arquitetura

> Módulo enterprise de revisão, auditoria, conformidade normativa e geração documental.

## Visão geral

```
Upload (PDF/DOCX/XLSX/DWG/DXF/IFC/PNG/JPG/ZIP)
        ↓
IngestionPipeline (disciplina, metadados)
        ↓
┌───────┴───────┬───────────┬────────────┐
│ OCR Pipeline  │ BIM (IFC) │ CAD (DXF)  │
│ PyMuPDF/      │ IFCOpen   │ ezdxf      │
│ pdfplumber    │ Shell     │            │
└───────┬───────┴───────────┴────────────┘
        ↓
VisionRouter (qwen2.5-vl) — Módulo 0
        ↓
Digital Twin (project_digital_twin)
        ↓
ProjectReviewAgent (qwen3:14b / gemma3:12b)
        ↓
RAG Normativo (FAISS híbrido + rerank)
        ↓
NC Engine + Scoring + Compatibilização
        ↓
Relatórios DOCX (revisão, NC, parecer, memorial, TDR)
```

## Pacotes

| Caminho | Responsabilidade |
|---------|------------------|
| `backend/core/project_review/` | Domínio: ingestão, agente, scoring, relatórios |
| `backend/app/routes/project_review.py` | API REST `/projects/{id}/review/*` |
| `backend/app/services/project_review_service.py` | Orquestração e persistência |
| `frontend/app/projects/[id]/review/` | Dashboard executivo por projeto |

## Tabelas PostgreSQL

- `project_digital_twin` — representação unificada (Módulo A)
- `project_reviews` — ciclos de revisão + scores (Módulos G, L, S)
- `project_nonconformities` — NCs (Módulo H)
- `project_document_extractions` — JSON por arquivo (Módulos B–E, 0)

## API principal

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/projects/{id}/review/start` | Pipeline completo de revisão |
| GET | `/projects/{id}/review` | Lista revisões |
| GET | `/projects/{id}/review/dashboard` | KPIs e scores |
| GET | `/projects/{id}/digital-twin` | Último digital twin |
| GET | `/projects/{id}/ncs` | Não conformidades |
| GET | `/projects/{id}/review/compare?v1=&v2=` | Comparação V1/V2 |
| GET | `/projects/{id}/review/{rid}/export/{type}` | DOCX (review, nc, parecer, tdr, memorial:{disc}) |

## Workflow (Módulo S)

`recebido` → `em_processamento` → `analisado` | `com_pendencias` → `aguardando_correcao` → `revisado` → `aprovado`

## Dependências opcionais

| Pacote | Uso |
|--------|-----|
| pymupdf | PDF → imagem para visão |
| pdfplumber / camelot | Tabelas PDF |
| paddleocr | OCR em PNG/JPG |
| ifcopenshell | Inventário BIM |
| ezdxf | Análise CAD |

## Próximas fases

1. Workers/queues assíncronos (Celery/Redis) para projetos grandes
2. Export PDF via LibreOffice headless
3. Assinatura digital e numeração corporativa
4. Dashboard global `/review` multi-projeto
5. Integração orçamento salvo (`budget_documents`) na análise J
