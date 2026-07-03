from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pricing.budget.bdi_edital_profiles import (
    BdiEditalProfile,
    BdiTcuComponents,
    get_bdi_edital_profile,
    seminf_profile_for_obra,
)
from pricing.budget.bdi_types import DEFAULT_OBRA_TYPE, get_obra_bdi, normalize_obra_type


@dataclass
class BdiConfig:
    """Configuração BDI — SEMINF, edital TCU ou customizado."""

    obra_type: str = DEFAULT_OBRA_TYPE
    label: str = "BDI1"
    rate_com_desoneracao: float = 0.2426
    rate_sem_desoneracao: float = 0.2097
    obra_label: str = "Rodovias e Ferrovias"
    source: str = "seminf"  # seminf | edital | custom
    profile_id: str | None = "seminf_table"
    components_comd: BdiTcuComponents = field(default_factory=BdiTcuComponents)
    components_semd: BdiTcuComponents = field(default_factory=BdiTcuComponents)

    def sync_rates(self) -> None:
        if self.source == "seminf":
            rates = get_obra_bdi(self.obra_type)
            self.rate_com_desoneracao = rates.rate_com_desoneracao
            self.rate_sem_desoneracao = rates.rate_sem_desoneracao
            self.obra_label = rates.label
            return
        try:
            self.rate_com_desoneracao = self.components_comd.compute_rate()
            self.rate_sem_desoneracao = self.components_semd.compute_rate()
        except ValueError:
            pass
        profile = get_bdi_edital_profile(self.profile_id or "") if self.profile_id else None
        if profile:
            if profile.max_rate_comd is not None:
                self.rate_com_desoneracao = min(self.rate_com_desoneracao, profile.max_rate_comd)
            if profile.max_rate_semd is not None:
                self.rate_sem_desoneracao = min(self.rate_sem_desoneracao, profile.max_rate_semd)

    @classmethod
    def from_obra_type(cls, obra_type: str | None, label: str = "BDI1") -> BdiConfig:
        code = normalize_obra_type(obra_type)
        cfg = cls(
            obra_type=code,
            label=label,
            source="seminf",
            profile_id="seminf_table",
        )
        cfg.sync_rates()
        return cfg

    @classmethod
    def from_profile(cls, profile: BdiEditalProfile, obra_type: str | None = None) -> BdiConfig:
        code = normalize_obra_type(obra_type or profile.obra_type)
        cfg = cls(
            obra_type=code,
            label=profile.label,
            source=profile.source,
            profile_id=profile.id,
            components_comd=BdiTcuComponents.from_dict(profile.components_comd.to_dict()),
            components_semd=BdiTcuComponents.from_dict(profile.components_semd.to_dict()),
            obra_label=get_obra_bdi(code).label if profile.source == "seminf" else profile.label,
        )
        if profile.source == "seminf":
            cfg = cls.from_obra_type(code, label=profile.label)
            cfg.profile_id = profile.id
            return cfg
        cfg.sync_rates()
        return cfg

    @classmethod
    def from_profile_id(cls, profile_id: str, obra_type: str | None = None) -> BdiConfig:
        if profile_id == "seminf_table":
            return cls.from_obra_type(obra_type)
        profile = get_bdi_edital_profile(profile_id)
        if not profile:
            raise ValueError(f"Perfil BDI desconhecido: {profile_id}")
        return cls.from_profile(profile, obra_type=obra_type)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BdiConfig:
        obra_type = normalize_obra_type(data.get("obra_type"))
        cfg = cls(
            obra_type=obra_type,
            label=str(data.get("label") or "BDI1"),
            source=str(data.get("source") or "seminf"),
            profile_id=data.get("profile_id"),
            components_comd=BdiTcuComponents.from_dict(data.get("components_comd")),
            components_semd=BdiTcuComponents.from_dict(data.get("components_semd")),
        )
        if data.get("rate_com_desoneracao") is not None:
            cfg.rate_com_desoneracao = float(data["rate_com_desoneracao"])
        if data.get("rate_sem_desoneracao") is not None:
            cfg.rate_sem_desoneracao = float(data["rate_sem_desoneracao"])
        if data.get("obra_label"):
            cfg.obra_label = str(data["obra_label"])
        elif cfg.source == "seminf":
            cfg.sync_rates()
        else:
            cfg.sync_rates()
        return cfg

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
            "source": self.source,
            "profile_id": self.profile_id,
            "components_comd": self.components_comd.to_dict(),
            "components_semd": self.components_semd.to_dict(),
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
    price_bases: list[dict[str, Any]] = field(default_factory=list)
    commercial_margin_pct: float = 0.0
    commercial_client: str = ""

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
            "price_bases": list(self.price_bases),
            "commercial_margin_pct": self.commercial_margin_pct,
            "commercial_client": self.commercial_client,
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
        if bdi_data.get("source"):
            bdi.source = str(bdi_data["source"])
        if bdi_data.get("profile_id"):
            bdi.profile_id = str(bdi_data["profile_id"])
        if bdi_data.get("components_comd"):
            bdi.components_comd = BdiTcuComponents.from_dict(bdi_data["components_comd"])
        if bdi_data.get("components_semd"):
            bdi.components_semd = BdiTcuComponents.from_dict(bdi_data["components_semd"])
        if bdi_data.get("rate_com_desoneracao"):
            bdi.rate_com_desoneracao = float(bdi_data["rate_com_desoneracao"])
        elif bdi.source != "seminf":
            bdi.sync_rates()
        if bdi_data.get("rate_sem_desoneracao"):
            bdi.rate_sem_desoneracao = float(bdi_data["rate_sem_desoneracao"])
        elif bdi.source != "seminf" and "rate_sem_desoneracao" not in bdi_data:
            bdi.sync_rates()
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
            price_bases=list(data.get("price_bases") or []),
            commercial_margin_pct=float(data.get("commercial_margin_pct") or 0),
            commercial_client=str(data.get("commercial_client") or ""),
        )

    def set_obra_type(self, obra_type: str) -> None:
        self.obra_type = normalize_obra_type(obra_type)
        self.bdi = BdiConfig.from_obra_type(self.obra_type, label=self.bdi.label)
        self.bdi.profile_id = "seminf_table"
        self.bdi.source = "seminf"

    def apply_bdi_config(self, config: BdiConfig) -> None:
        self.bdi = config
        self.obra_type = config.obra_type
