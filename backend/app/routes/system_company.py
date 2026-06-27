from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from core.system.company_profile import (
    company_profile_status,
    get_company_profile,
    load_company_brasao,
    load_company_logo,
    save_company_brasao,
    save_company_logo,
    update_company_profile,
)
from core.system.export_branding_store import export_branding_status, save_global_export_branding

router = APIRouter(prefix="/system", tags=["System"])


class CompanyProfileUpdateRequest(BaseModel):
    razao_social: str | None = None
    nome_fantasia: str | None = None
    cnpj: str | None = None
    endereco: str | None = None
    numero: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    cidade: str | None = None
    uf: str | None = Field(default=None, max_length=2)
    cep: str | None = None
    telefone: str | None = None
    email: str | None = None
    site: str | None = None
    responsavel_tecnico: str | None = None
    rt_profissao: str | None = None
    rt_crea: str | None = None
    rt_email: str | None = None
    rt_telefone: str | None = None


class ExportBrandingUpdateRequest(BaseModel):
    header_title: str | None = None
    header_line1: str | None = None
    header_line2: str | None = None
    header_line3: str | None = None
    footer_line1: str | None = None
    footer_line2: str | None = None
    show_logo: bool | None = None
    show_brasao: bool | None = None


@router.get("/export-branding")
def get_export_branding_route():
    return export_branding_status()


@router.patch("/export-branding")
def patch_export_branding(body: ExportBrandingUpdateRequest):
    save_global_export_branding(body.model_dump(exclude_unset=True))
    return export_branding_status()


@router.get("/company-profile")
def get_company_profile_route():
    return company_profile_status()


@router.patch("/company-profile")
def patch_company_profile(body: CompanyProfileUpdateRequest):
    profile = update_company_profile(body.model_dump(exclude_unset=True))
    return company_profile_status()


@router.post("/company-profile/logo")
async def upload_company_logo(file: UploadFile = File(...)):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo vazio")
    content_type = file.content_type or "image/png"
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Envie uma imagem (PNG, JPG, etc.)")
    save_company_logo(content, content_type=content_type)
    return company_profile_status()


@router.get("/company-profile/logo")
def get_company_logo():
    logo = load_company_logo()
    if not logo:
        raise HTTPException(status_code=404, detail="Logo não cadastrada")
    return Response(content=logo, media_type="image/png")


@router.post("/company-profile/brasao")
async def upload_company_brasao(file: UploadFile = File(...)):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo vazio")
    content_type = file.content_type or "image/png"
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Envie uma imagem (PNG, JPG, etc.)")
    save_company_brasao(content, content_type=content_type)
    return company_profile_status()


@router.get("/company-profile/brasao")
def get_company_brasao():
    img = load_company_brasao()
    if not img:
        raise HTTPException(status_code=404, detail="Brasão não cadastrado")
    return Response(content=img, media_type="image/png")
