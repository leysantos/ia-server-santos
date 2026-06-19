"""
Constantes e limites do Agent Generation Loop v1 (controlled).
"""

from __future__ import annotations

# Domínios permitidos (chaves normalizadas sem acento)
ONLY_ALLOWED_DOMAINS: tuple[str, ...] = (
    "ARQUITETURA",
    "ESTRUTURAL",
    "HIDROSSANITARIO",
    "GEOTECNIA",
    "DRENAGEM",
    "ELETRICA",
    "INCENDIO",
    "ORCAMENTO",
    "TRANSPORTES",
    "INFRAESTRUTURA",
)

# Mapeamento chave normalizada → disciplina do sistema (com acentos quando aplicável)
DOMAIN_TO_DISCIPLINE: dict[str, str] = {
    "ARQUITETURA": "ARQUITETURA",
    "ESTRUTURAL": "ESTRUTURAL",
    "HIDROSSANITARIO": "HIDROSSANITÁRIO",
    "GEOTECNIA": "GEOTECNIA",
    "DRENAGEM": "DRENAGEM",
    "ELETRICA": "ELÉTRICA",
    "INCENDIO": "INCÊNDIO",
    "ORCAMENTO": "ORÇAMENTO",
    "TRANSPORTES": "TRANSPORTES",
    "INFRAESTRUTURA": "INFRAESTRUTURA",
}

DISCIPLINE_TO_DOMAIN: dict[str, str] = {v: k for k, v in DOMAIN_TO_DISCIPLINE.items()}

MAX_AGENTS_TOTAL = 25
MAX_NEW_AGENTS_PER_WEEK = 2
IMPROVEMENT_THRESHOLD = 0.08
RISK_SCORE_THRESHOLD = 0.60
SIMULATION_RUNS_MIN = 20
SIMULATION_RUNS_MAX = 50
SIMULATION_RUNS_DEFAULT = 30

PROPOSAL_STATUS_PROPOSED = "proposed"
PROPOSAL_STATUS_SIMULATING = "simulating"
PROPOSAL_STATUS_EVALUATED = "evaluated"
PROPOSAL_STATUS_APPROVED = "approved_for_deployment"
PROPOSAL_STATUS_REJECTED = "rejected"

CANDIDATE_STATUS_DRAFT = "draft"
CANDIDATE_STATUS_SANDBOX = "sandbox"
CANDIDATE_STATUS_PROMOTED = "promoted"
CANDIDATE_STATUS_REJECTED = "rejected"


def normalize_domain(value: str) -> str:
    """Normaliza nome de domínio para chave ONLY_ALLOWED_DOMAINS."""
    import unicodedata

    text = unicodedata.normalize("NFKD", (value or "").upper())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.replace(" ", "_")


def is_allowed_domain(domain_or_discipline: str) -> bool:
    key = normalize_domain(domain_or_discipline)
    if key in ONLY_ALLOWED_DOMAINS:
        return True
    disc = domain_or_discipline.upper()
    return DISCIPLINE_TO_DOMAIN.get(disc) in ONLY_ALLOWED_DOMAINS


def resolve_discipline(domain_or_discipline: str) -> str:
    key = normalize_domain(domain_or_discipline)
    if key in DOMAIN_TO_DISCIPLINE:
        return DOMAIN_TO_DISCIPLINE[key]
    upper = domain_or_discipline.upper()
    if upper in DISCIPLINE_TO_DOMAIN:
        return upper
    return upper
