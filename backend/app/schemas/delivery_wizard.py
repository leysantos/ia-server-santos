"""Schemas — Wizard de Entrega (Fase 3)."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class DeliveryPackageCreateRequest(BaseModel):
    titulo: Optional[str] = Field(default=None, max_length=200)


class DeliveryPackageUpdateRequest(BaseModel):
    titulo: Optional[str] = Field(default=None, max_length=200)
    codigo_emissao: Optional[str] = Field(default=None, max_length=20)
    formato_padrao: Optional[str] = Field(default=None, max_length=10)
    orientacao_padrao: Optional[str] = Field(default=None, max_length=20)
    template_id: Optional[str] = None
    stamp_id: Optional[str] = None
    observacoes: Optional[str] = None


class DeliverySelectionRequest(BaseModel):
    file_ids: list[str] = Field(default_factory=list)


class DeliveryItemUpdateRequest(BaseModel):
    selected: Optional[bool] = None
    codigo_aprovado: Optional[str] = Field(default=None, max_length=120)
    formato: Optional[str] = Field(default=None, max_length=10)
    escala: Optional[str] = Field(default=None, max_length=20)
    titulo: Optional[str] = Field(default=None, max_length=300)
    pasta_destino: Optional[str] = Field(default=None, max_length=120)
    folha_numero: Optional[int] = Field(default=None, ge=1, le=999)


class NomenclatureStandardsResponse(BaseModel):
    pattern: str
    discipline_codes: dict[str, str]
    document_folders: dict[str, str]
    sheet_formats: list[str]
