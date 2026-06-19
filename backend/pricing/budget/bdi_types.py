from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ObraBdiRates:
    code: str
    label: str
    rate_com_desoneracao: float
    rate_sem_desoneracao: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "label": self.label,
            "rate_com_desoneracao": self.rate_com_desoneracao,
            "rate_sem_desoneracao": self.rate_sem_desoneracao,
        }


# Tabela PPD SEMINF — BDI por tipo de obra (ComD / SemD)
OBRA_BDI_TABLE: dict[str, ObraBdiRates] = {
    "ED": ObraBdiRates("ED", "Edificação", 0.2572, 0.2212),
    "RF": ObraBdiRates("RF", "Rodovias e Ferrovias", 0.2426, 0.2097),
    "FIE": ObraBdiRates("FIE", "Fornecimento e Instalação de Equipamentos", 0.1738, 0.1402),
    "IE": ObraBdiRates("IE", "Instalação Elétrica", 0.2889, 0.2520),
    "OPMF": ObraBdiRates("OPMF", "Obra Portuária, Marítima e Fluvial", 0.3123, 0.2520),
    "SEE": ObraBdiRates("SEE", "Serviços Especializados em Engenharia", 0.0, 0.1772),
    "AG": ObraBdiRates("AG", "Construção de Água e Esgoto", 0.2788, 0.2418),
}

DEFAULT_OBRA_TYPE = "RF"

# Alias comuns (inclui EI citado pelo usuário → IE)
OBRA_TYPE_ALIASES: dict[str, str] = {
    "EI": "IE",
    "ELETRICA": "IE",
    "ELÉTRICA": "IE",
    "RODOVIA": "RF",
    "FERROVIA": "RF",
    "PONTE": "RF",
    "PONTES": "RF",
    "EDIFICACAO": "ED",
    "EDIFICAÇÃO": "ED",
    "EQUIPAMENTO": "FIE",
    "EQUIPAMENTOS": "FIE",
    "PORTUARIA": "OPMF",
    "MARITIMA": "OPMF",
    "FLUVIAL": "OPMF",
    "ESGOTO": "AG",
    "SANEAMENTO": "AG",
    "AGUA": "AG",
    "ÁGUA": "AG",
}


def normalize_obra_type(code: str | None) -> str:
    if not code:
        return DEFAULT_OBRA_TYPE
    upper = str(code).strip().upper()
    if upper in OBRA_BDI_TABLE:
        return upper
    return OBRA_TYPE_ALIASES.get(upper, DEFAULT_OBRA_TYPE)


def get_obra_bdi(code: str | None) -> ObraBdiRates:
    return OBRA_BDI_TABLE[normalize_obra_type(code)]


def list_obra_bdi_types() -> list[dict[str, Any]]:
    return [r.to_dict() for r in OBRA_BDI_TABLE.values()]


def detect_obra_type(
    text: str = "",
    orcamento: str = "",
    objeto: str = "",
    scope: str = "",
) -> str:
    """Detecta tipo de obra para BDI a partir de texto (determinístico)."""
    blob = " ".join([text, orcamento, objeto, scope]).lower()

    rules: list[tuple[tuple[str, ...], str]] = [
        (("instalação elétrica", "instalacao eletrica", "instalação elétrica", "eletroduto", "quadro elétrico"), "IE"),
        (("portuária", "portuaria", "marítima", "maritima", "fluvial", "cais", "embarcadouro"), "OPMF"),
        (("água e esgoto", "agua e esgoto", "saneamento", "esgotamento", "eta", "ete"), "AG"),
        (("equipamento", "fornecimento e instalação"), "FIE"),
        (("administração técnica", "administracao tecnica", "serviços especializados", "servicos especializados"), "SEE"),
        (("edificação", "edificacao", "predio", "prédio", "residencial", "comercial"), "ED"),
        (("ponte", "pontes", "viaduto", "rodovia", "ferrovia", "trecho", "pavimentação", "pavimentacao"), "RF"),
    ]
    for keywords, code in rules:
        if any(k in blob for k in keywords):
            return code
    return DEFAULT_OBRA_TYPE
