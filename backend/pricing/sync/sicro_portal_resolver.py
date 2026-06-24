"""Resolve downloads SICRO no portal DNIT (gov.br)."""

from __future__ import annotations

import logging
import re
import time
import unicodedata
from dataclasses import dataclass
from http.client import IncompleteRead
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests
from requests.exceptions import ChunkedEncodingError, ConnectionError, ReadTimeout
from urllib3.exceptions import ProtocolError

logger = logging.getLogger(__name__)

SICRO_PORTAL_URL = (
    "https://www.gov.br/dnit/pt-br/assuntos/planejamento-e-pesquisa/"
    "custos-referenciais/sistemas-de-custos/sicro/relatorios/relatorios-sicro"
)
SICRO_BASE_PATH = (
    "/pt-br/assuntos/planejamento-e-pesquisa/custos-referenciais/"
    "sistemas-de-custos/sicro/relatorios/relatorios-sicro"
)

SICRO_REGIONS = ("norte", "nordeste", "centro-oeste", "sudeste", "sul")

# slug DNIT → UF (arquivo am-01-2026.7z)
STATE_SLUG_TO_UF: dict[str, str] = {
    "acre": "AC",
    "amazonas": "AM",
    "amapa": "AP",
    "para": "PA",
    "rondonia": "RO",
    "roraima": "RR",
    "tocantins": "TO",
    "alagoas": "AL",
    "bahia": "BA",
    "ceara": "CE",
    "maranhao": "MA",
    "paraiba": "PB",
    "pernambuco": "PE",
    "piaui": "PI",
    "rio-grande-do-norte": "RN",
    "sergipe": "SE",
    "distrito-federal": "DF",
    "goias": "GO",
    "mato-grosso": "MT",
    "mato-grosso-do-sul": "MS",
    "espirito-santo": "ES",
    "minas-gerais": "MG",
    "rio-de-janeiro": "RJ",
    "sao-paulo": "SP",
    "parana": "PR",
    "rio-grande-do-sul": "RS",
    "santa-catarina": "SC",
}

MONTH_FOLDER: dict[int, str] = {1: "janeiro", 4: "abril", 7: "julho", 10: "outubro"}
MONTH_SLUG = MONTH_FOLDER

_ARCHIVE_RE = re.compile(
    r'href="(?P<url>https://www\.gov\.br/dnit[^"]+/(?P<name>[a-z]{2}-\d{2}-\d{4})\.(?:7z|zip))"',
    re.I,
)
_HREF_RE = re.compile(r'href="(?P<url>[^"]+)"')
_STATE_PATH_RE = re.compile(
    rf"{re.escape(SICRO_BASE_PATH)}/(?P<region>[\w-]+)/(?P<state>[\w-]+)/(?P<year>\d{{4}})/(?P<month>[\w-]+)/(?P<slug>[\w-]+)"
)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

_CHUNK_SIZE = 256 * 1024
_CONNECT_TIMEOUT = 30
_READ_TIMEOUT = 600
_DOWNLOAD_RETRIES = 5
_DOWNLOAD_DELAYS = (3.0, 6.0, 12.0, 24.0, 45.0)


@dataclass(frozen=True)
class SicroArchiveLink:
    url: str
    filename: str
    uf: str
    year: int
    month: int
    region: str
    state_slug: str

    @property
    def reference(self) -> str:
        return f"BR-SICRO-{self.uf}-{self.year}-{self.month:02d}"


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": _USER_AGENT,
            "Accept-Language": "pt-BR,pt;q=0.9",
            "Accept": "application/x-7z-compressed,application/zip,application/octet-stream,*/*",
        }
    )
    return session


def _is_transient_download_error(exc: BaseException) -> bool:
    if isinstance(exc, (IncompleteRead, ChunkedEncodingError, ConnectionError, ReadTimeout, ProtocolError)):
        return True
    if isinstance(exc, requests.HTTPError):
        resp = exc.response
        return resp is not None and resp.status_code >= 500
    cur: BaseException | None = exc
    while cur is not None:
        msg = str(cur).lower()
        if "incompleteread" in msg or "connection broken" in msg:
            return True
        cur = cur.__cause__  # type: ignore[assignment]
    return False


