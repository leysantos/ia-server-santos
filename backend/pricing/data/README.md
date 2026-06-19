# Bases de preços — Pricing Engine

Coloque arquivos SINAPI, ORSE, TCPO etc. nesta pasta.

## Estrutura suportada

```
data/
├── sinapi.csv              # arquivo único
├── orse.csv
├── sinapi/                 # múltiplos arquivos (mesclados)
│   ├── composicoes_2025-01.csv
│   └── insumos_2025-01.csv
└── orse/
    └── base_orse.xlsx
```

## Colunas aceitas (detecção automática)

- Código: `codigo`, `code`, `cód`
- Descrição: `descricao`, `description`, `servico`
- Unidade: `unidade`, `unit`, `und`
- Preço: `preco`, `price`, `valor`, `custo`

## Variável de ambiente

```bash
export PRICING_DATA_DIR=/caminho/para/bases
```

## Upload via API

```bash
curl -X POST http://localhost:8000/pricing/providers/sinapi/upload \
  -F "file=@sinapi_composicoes.csv"
```
