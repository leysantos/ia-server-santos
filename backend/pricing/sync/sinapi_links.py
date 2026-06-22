"""URLs oficiais SINAPI (Caixa). Evitar default.aspx — redirect loop no WAF."""

from __future__ import annotations

SINAPI_PORTAL = "https://www.caixa.gov.br/sinapi"

SINAPI_DOWNLOADS_BASE = "https://www.caixa.gov.br/site/Paginas/downloads.aspx"

# Relatórios mensais nacionais (formato ZIP/XLSX 2025+) no portal downloads.aspx
SINAPI_NATIONAL_CATEGORIA = 888

SINAPI_SUMARIO_MIRROR = "https://cesarep.github.io/sumario-sinapi/#relatorios-mensais"

# Formato 2025+: ZIP nacional (todas UFs em uma planilha Referência)
SINAPI_NATIONAL_BASE = "https://www.caixa.gov.br/Downloads/sinapi-relatorios-mensais"


def sinapi_national_zip_url(year: int, month: int) -> str:
    return f"{SINAPI_NATIONAL_BASE}/SINAPI-{year}-{month:02d}-formato-xlsx.zip"

# Categoria downloads.aspx por UF (sumário oficial SINAPI).
SINAPI_UF_CATEGORIA: dict[str, int] = {
    "AC": 638,
    "AL": 639,
    "AM": 640,
    "AP": 641,
    "BA": 642,
    "CE": 643,
    "DF": 644,
    "ES": 645,
    "GO": 646,
    "MA": 647,
    "MG": 648,
    "MS": 649,
    "MT": 650,
    "PA": 651,
    "PB": 652,
    "PE": 653,
    "PI": 654,
    "PR": 655,
    "RJ": 656,
    "RN": 657,
    "RO": 658,
    "RR": 659,
    "RS": 660,
    "TO": 661,
    "SC": 662,
    "SE": 663,
    "SP": 664,
}


def sinapi_national_downloads_url() -> str:
    """Página oficial dos ZIPs nacionais (todas UFs) no portal Caixa."""
    return f"{SINAPI_DOWNLOADS_BASE}#categoria_{SINAPI_NATIONAL_CATEGORIA}"


def sinapi_downloads_url(uf: str = "SP") -> str:
    cat = SINAPI_UF_CATEGORIA.get(uf.upper())
    if cat is None:
        return sinapi_national_downloads_url()
    return f"{SINAPI_DOWNLOADS_BASE}#categoria_{cat}"
