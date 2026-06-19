"""
Registry central de nomes de agentes — fonte única de verdade.

Padrão: {modulo}_agent (sem acentos, plural quando aplicável)
"""

DISCIPLINE_TO_AGENT: dict[str, str] = {
    "ARQUITETURA": "arquitetura_agent",
    "ESTRUTURAL": "estruturas_agent",
    "HIDROSSANITÁRIO": "hidrossanitario_agent",
    "DRENAGEM": "drenagem_agent",
    "ELÉTRICA": "eletrica_agent",
    "TELECOM": "telecom_agent",
    "INCÊNDIO": "incendio_agent",
    "GEOTECNIA": "geotecnia_agent",
    "TRANSPORTES": "transportes_agent",
    "INFRAESTRUTURA": "infraestrutura_agent",
    "SANEAMENTO": "saneamento_agent",
    "GEOPROCESSAMENTO": "geoprocessamento_agent",
    "TOPOGRAFIA": "topografia_agent",
    "ORÇAMENTO": "orcamento_agent",
    "MEIO_AMBIENTE": "meio_ambiente_agent",
    "GERAL": "geral_agent",
}


def get_agent_name(discipline: str) -> str:
    return DISCIPLINE_TO_AGENT.get(discipline, "geral_agent")
