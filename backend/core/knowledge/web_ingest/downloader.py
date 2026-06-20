"""Download seguro de arquivos remotos."""

from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

from core.knowledge.ingestion import INGESTABLE_SUFFIXES
from core.knowledge.web_ingest.security import validate_public_http_url

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = (15, 180)
_MAX_BYTES = 80 * 1024 * 1024  # 80 MB por arquivo

_USER_AGENT = (
    "Mozilla/5.0 (compatible; IAServerSantos/1.0; "
    "+https://github.com/leysantos/ia-server-santos)"
)

_CONTENT_TYPE_SUFFIX: dict[str, str] = {
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "text/plain": ".txt",
    "text/csv": ".csv",
}


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": _USER_AGENT,
            "Accept": "*/*",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }
    )
    return session


def download_file(
    url: str,
    dest_dir: Path | None = None,
    *,
    hint_filename: str | None = None,
    hint_suffix: str | None = None,
    session: requests.Session | None = None,
    post_data: dict[str, str] | None = None,
) -> Path:
    """Baixa arquivo para diretório temporário ou destino informado."""
    safe_url = validate_public_http_url(url)
    dest_dir = dest_dir or Path(tempfile.mkdtemp(prefix="web_ingest_"))
    dest_dir.mkdir(parents=True, exist_ok=True)

    session = session or _session()
    request_fn = session.post if post_data else session.get
    request_kwargs: dict = {"stream": True, "timeout": _DEFAULT_TIMEOUT, "allow_redirects": True}
    if post_data:
        request_kwargs["data"] = post_data

    with request_fn(safe_url, **request_kwargs) as resp:
        resp.raise_for_status()
        filename = _filename_from_response(
            safe_url,
            resp.headers.get("Content-Disposition", ""),
            resp.headers.get("Content-Type", ""),
            hint_filename=hint_filename,
            hint_suffix=hint_suffix,
        )
        suffix = Path(filename).suffix.lower()
        if suffix not in INGESTABLE_SUFFIXES:
            raise ValueError(
                f"Tipo não suportado para ingestão: {suffix or 'desconhecido'} "
                f"(URL: {safe_url[:120]})"
            )

        dest = dest_dir / filename
        total = 0
        with open(dest, "wb") as handle:
            for chunk in resp.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                total += len(chunk)
                if total > _MAX_BYTES:
                    dest.unlink(missing_ok=True)
                    raise ValueError(f"Arquivo excede limite de {_MAX_BYTES // (1024 * 1024)} MB")
                handle.write(chunk)

    if dest.stat().st_size == 0:
        dest.unlink(missing_ok=True)
        raise ValueError("Arquivo baixado está vazio")

    return dest


def fetch_page(url: str, session: requests.Session | None = None) -> tuple[str, requests.Session]:
    """Baixa HTML da página e devolve a sessão (cookies) para downloads POST."""
    safe_url = validate_public_http_url(url)
    session = session or _session()
    resp = session.get(safe_url, timeout=_DEFAULT_TIMEOUT, allow_redirects=True)
    resp.raise_for_status()
    if resp.encoding:
        resp.encoding = resp.apparent_encoding or resp.encoding
    return resp.text, session


def fetch_page_html(url: str) -> str:
    html, _ = fetch_page(url)
    return html


def _filename_from_response(
    url: str,
    content_disposition: str,
    content_type: str,
    *,
    hint_filename: str | None = None,
    hint_suffix: str | None = None,
) -> str:
    name = ""

    if content_disposition:
        match = re.search(
            r"filename\*=(?:UTF-8''|utf-8'')([^;\s]+)",
            content_disposition,
            re.I,
        )
        if match:
            name = unquote(match.group(1).strip())
        else:
            match = re.search(r'filename="?([^";]+)"?', content_disposition, re.I)
            if match:
                name = unquote(match.group(1).strip())

    if not name:
        path = urlparse(url).path
        name = unquote(path.rsplit("/", 1)[-1]) or ""

    if hint_filename:
        hint = _sanitize_filename(hint_filename)
        if Path(hint).suffix.lower() in INGESTABLE_SUFFIXES:
            if not name or Path(name).suffix.lower() not in INGESTABLE_SUFFIXES:
                name = hint

    suffix = Path(name).suffix.lower() if name else ""
    if suffix not in INGESTABLE_SUFFIXES:
        ct = (content_type or "").split(";")[0].strip().lower()
        mapped = _CONTENT_TYPE_SUFFIX.get(ct)
        if mapped:
            stem = Path(name).stem if name else (Path(hint_filename or "documento").stem)
            name = f"{stem}{mapped}"
        elif hint_suffix and hint_suffix in INGESTABLE_SUFFIXES:
            stem = Path(name).stem if name and name != "download" else Path(hint_filename or "documento").stem
            name = f"{stem}{hint_suffix}"

    if not name:
        name = "documento.bin"

    return _sanitize_filename(name)


def _sanitize_filename(name: str) -> str:
    name = name.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^\w\s.\-()]", "_", name, flags=re.UNICODE)
    name = re.sub(r"\s+", "_", name.strip())
    return name[:180] or "documento.bin"
