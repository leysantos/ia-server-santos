"""Perfil da empresa (configuração do sistema) — dados para PDFs e exportações."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from config.settings import DATA_DIR
from core.workflow.storage.client import get_workflow_storage

PROFILE_PATH = DATA_DIR / "system" / "company_profile.json"
LOGO_KEY = "system/company/logo"
BRASAO_KEY = "system/company/brasao"


@dataclass
class CompanyProfile:
    razao_social: str = ""
    nome_fantasia: str = ""
    cnpj: str = ""
    endereco: str = ""
    numero: str = ""
    complemento: str = ""
    bairro: str = ""
    cidade: str = ""
    uf: str = ""
    cep: str = ""
    telefone: str = ""
    email: str = ""
    site: str = ""
    responsavel_tecnico: str = ""
    rt_profissao: str = ""
    rt_crea: str = ""
    rt_email: str = ""
    rt_telefone: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> CompanyProfile:
        if not data:
            return cls()
        field_names = {f.name for f in fields(cls)}
        return cls(**{k: str(v or "") for k, v in data.items() if k in field_names})

    def display_name(self) -> str:
        return self.nome_fantasia or self.razao_social

    def endereco_linha(self) -> str:
        rua = self.endereco.strip()
        if self.numero:
            rua = f"{rua}, {self.numero}" if rua else self.numero
        if self.complemento:
            rua = f"{rua} — {self.complemento}" if rua else self.complemento
        if self.bairro:
            rua = f"{rua} — {self.bairro}" if rua else self.bairro
        cidade_uf = ""
        if self.cidade and self.uf:
            cidade_uf = f"{self.cidade}/{self.uf}"
        elif self.cidade:
            cidade_uf = self.cidade
        parts = [p for p in (rua, cidade_uf, self.cep) if p]
        return " · ".join(parts)

    def contato_linha(self) -> str:
        parts = [p for p in (self.telefone, self.email, self.site) if p]
        return " · ".join(parts)

    def responsavel_linha(self) -> str:
        nome = self.responsavel_tecnico.strip()
        prof = self.rt_profissao.strip()
        crea = self.rt_crea.strip()
        chunks: list[str] = []
        if nome:
            chunks.append(nome)
        if prof:
            chunks.append(prof)
        if crea:
            chunks.append(f"CREA: {crea}")
        return " — ".join(chunks)

    def rt_contato_linha(self) -> str:
        parts = [p for p in (self.rt_telefone, self.rt_email) if p]
        return " · ".join(parts)


def _ensure_profile_dir() -> None:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_company_profile() -> CompanyProfile:
    _ensure_profile_dir()
    if not PROFILE_PATH.exists():
        return CompanyProfile()
    try:
        raw = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        return CompanyProfile.from_dict(raw if isinstance(raw, dict) else {})
    except (json.JSONDecodeError, OSError):
        return CompanyProfile()


def save_company_profile(profile: CompanyProfile) -> CompanyProfile:
    _ensure_profile_dir()
    PROFILE_PATH.write_text(
        json.dumps(profile.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return profile


def update_company_profile(data: dict[str, Any]) -> CompanyProfile:
    current = get_company_profile()
    merged = CompanyProfile.from_dict({**current.to_dict(), **data})
    return save_company_profile(merged)


def save_company_logo(content: bytes, content_type: str = "image/png") -> str:
    storage = get_workflow_storage()
    storage.put_bytes(LOGO_KEY, content, content_type=content_type)
    return LOGO_KEY


def save_company_brasao(content: bytes, content_type: str = "image/png") -> str:
    storage = get_workflow_storage()
    storage.put_bytes(BRASAO_KEY, content, content_type=content_type)
    return BRASAO_KEY


def load_company_logo() -> bytes | None:
    storage = get_workflow_storage()
    if not storage.exists(LOGO_KEY):
        return None
    return storage.get_bytes(LOGO_KEY)


def load_company_brasao() -> bytes | None:
    storage = get_workflow_storage()
    if not storage.exists(BRASAO_KEY):
        return None
    return storage.get_bytes(BRASAO_KEY)


def company_profile_status() -> dict[str, Any]:
    profile = get_company_profile()
    return {
        **profile.to_dict(),
        "has_logo": load_company_logo() is not None,
        "has_brasao": load_company_brasao() is not None,
    }
