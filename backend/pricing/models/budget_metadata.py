from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pricing.budget.bdi_types import DEFAULT_OBRA_TYPE, get_obra_bdi, normalize_obra_type


@dataclass
class BdiConfig:
    """Configuração BDI — taxas por tipo de obra (PPD SEMINF)."""

    obra_type: str = DEFAULT_OBRA_TYPE
    label: str = "BDI1"
    rate_com_desoneracao: float = 0.2426
    rate_sem_desoneracao: float = 0.2097
    obra_label: str = "Rodovias e Ferrovias"

    @classmethod
    def from_obra_type(cls, obra_type: str | None, label: str = "BDI1") -> BdiConfig:
        code = normalize_obra_type(obra_type)
        rates = get_obra_bdi(code)
        return cls(
            obra_type=code,
            label=label,
            rate_com_desoneracao=rates.rate_com_desoneracao,
            rate_sem_desoneracao=rates.rate_sem_desoneracao,
            obra_label=rates.label,
        )

    def price_with_bdi(self, unit_cost: float, with_relief: bool = True) -> float:
        rate = self.rate_com_desoneracao if with_relief else self.rate_sem_desoneracao
        return round(unit_cost * (1 + rate), 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "obra_type": self.obra_type,
            "obra_label": self.obra_label,
            "label": self.label,
            "rate_com_desoneracao": self.rate_com_desoneracao,
            "rate_sem_desoneracao": self.rate_sem_desoneracao,
        }


@dataclass
class BudgetProjectMetadata:
    """Cabeçalho de projeto — espelha MCQ/PLANILHA PPD."""

    projeto: str = ""
    objeto: str = ""
    local: str = ""
    orcamento: str = ""
    base_preco: str = "SINAPI"
    orgao: str = ""
    empresa: str = ""
    responsavel_tecnico: str = ""
    processo: str = ""
    data_ref: str = ""
    obra_type: str = DEFAULT_OBRA_TYPE
    bdi: BdiConfig = field(default_factory=lambda: BdiConfig.from_obra_type(DEFAULT_OBRA_TYPE))
    template: str = "PPD_MC_OR"

    def to_dict(self) -> dict[str, Any]:
        return {
            "projeto": self.projeto,
            "objeto": self.objeto,
            "local": self.local,
            "orcamento": self.orcamento,
            "base_preco": self.base_preco,
            "orgao": self.orgao,
            "empresa": self.empresa,
            "responsavel_tecnico": self.responsavel_tecnico,
            "processo": self.processo,
            "data_ref": self.data_ref,
            "obra_type": self.obra_type,
            "bdi": self.bdi.to_dict(),
            "template": self.template,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> BudgetProjectMetadata:
        if not data:
            return cls()
        bdi_data = data.get("bdi") or {}
        obra_type = normalize_obra_type(
            data.get("obra_type") or bdi_data.get("obra_type")
        )
        bdi = BdiConfig.from_obra_type(obra_type, label=str(bdi_data.get("label") or "BDI1"))
        if bdi_data.get("rate_com_desoneracao"):
            bdi.rate_com_desoneracao = float(bdi_data["rate_com_desoneracao"])
        if bdi_data.get("rate_sem_desoneracao"):
            bdi.rate_sem_desoneracao = float(bdi_data["rate_sem_desoneracao"])
        return cls(
            projeto=str(data.get("projeto") or ""),
            objeto=str(data.get("objeto") or ""),
            local=str(data.get("local") or ""),
            orcamento=str(data.get("orcamento") or ""),
            base_preco=str(data.get("base_preco") or "SINAPI"),
            orgao=str(data.get("orgao") or ""),
            empresa=str(data.get("empresa") or data.get("orgao") or ""),
            responsavel_tecnico=str(data.get("responsavel_tecnico") or ""),
            processo=str(data.get("processo") or ""),
            data_ref=str(data.get("data_ref") or ""),
            obra_type=obra_type,
            bdi=bdi,
            template=str(data.get("template") or "PPD_MC_OR"),
        )

    def set_obra_type(self, obra_type: str) -> None:
        self.obra_type = normalize_obra_type(obra_type)
        self.bdi = BdiConfig.from_obra_type(self.obra_type, label=self.bdi.label)
