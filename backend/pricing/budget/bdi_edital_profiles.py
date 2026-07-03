"""Perfis BDI por edital — decomposição TCU (AC, G, R, DF, L, T)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pricing.budget.bdi_types import get_obra_bdi, normalize_obra_type


@dataclass(frozen=True)
class BdiTcuComponents:
    """Componentes percentuais decimais (0.05 = 5%)."""

    administracao_central: float = 0.0
    garantias_seguros: float = 0.0
    riscos: float = 0.0
    despesas_financeiras: float = 0.0
    lucro: float = 0.0
    tributos: float = 0.0

    def validate(self) -> None:
        margin = self.lucro + self.tributos
        if margin >= 0.99:
            raise ValueError("Lucro + tributos deve ser inferior a 99%")

    def compute_rate(self) -> float:
        self.validate()
        numerator = (
            (1 + self.administracao_central)
            * (1 + self.garantias_seguros)
            * (1 + self.riscos)
            * (1 + self.despesas_financeiras)
        )
        denominator = 1 - (self.lucro + self.tributos)
        return round(numerator / denominator - 1, 6)

    def to_dict(self) -> dict[str, float]:
        return {
            "administracao_central": self.administracao_central,
            "garantias_seguros": self.garantias_seguros,
            "riscos": self.riscos,
            "despesas_financeiras": self.despesas_financeiras,
            "lucro": self.lucro,
            "tributos": self.tributos,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> BdiTcuComponents:
        if not data:
            return cls()
        return cls(
            administracao_central=float(data.get("administracao_central") or 0),
            garantias_seguros=float(data.get("garantias_seguros") or 0),
            riscos=float(data.get("riscos") or 0),
            despesas_financeiras=float(data.get("despesas_financeiras") or 0),
            lucro=float(data.get("lucro") or 0),
            tributos=float(data.get("tributos") or 0),
        )


@dataclass(frozen=True)
class BdiEditalProfile:
    id: str
    label: str
    description: str
    source: str  # seminf | edital | custom
    obra_type: str | None = None
    components_comd: BdiTcuComponents = field(default_factory=BdiTcuComponents)
    components_semd: BdiTcuComponents = field(default_factory=BdiTcuComponents)
    max_rate_comd: float | None = None
    max_rate_semd: float | None = None

    def rates(self) -> tuple[float, float]:
        if self.source == "seminf" and self.obra_type:
            rates = get_obra_bdi(self.obra_type)
            return rates.rate_com_desoneracao, rates.rate_sem_desoneracao
        comd = self.components_comd.compute_rate()
        semd = self.components_semd.compute_rate()
        if self.max_rate_comd is not None:
            comd = min(comd, self.max_rate_comd)
        if self.max_rate_semd is not None:
            semd = min(semd, self.max_rate_semd)
        return comd, semd

    def to_dict(self) -> dict[str, Any]:
        comd, semd = self.rates()
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "source": self.source,
            "obra_type": self.obra_type,
            "components_comd": self.components_comd.to_dict(),
            "components_semd": self.components_semd.to_dict(),
            "rate_com_desoneracao": comd,
            "rate_sem_desoneracao": semd,
            "max_rate_comd": self.max_rate_comd,
            "max_rate_semd": self.max_rate_semd,
        }


# Perfis edital — valores referenciais TCU / licitações (ajustáveis na UI)
_TCUCivil = BdiTcuComponents(
    administracao_central=0.05,
    garantias_seguros=0.005,
    riscos=0.01,
    despesas_financeiras=0.018,
    lucro=0.06,
    tributos=0.0565,
)
_TCUCivilSemd = BdiTcuComponents(
    administracao_central=0.05,
    garantias_seguros=0.005,
    riscos=0.01,
    despesas_financeiras=0.018,
    lucro=0.055,
    tributos=0.048,
)

BDI_EDITAL_PROFILES: dict[str, BdiEditalProfile] = {
    "seminf_table": BdiEditalProfile(
        id="seminf_table",
        label="SEMINF — tabela por tipo de obra",
        description="Taxas fixas PPD SEMINF/SEINFRA (ComD/SemD por tipo RF, ED, IE…).",
        source="seminf",
    ),
    "tcu_obra_civil": BdiEditalProfile(
        id="tcu_obra_civil",
        label="Edital — Obra civil (TCU)",
        description="Decomposição AC+G+R+DF / (1−L−T) — referência licitação obra civil.",
        source="edital",
        components_comd=_TCUCivil,
        components_semd=_TCUCivilSemd,
        max_rate_comd=0.30,
        max_rate_semd=0.28,
    ),
    "tcu_edificacao": BdiEditalProfile(
        id="tcu_edificacao",
        label="Edital — Edificação (TCU)",
        description="Perfil edital edificação com margens típicas de edificações públicas.",
        source="edital",
        components_comd=BdiTcuComponents(0.055, 0.006, 0.012, 0.02, 0.065, 0.058),
        components_semd=BdiTcuComponents(0.055, 0.006, 0.012, 0.02, 0.06, 0.05),
        max_rate_comd=0.32,
        max_rate_semd=0.30,
    ),
    "custom_edital": BdiEditalProfile(
        id="custom_edital",
        label="Edital — personalizado",
        description="Informe componentes ComD/SemD conforme planilha do edital.",
        source="custom",
    ),
}


def list_bdi_edital_profiles() -> list[dict[str, Any]]:
    return [p.to_dict() for p in BDI_EDITAL_PROFILES.values()]


def get_bdi_edital_profile(profile_id: str) -> BdiEditalProfile | None:
    return BDI_EDITAL_PROFILES.get(profile_id)


def seminf_profile_for_obra(obra_type: str | None) -> BdiEditalProfile:
    code = normalize_obra_type(obra_type)
    rates = get_obra_bdi(code)
    return BdiEditalProfile(
        id="seminf_table",
        label=f"SEMINF — {rates.label}",
        description="Tabela SEMINF para o tipo de obra selecionado.",
        source="seminf",
        obra_type=code,
    )
