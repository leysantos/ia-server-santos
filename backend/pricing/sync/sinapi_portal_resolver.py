"""Resolve ZIP SINAPI pelo portal downloads.aspx (API SharePoint da Caixa)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests

from .sinapi_links import (
    SINAPI_NATIONAL_BASE,
    SINAPI_NATIONAL_CATEGORIA,
    SINAPI_UF_CATEGORIA,
    sinapi_national_downloads_url,
)

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
_CAIXA_BASE = "https://www.caixa.gov.br"
_TITLE_RE = re.compile(
    r"^SINAPI-(?P<year>\d{4})-(?P<month>\d{2})-formato-xlsx(?:_Retificacao(?P<ret>\d+))?$",
    re.I,
)
_CATEGORIA_HASH_RE = re.compile(r"#categoria_(\d+)", re.I)


@dataclass(frozen=True)
class SinapiPortalFile:
    title: str
    url: str
    modified: str
    retificacao: int = 0

    @property
    def period(self) -> str:
        m = _TITLE_RE.match(self.title)
        if not m:
            return ""
        return f"{m.group('year')}-{m.group('month')}"


def parse_categoria_id(page_url: str | None) -> int | None:
    """Extrai ID da categoria do hash downloads.aspx#categoria_888."""
    if not page_url:
        return None
    m = _CATEGORIA_HASH_RE.search(page_url)
    if m:
        return int(m.group(1))
    return None


def categoria_for_sinapi(*, uf: str = "SP", page_url: str | None = None, national: bool = True) -> int:
    if national:
        return parse_categoria_id(page_url) or SINAPI_NATIONAL_CATEGORIA
    if page_url:
        parsed = parse_categoria_id(page_url)
        if parsed:
            return parsed
    return SINAPI_UF_CATEGORIA.get(uf.upper(), SINAPI_NATIONAL_CATEGORIA)


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": _USER_AGENT,
            "Accept": "application/json;odata=verbose",
        }
    )
    try:
        s.get(f"{_CAIXA_BASE}/site/Paginas/downloads.aspx", timeout=45)
    except Exception as exc:
        logger.debug("Warmup downloads.aspx: %s", exc)
    return s


def fetch_categoria_items(categoria_id: int, *, top: int = 500) -> list[dict[str, Any]]:
    """Lista arquivos publicados na categoria (ex.: 888 = SINAPI nacional mensal)."""
    url = (
        f"{_CAIXA_BASE}/_api/web/lists/getbytitle('Downloads')/Items"
        f"?$select=Title,EncodedAbsUrl,Modified,FileLeafRef"
        f"&$filter=CategoriaId eq {int(categoria_id)}"
        f"&$top={top}&$orderby=Modified desc"
    )
    response = _session().get(url, timeout=60)
    response.raise_for_status()
    payload = response.json()
    return list(payload.get("d", {}).get("results") or [])


def _parse_item(raw: dict[str, Any]) -> SinapiPortalFile | None:
    title = str(raw.get("Title") or "").strip()
    if not _TITLE_RE.match(title):
        return None
    url = str(raw.get("EncodedAbsUrl") or "").replace("http:", "https:")
    if not url:
        return None
    m = _TITLE_RE.match(title)
    ret = int(m.group("ret") or 0) if m else 0
    return SinapiPortalFile(
        title=title,
        url=url,
        modified=str(raw.get("Modified") or ""),
        retificacao=ret,
    )


def pick_best_for_period(
    items: list[SinapiPortalFile],
    *,
    year: int,
    month: int,
) -> SinapiPortalFile | None:
    target = f"{year:04d}-{month:02d}"
    matches = [it for it in items if it.period == target]
    if not matches:
        return None
    return sorted(matches, key=lambda it: (it.retificacao, it.modified), reverse=True)[0]


def resolve_from_portal(
    year: int,
    month: int,
    *,
    categoria_id: int | None = None,
    page_url: str | None = None,
    uf: str = "SP",
    national: bool = True,
) -> SinapiPortalFile:
    """Busca no portal Caixa o ZIP XLSX do período (inclui retificações)."""
    cat = categoria_id or categoria_for_sinapi(uf=uf, page_url=page_url, national=national)
    raw_items = fetch_categoria_items(cat)
    parsed = [p for p in (_parse_item(r) for r in raw_items) if p]
    chosen = pick_best_for_period(parsed, year=year, month=month)
    if not chosen:
        page = page_url or sinapi_national_downloads_url()
        raise FileNotFoundError(
            f"SINAPI {year:04d}-{month:02d} não encontrado na categoria {cat} ({page})"
        )
    logger.info(
        "Portal SINAPI: %s -> %s (retificação %s)",
        chosen.period,
        chosen.title,
        chosen.retificacao or "—",
    )
    return chosen


def probe_direct_national_urls(year: int, month: int, *, max_ret: int = 5) -> str:
    """Fallback: tenta URL direta com sufixo _RetificacaoNN."""
    period = f"{year:04d}-{month:02d}"
    candidates = [f"{SINAPI_NATIONAL_BASE}/SINAPI-{period}-formato-xlsx.zip"]
    for n in range(1, max_ret + 1):
        candidates.append(
            f"{SINAPI_NATIONAL_BASE}/SINAPI-{period}-formato-xlsx_Retificacao{n:02d}.zip"
        )

    s = _session()
    s.headers["Accept"] = "application/zip,application/octet-stream,*/*"
    for url in candidates:
        try:
            r = s.get(url, timeout=90, allow_redirects=True)
            if r.status_code != 200:
                continue
            head = r.content[:32].lstrip()
            if head.startswith(b"PK"):
                return url
        except Exception as exc:
            logger.debug("Probe %s: %s", url, exc)
    raise FileNotFoundError(f"ZIP direto não encontrado para {period}")


def resolve_download_url(
    year: int,
    month: int,
    *,
    page_url: str | None = None,
    uf: str = "SP",
    national: bool = True,
) -> tuple[str, str]:
    """
    Retorna (url_zip, titulo_publicacao).
    Prioriza API do portal; fallback para URLs diretas com retificação.
    """
    try:
        found = resolve_from_portal(
            year,
            month,
            page_url=page_url,
            uf=uf,
            national=national,
        )
        return found.url, found.title
    except Exception as exc:
        logger.warning("Resolver portal SINAPI: %s — tentando URLs diretas", exc)
    if national:
        url = probe_direct_national_urls(year, month)
        return url, urlparse(url).path.rsplit("/", 1)[-1].replace(".zip", "")
    raise FileNotFoundError(f"SINAPI {year:04d}-{month:02d} indisponível")
