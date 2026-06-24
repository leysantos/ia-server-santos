"""Constantes do Project Review Engine."""

from __future__ import annotations

from enum import StrEnum


class ReviewStatus(StrEnum):
    RECEBIDO = "recebido"
    EM_PROCESSAMENTO = "em_processamento"
    ANALISADO = "analisado"
    COM_PENDENCIAS = "com_pendencias"
    AGUARDANDO_CORRECAO = "aguardando_correcao"
    REVISADO = "revisado"
    APROVADO = "aprovado"


class Discipline(StrEnum):
    ARQUITETURA = "arquitetura"
    ESTRUTURA = "estrutura"
    HIDRAULICA = "hidraulica"
    ELETRICA = "eletrica"
    PCI = "pci"
    URBANISMO = "urbanismo"
    INFRAESTRUTURA = "infraestrutura"
    ORCAMENTO = "orcamento"
    DOCUMENTACAO = "documentacao"
    DESCONHECIDA = "desconhecida"


class NCCategory(StrEnum):
    DOCUMENTAL = "documental"
    ESTRUTURAL = "estrutural"
    ARQUITETONICA = "arquitetonica"
    HIDRAULICA = "hidraulica"
    ELETRICA = "eletrica"
    PCI = "pci"
    ORCAMENTARIA = "orcamentaria"


class NCCriticidade(StrEnum):
    BAIXA = "baixa"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"


class NCStatus(StrEnum):
    ABERTA = "aberta"
    EM_CORRECAO = "em_correcao"
    CORRIGIDA = "corrigida"
    ACEITA = "aceita"
    REJEITADA = "rejeitada"


TWIN_DISCIPLINE_KEYS: tuple[str, ...] = (
    "arquitetura",
    "estrutura",
    "hidraulica",
    "eletrica",
    "pci",
    "orcamento",
    "documentacao",
)

VISION_MODEL_PRIMARY = "gemma4:latest"
VISION_MODEL_FALLBACKS: tuple[str, ...] = ("gemma4:latest", "gemma3:12b", "gemma3")
TECHNICAL_MODEL = "qwen3:14b"
TECHNICAL_MODEL_FALLBACK = "gemma4:latest"

NORMATIVE_BASES: tuple[str, ...] = (
    "NBR",
    "DNIT",
    "CBMAM",
    "SINAPI",
    "SICRO",
    "SEMINF",
    "SEINFRA",
    "ORSE",
)

REVIEW_UPLOAD_SUFFIXES: frozenset[str] = frozenset(
    {
        ".pdf",
        ".docx",
        ".xlsx",
        ".xls",
        ".dwg",
        ".dxf",
        ".ifc",
        ".png",
        ".jpg",
        ".jpeg",
        ".zip",
        ".txt",
        ".md",
        ".csv",
    }
)
