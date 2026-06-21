"""Limites da importação em lote NBR/NR."""

# Starlette limita multipart a 1000 arquivos por padrão — rota usa este teto.
NORM_BULK_MAX_FILES = 5000

# Frontend envia em lotes menores (703 MB+ num único POST estoura timeout/memória).
NORM_BULK_UPLOAD_CHUNK = 350
