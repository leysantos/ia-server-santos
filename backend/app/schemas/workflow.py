"""Schemas Pydantic — Workflow Projetos."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class WorkflowProjectUpdateRequest(BaseModel):
    codigo: Optional[str] = None
    cliente: Optional[str] = None
    responsavel: Optional[str] = None
    disciplina: Optional[str] = None
    status: Optional[str] = None
    empresa_id: Optional[str] = None


class CompanyCreateRequest(BaseModel):
    nome: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=80)


class WorkflowDashboardResponse(BaseModel):
    projetos_ativos: int
    arquivos_processados: int
    pranchas_geradas: int
    revisoes_registradas: int
    publicacoes_recentes: int
    eventos_recentes: list[dict[str, Any]]
