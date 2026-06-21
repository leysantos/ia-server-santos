"""Padrões de nomenclatura e estrutura de entrega — escritórios de engenharia."""

from __future__ import annotations

# Código de disciplina (carimbo / nome de arquivo)
DISCIPLINE_CODES: dict[str, str] = {
    "arquitetura": "ARQ",
    "estrutural": "EST",
    "eletrica": "ELE",
    "hidraulica": "HID",
    "incendio": "PCI",
    "geotecnia": "GEO",
    "topografia": "TOP",
    "drenagem": "DRE",
    "telecom": "TEL",
    "geral": "GER",
}

# Tipo de desenho → segmento no nome
DRAWING_TYPE_LABELS: dict[str, str] = {
    "planta_baixa": "PLANTA",
    "planta": "PLANTA",
    "corte": "CORTE",
    "fachada": "FACHADA",
    "detalhe": "DETALHE",
    "fundacao": "FUNDACAO",
    "forma": "FORMA",
    "armadura": "ARMADURA",
    "instalacao": "INSTALACAO",
    "pci": "PCI",
    "desenho_tecnico": "DESENHO",
    "prancha_arquitetura": "PLANTA",
    "prancha_pci": "PCI",
    "prancha_estrutural": "ESTRUTURAL",
    "prancha_eletrica": "ELETRICA",
    "prancha_hidraulica": "HIDRAULICA",
    "prancha_tecnica": "DESENHO",
}

# Documento complementar → pasta no pacote GRD
DOCUMENT_FOLDERS: dict[str, str] = {
    "memorial": "02_MEMORIAIS",
    "memorial_descritivo": "02_MEMORIAIS",
    "memoria_calculo": "03_MEMORIAS_DE_CALCULO",
    "parecer": "04_CORRESPONDENCIAS",
    "carta": "04_CORRESPONDENCIAS",
    "termo": "04_CORRESPONDENCIAS",
    "documento_tecnico": "05_RELATORIOS",
    "pdf_generico": "05_RELATORIOS",
}

SHEET_FOLDER = "01_PRANCHAS"
NATIVES_FOLDER = "06_NATIVOS"

# Formatos de prancha suportados
SHEET_FORMATS = ("A4", "A3", "A2", "A1", "A0")