def download_archive(
    link: SicroArchiveLink,
    dest: Path,
    *,
    session: requests.Session | None = None,
) -> Path:
    """Baixa .7z/.zip do DNIT com streaming, verificação de tamanho e retries."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    out = dest / link.filename
    http = session or _session()
    headers = {"Referer": SICRO_PORTAL_URL}

    last_error: Exception | None = None
    for attempt in range(_DOWNLOAD_RETRIES):
        try:
            if out.exists():
                out.unlink()

            with http.get(
                link.url,
                stream=True,
                timeout=(_CONNECT_TIMEOUT, _READ_TIMEOUT),
                headers=headers,
                allow_redirects=True,
            ) as response:
                response.raise_for_status()
                raw_len = response.headers.get("Content-Length")
                expected_size = int(raw_len) if raw_len and str(raw_len).isdigit() else None

                written = 0
                with open(out, "wb") as handle:
                    for chunk in response.iter_content(chunk_size=_CHUNK_SIZE):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        written += len(chunk)

                if expected_size is not None and written < expected_size:
                    raise IncompleteRead(b"", expected_size - written)
                if written < 1024:
                    raise ValueError(
                        f"Arquivo SICRO suspeitamente pequeno ({written} bytes): {link.filename}"
                    )

            logger.info("SICRO baixado %s (%s bytes)", link.filename, written)
            return out
        except Exception as exc:
            last_error = exc
            if out.exists():
                out.unlink(missing_ok=True)
            if isinstance(exc, requests.HTTPError):
                resp = exc.response
                if resp is not None and resp.status_code < 500:
                    raise
            if not _is_transient_download_error(exc):
                raise
            logger.warning(
                "SICRO download %s tentativa %s/%s: %s",
                link.filename,
                attempt + 1,
                _DOWNLOAD_RETRIES,
                exc,
            )
            if attempt < _DOWNLOAD_RETRIES - 1:
                time.sleep(_DOWNLOAD_DELAYS[min(attempt, len(_DOWNLOAD_DELAYS) - 1)])

    assert last_error is not None
    raise RuntimeError(
        f"Falha ao baixar {link.filename} ({link.uf}) após {_DOWNLOAD_RETRIES} tentativas: {last_error}"
    ) from last_error


def _fetch_html(url: str) -> str:
    response = _session().get(url, timeout=60)
    response.raise_for_status()
    return response.text


def _slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug


def month_folder(month: int) -> str:
    if month in MONTH_FOLDER:
        return MONTH_FOLDER[month]
    names = (
        "janeiro",
        "fevereiro",
        "marco",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    )
    if 1 <= month <= 12:
        return names[month - 1]
    raise ValueError(f"Mês inválido: {month}")


def list_state_slugs(region: str) -> list[str]:
    """Lista slugs de estados em uma região DNIT (ex.: norte → amazonas, acre…)."""
    url = f"{SICRO_PORTAL_URL}/{region}/{region}"
    html = _fetch_html(url)
    prefix = f"{SICRO_BASE_PATH}/{region}/"
    states: set[str] = set()
    for match in _HREF_RE.finditer(html):
        href = match.group("url")
        if prefix not in href:
            continue
        tail = href.split(prefix, 1)[-1].strip("/")
        state = tail.split("/", 1)[0]
        if state and state != region:
            states.add(state)
    return sorted(states)


def build_month_page_url(
    *,
    region: str,
    state_slug: str,
    year: int,
    month: int,
) -> str:
    month_name = month_folder(month)
    slug = f"{month_name}-{year}"
    return (
        f"https://www.gov.br/dnit{SICRO_BASE_PATH}/"
        f"{region}/{state_slug}/{year}/{month_name}/{slug}"
    )


def resolve_archive_on_page(page_url: str) -> SicroArchiveLink | None:
    html = _fetch_html(page_url)
    match = _ARCHIVE_RE.search(html)
    if not match:
        return None
    archive_url = match.group("url")
    filename = f"{match.group('name')}.{archive_url.rsplit('.', 1)[-1]}"
    parts = match.group("name").split("-")
    if len(parts) != 3:
        return None
    uf = parts[0].upper()
    month = int(parts[1])
    year = int(parts[2])
    path_match = _STATE_PATH_RE.search(page_url)
    region = path_match.group("region") if path_match else ""
    state_slug = path_match.group("state") if path_match else ""
    return SicroArchiveLink(
        url=archive_url,
        filename=filename,
        uf=uf,
        year=year,
        month=month,
        region=region,
        state_slug=state_slug,
    )


def resolve_archive_for_state(
    *,
    state_slug: str,
    year: int,
    month: int,
    region: str | None = None,
) -> SicroArchiveLink | None:
    """Localiza .7z/.zip publicado para UF/mês no portal DNIT."""
    regions = [region] if region else list(SICRO_REGIONS)
    month_name = month_folder(month)
    slug = f"{month_name}-{year}"

    for reg in regions:
        page_url = (
            f"https://www.gov.br/dnit{SICRO_BASE_PATH}/"
            f"{reg}/{state_slug}/{year}/{month_name}/{slug}"
        )
        try:
            link = resolve_archive_on_page(page_url)
        except Exception as exc:
            logger.debug("SICRO page miss %s: %s", page_url, exc)
            continue
        if link:
            return link
    return None


def resolve_archive_by_uf(
    uf: str,
    *,
    year: int,
    month: int,
) -> SicroArchiveLink | None:
    uf = uf.upper()
    state_slug = next((slug for slug, code in STATE_SLUG_TO_UF.items() if code == uf), None)
    if not state_slug:
        state_slug = _slugify(uf)
    region = next(
        (
            reg
            for reg in SICRO_REGIONS
            for slug, code in STATE_SLUG_TO_UF.items()
            if code == uf and slug.startswith(state_slug[:3])
        ),
        None,
    )
    return resolve_archive_for_state(
        state_slug=state_slug,
        year=year,
        month=month,
        region=region,
    )


def iter_all_state_archives(
    *,
    year: int,
    month: int,
    regions: Iterable[str] | None = None,
) -> list[SicroArchiveLink]:
    """Varre regiões/UFs e retorna links de arquivo disponíveis no portal."""
    found: list[SicroArchiveLink] = []
    seen: set[str] = set()
    for region in regions or SICRO_REGIONS:
        try:
            states = list_state_slugs(region)
        except Exception as exc:
            logger.warning("SICRO região %s indisponível: %s", region, exc)
            continue
        for state_slug in states:
            page_url = build_month_page_url(
                region=region,
                state_slug=state_slug,
                year=year,
                month=month,
            )
            try:
                link = resolve_archive_on_page(page_url)
            except Exception as exc:
                logger.debug("SICRO %s: %s", state_slug, exc)
                continue
            if not link or link.uf in seen:
                continue
            seen.add(link.uf)
            found.append(link)
    return sorted(found, key=lambda x: x.uf)


def sicro_reference_key(uf: str, year: int, month: int) -> str:
    return f"BR-SICRO-{uf.upper()}-{year}-{month:02d}"


def list_imported_sicro_ufs(*, year: int, month: int) -> set[str]:
    """UFs com banco SICRO completo já gravado para o período."""
    from pricing.budget.price_bank_index import PriceBankIndex
    from pricing.budget.price_bank_store import CLOSED_NAME, PriceBankStore

    suffix = f"-{year}-{month:02d}"
    imported: set[str] = set()
    for entry in PriceBankIndex.load().references:
        ref = entry.reference.replace("/", "-").upper()
        if not ref.startswith("BR-SICRO-") or not ref.endswith(suffix):
            continue
        parts = ref.split("-")
        if len(parts) < 5:
            continue
        uf = parts[2].upper()
        store = PriceBankStore.for_reference(ref)
        if store.load_manifest() and (store.root / CLOSED_NAME).is_file():
            imported.add(uf)
    return imported
