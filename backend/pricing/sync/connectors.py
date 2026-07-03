"""Conectores de download/importação por fonte de preços."""

from __future__ import annotations

import io
import logging
import re
import time
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import requests

from pricing.sync.sinapi_errors import SinapiDownloadBlockedError, SinapiPeriodNotFoundError
from pricing.sync.sinapi_links import SINAPI_PORTAL
from pricing.sync.sinapi_parser import export_sinapi_csv, parse_sinapi_full_workbook

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
_DOWNLOAD_RETRIES = 4
_DOWNLOAD_DELAYS = (2.0, 5.0, 15.0, 30.0)


@dataclass
class DownloadResult:
    source: str
    local_path: Path
    reference: str
    item_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class BasePriceConnector(ABC):
    name: str
    label: str

    @abstractmethod
    def download(self, *, dest_dir: Path, **options: Any) -> DownloadResult:
        """Baixa ou resolve arquivo local da base."""

    def supports_auto_download(self) -> bool:
        return True


class SinapiConnector(BasePriceConnector):
    name = "sinapi"
    label = "SINAPI (Caixa)"

    # Formato legado (até ~2024): ZIP por UF
    LEGACY_BASE_URL = (
        "https://www.caixa.gov.br/Downloads/sinapi-relatorios-mensais-de-precos"
    )
    # Formato 2025+: ZIP nacional com todas as UFs (planilha Referência)
    NATIONAL_BASE_URL = (
        "https://www.caixa.gov.br/Downloads/sinapi-relatorios-mensais"
    )
    NATIONAL_FORMAT_FROM = (2025, 1)

    @staticmethod
    def reference_url_legacy(
        uf: str,
        *,
        year: int,
        month: int,
        desonerado: bool = True,
    ) -> str:
        yyyymm = f"{year}{month:02d}"
        suffix = "Desonerado" if desonerado else "NaoDesonerado"
        return (
            f"{SinapiConnector.LEGACY_BASE_URL}/{uf.upper()}/"
            f"SINAPI_Referencia_{yyyymm}_{suffix}.zip"
        )

    @staticmethod
    def reference_url_national(*, year: int, month: int) -> str:
        return (
            f"{SinapiConnector.NATIONAL_BASE_URL}/"
            f"SINAPI-{year}-{month:02d}-formato-xlsx.zip"
        )

    @staticmethod
    def _uses_national_format(year: int, month: int) -> bool:
        fy, fm = SinapiConnector.NATIONAL_FORMAT_FROM
        return (year, month) >= (fy, fm)

    @staticmethod
    def reference_url(
        uf: str,
        *,
        year: int,
        month: int,
        desonerado: bool = True,
    ) -> str:
        if SinapiConnector._uses_national_format(year, month):
            return SinapiConnector.reference_url_national(year=year, month=month)
        return SinapiConnector.reference_url_legacy(
            uf, year=year, month=month, desonerado=desonerado
        )

    @staticmethod
    def _default_period() -> tuple[int, int]:
        today = date.today()
        if today.month == 1:
            return today.year - 1, 12
        return today.year, today.month - 1

    @staticmethod
    def _shift_period(year: int, month: int, delta: int) -> tuple[int, int]:
        month -= delta
        while month < 1:
            month += 12
            year -= 1
        return year, month

    @staticmethod
    def _candidate_periods(
        year: int | None, month: int | None, *, lookback: int = 6
    ) -> list[tuple[int, int]]:
        if year is None or month is None:
            y, m = SinapiConnector._default_period()
        else:
            y, m = year, month
        return [SinapiConnector._shift_period(y, m, i) for i in range(lookback)]

    def _http_get(self, url: str, *, uf: str = "", period: str = "") -> bytes:
        last_error: Exception | None = None
        headers = {
            "User-Agent": _USER_AGENT,
            "Accept": "application/zip,application/vnd.ms-excel,application/octet-stream,*/*",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Referer": SINAPI_PORTAL,
        }
        session = requests.Session()
        session.headers.update(headers)
        try:
            session.get(SINAPI_PORTAL, timeout=30)
        except Exception as exc:
            logger.debug("SINAPI portal warmup falhou: %s", exc)

        for attempt in range(_DOWNLOAD_RETRIES):
            try:
                response = session.get(url, timeout=120, allow_redirects=True)
                status = response.status_code
                if status == 403:
                    raise SinapiDownloadBlockedError(
                        uf=uf, period=period, status_code=status
                    )
                if status == 429:
                    delay = _DOWNLOAD_DELAYS[min(attempt, len(_DOWNLOAD_DELAYS) - 1)]
                    logger.warning("SINAPI rate limit (429); retry em %.0fs", delay)
                    time.sleep(delay)
                    continue
                if status == 404:
                    raise FileNotFoundError(url)
                if status in (502, 503, 504):
                    last_error = requests.HTTPError(
                        f"HTTP {status} from Caixa", response=response
                    )
                    if attempt < _DOWNLOAD_RETRIES - 1:
                        time.sleep(_DOWNLOAD_DELAYS[min(attempt, len(_DOWNLOAD_DELAYS) - 1)])
                        continue
                    raise SinapiDownloadBlockedError(
                        uf=uf, period=period, status_code=status
                    )
                response.raise_for_status()
                content = response.content
                head = content[:32].lstrip()
                is_html = head.startswith(b"<!") or head.startswith(b"<html")
                final_url = str(response.url).lower()
                if is_html:
                    # Mês não publicado: Caixa redireciona para home/erro com HTML (~300 KB)
                    unavailable = (
                        status == 404
                        or "home-caixa" in final_url
                        or "/paginas/home" in final_url
                        or len(content) < 1_000_000
                    )
                    if unavailable:
                        logger.info(
                            "SINAPI %s indisponível (HTML %s bytes, url=%s)",
                            period,
                            len(content),
                            final_url[:80],
                        )
                        raise FileNotFoundError(url)
                    raise SinapiDownloadBlockedError(
                        uf=uf, period=period, status_code=status
                    )
                if len(content) < 1024:
                    raise ValueError(f"Arquivo SINAPI suspeitoamente pequeno ({len(content)} bytes)")
                return content
            except SinapiDownloadBlockedError:
                raise
            except FileNotFoundError:
                raise
            except Exception as exc:
                last_error = exc
                if attempt < _DOWNLOAD_RETRIES - 1:
                    time.sleep(_DOWNLOAD_DELAYS[min(attempt, len(_DOWNLOAD_DELAYS) - 1)])
        assert last_error is not None
        raise last_error

    @staticmethod
    def _sinapi_portal_page_url() -> str:
        from pricing.sync.source_registry import get_source_registry

        return get_source_registry().get_download_url("sinapi")

    def _download_remote_zip(
        self,
        *,
        dest_dir: Path,
        uf: str,
        year: int | None,
        month: int | None,
        desonerado: bool,
    ) -> tuple[Path, Path, str]:
        """Baixa ZIP SINAPI — portal downloads.aspx (categoria_888) + fallback URL direta."""
        lookback = 1 if year is not None and month is not None else 6
        tried: list[str] = []
        blocked: SinapiDownloadBlockedError | None = None
        portal_url = self._sinapi_portal_page_url()

        for y, m in self._candidate_periods(year, month, lookback=lookback):
            period = f"{y:04d}-{m:02d}"
            tried.append(period)
            national = self._uses_national_format(y, m)
            fmt = "nacional" if national else "legado"
            try:
                if national:
                    from pricing.sync.sinapi_portal_resolver import resolve_download_url

                    url, title = resolve_download_url(
                        y,
                        m,
                        page_url=portal_url or None,
                        uf=uf,
                        national=True,
                    )
                    logger.info(
                        "Baixando SINAPI %s UF=%s (%s via portal: %s) — %s",
                        period,
                        uf,
                        fmt,
                        title,
                        url,
                    )
                else:
                    url = self.reference_url(uf, year=y, month=m, desonerado=desonerado)
                    logger.info("Baixando SINAPI %s UF=%s (%s) — %s", period, uf, fmt, url)
                payload = self._http_get(url, uf=uf, period=period)
            except SinapiDownloadBlockedError as exc:
                logger.warning("SINAPI %s bloqueado pela Caixa — tentando mês anterior", period)
                blocked = exc
                continue
            except FileNotFoundError:
                logger.info("SINAPI %s não publicado ou indisponível no portal", period)
                continue

            zip_path = dest_dir / f"sinapi_{uf.upper()}_{y}{m:02d}.zip"
            zip_path.write_bytes(payload)
            xlsx_name, xlsx_bytes = self._pick_xlsx_from_zip(payload)
            xlsx_path = dest_dir / Path(xlsx_name).name
            xlsx_path.write_bytes(xlsx_bytes)
            ref = f"{uf.upper()}-{period}" if not national else f"BR-{period}"
            return zip_path, xlsx_path, ref

        if blocked:
            raise SinapiDownloadBlockedError(
                uf=uf,
                period=tried[0] if tried else "",
                status_code=getattr(blocked, "status_code", None),
                tried=tried,
            )
        raise SinapiPeriodNotFoundError(uf, tried)

    @staticmethod
    def _pick_xlsx_from_zip(data: bytes) -> tuple[str, bytes]:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            candidates = [
                name
                for name in zf.namelist()
                if name.lower().endswith((".xlsx", ".xls")) and not name.startswith("__MACOSX")
            ]
            if not candidates:
                raise ValueError("ZIP SINAPI sem planilha XLS/XLSX")
            preferred = next(
                (n for n in candidates if re.search(r"referencia|referência", n, re.I)),
                candidates[0],
            )
            return preferred, zf.read(preferred)

    def download(
        self,
        *,
        dest_dir: Path,
        uf: str = "SP",
        year: int | None = None,
        month: int | None = None,
        desonerado: bool = True,
        local_file: Path | None = None,
        on_progress: Any | None = None,
        set_active: bool = False,
        **_: Any,
    ) -> DownloadResult:
        dest_dir.mkdir(parents=True, exist_ok=True)

        def emit(pct: int, phase: str, msg: str) -> None:
            if on_progress:
                on_progress({"percent": pct, "phase": phase, "message": msg})

        if local_file and Path(local_file).is_file():
            emit(10, "download", "Lendo arquivo local…")
            source_path = Path(local_file)
            if source_path.suffix.lower() == ".zip":
                _, xlsx_bytes = self._pick_xlsx_from_zip(source_path.read_bytes())
                xlsx_name = f"sinapi_{uf.upper()}_{year or 'local'}.xlsx"
                xlsx_path = dest_dir / xlsx_name
                xlsx_path.write_bytes(xlsx_bytes)
            else:
                xlsx_path = source_path
            if year and month:
                ref = f"BR-{year}-{month:02d}"
            else:
                ref = source_path.stem
            emit(22, "download", "Arquivo local pronto")
        else:
            emit(8, "download", "Baixando SINAPI na Caixa…")
            _, xlsx_path, ref = self._download_remote_zip(
                dest_dir=dest_dir,
                uf=uf,
                year=year,
                month=month,
                desonerado=desonerado,
            )
            emit(22, "download", "Download concluído")

        xlsx_path = Path(xlsx_path)
        if xlsx_path.suffix.lower() in (".xlsx", ".xls"):
            emit(28, "parse", "Extraindo composições, CPUs e insumos (ComD + SemD)…")
            bank = parse_sinapi_full_workbook(xlsx_path, uf=uf.upper(), desonerado=desonerado)
            emit(
                52,
                "parse",
                f"Planilha processada — {len(bank['closed']):,} composições".replace(",", "."),
            )
        else:
            from pricing.providers._tabular import parse_tabular_file
            from pricing.budget.price_bank_store import CompositionClosed

            rows = parse_tabular_file(xlsx_path)
            bank = {
                "closed": [
                    CompositionClosed(
                        code=r["code"],
                        description=r["description"],
                        unit=r.get("unit", "un"),
                        price=float(r.get("price") or 0),
                    )
                    for r in rows
                ],
                "open": {},
                "insumos": [],
            }
        closed_rows = [c.to_dict() for c in bank["closed"]]
        csv_path = dest_dir / f"sinapi_{ref.replace('/', '-')}_fechadas.csv"
        export_sinapi_csv(closed_rows, csv_path)

        emit(58, "bank", "Gravando banco de preços…")
        from pricing.budget.price_bank_store import PriceBankStore

        dual = bank.get("format") == "national"
        ref_key = ref.replace("/", "-")
        if not ref_key.upper().startswith("BR-"):
            ref_key = f"BR-{ref_key}"
        manifest = PriceBankStore.for_reference(ref_key).save_bank(
            source=self.name,
            reference=ref_key,
            closed=bank["closed"],
            open_compositions=bank["open"],
            insumos=bank["insumos"],
            uf=uf.upper(),
            desonerado=True,
            labor_charges=bank.get("labor_charges"),
            metadata={
                "xlsx_path": str(xlsx_path),
                "zip_path": str(dest_dir),
                "format": bank.get("format", "legacy"),
                "dual_desoneracao": dual,
                "all_ufs": bank.get("all_ufs", False),
                "year": year,
                "month": month,
            },
            set_active=set_active,
        )
        emit(65, "bank", "Banco de preços salvo")

        return DownloadResult(
            source=self.name,
            local_path=csv_path,
            reference=ref,
            item_count=len(closed_rows),
            metadata={
                "uf": uf.upper(),
                "xlsx_path": str(xlsx_path),
                "desonerado": True,
                "dual_desoneracao": dual,
                "format": bank.get("format", "legacy"),
                "all_ufs": bank.get("all_ufs", False),
                "reference": ref_key,
                "bank": manifest.to_dict(),
                "compositions_closed": manifest.counts.get("compositions_closed", 0),
                "compositions_open": manifest.counts.get("compositions_open", 0),
                "insumos": manifest.counts.get("insumos", 0),
                "open_items_total": manifest.counts.get("open_items_total", 0),
            },
        )


class OrseConnector(BasePriceConnector):
    """
    ORSE (Sergipe) — download mensal do pacote `.ORSE` (CEHOP).

    O arquivo `.ORSE` é um pacote proprietário criptografado para atualização
    do SQL Server interno do ORSE 2 — **não** é CSV/Excel. Para alimentar o
    IA Server Santos, informe também export tabular (Relatórios → Composições/Insumos
    no ORSE) via `local_file` ou `ORSE_EXPORT_PATH`.
    """

    name = "orse"
    label = "ORSE (Sergipe)"
    PORTAL_BASE = "https://orse.cehop.se.gov.br"

    @staticmethod
    def monthly_filename(*, year: int, month: int, revision: str = "00") -> str:
        return f"{year}{month:02d}01-{revision}.ORSE"

    @staticmethod
    def monthly_download_url(*, year: int, month: int, revision: str = "00") -> str:
        name = OrseConnector.monthly_filename(year=year, month=month, revision=revision)
        return f"{OrseConnector.PORTAL_BASE}/downloads/{name}"

    @staticmethod
    def reference_label(*, year: int, month: int) -> str:
        return f"BR-ORSE-{year}-{month:02d}"

    def supports_auto_download(self) -> bool:
        return True

    def _session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({"User-Agent": _USER_AGENT})
        return session

    def _download_monthly_orse(
        self,
        *,
        dest_dir: Path,
        year: int,
        month: int,
        on_progress: Any | None = None,
    ) -> Path:
        dest_dir.mkdir(parents=True, exist_ok=True)
        filename = self.monthly_filename(year=year, month=month)
        dest = dest_dir / filename
        url = self.monthly_download_url(year=year, month=month)

        def emit(pct: int, msg: str) -> None:
            if on_progress:
                on_progress({"percent": pct, "phase": "download", "message": msg})

        emit(5, f"Baixando {filename} da CEHOP…")
        session = self._session()
        last_err: Exception | None = None
        for attempt, delay in enumerate(_DOWNLOAD_DELAYS, start=1):
            try:
                resp = session.get(url, timeout=180, stream=True)
                if resp.status_code == 404:
                    raise FileNotFoundError(
                        f"Base ORSE {year}-{month:02d} não publicada em {url}"
                    )
                resp.raise_for_status()
                size = int(resp.headers.get("Content-Length") or 0)
                written = 0
                with open(dest, "wb") as handle:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            handle.write(chunk)
                            written += len(chunk)
                            if size > 0:
                                pct = 5 + round(written / size * 55)
                                emit(min(60, pct), f"Download ORSE… {written // 1024} KB")
                if written < 1024:
                    raise ValueError(f"Download ORSE inválido ({written} bytes) — {url}")
                emit(62, f"Pacote ORSE salvo ({written // 1024} KB)")
                return dest
            except Exception as exc:
                last_err = exc
                if attempt < len(_DOWNLOAD_DELAYS):
                    time.sleep(delay)
        raise RuntimeError(f"Falha ao baixar ORSE após {_DOWNLOAD_RETRIES} tentativas") from last_err

    def _resolve_export_bundle(
        self,
        *,
        local_file: Path | None,
        insumos_file: Path | None,
        composicoes_file: Path | None,
        analitico_file: Path | None,
        dest_dir: Path,
        year: int,
        month: int,
    ) -> tuple[Path, Path | None, Path | None] | None:
        import os

        from pricing.budget.orse_bundle_detect import (
            classify_orse_bundle_files,
            is_foreign_price_base_file,
            is_orse_composicoes_file,
        )

        def _reject_foreign(path: Path, *, role: str) -> None:
            if is_foreign_price_base_file(path):
                raise ValueError(
                    f"Arquivo '{path.name}' não é export ORSE ({role}) — parece SEMINF/PPD/SINAPI. "
                    "Use planilhas exportadas do ORSE 2 (Relatórios → Cadastrais)."
                )

        if composicoes_file and composicoes_file.is_file():
            _reject_foreign(composicoes_file, role="composições")
            if insumos_file and insumos_file.is_file():
                _reject_foreign(insumos_file, role="insumos")
            if analitico_file and analitico_file.is_file():
                _reject_foreign(analitico_file, role="analítico")
            return composicoes_file, insumos_file, analitico_file

        if local_file and local_file.is_file():
            suffix = local_file.suffix.lower()
            if suffix in (".xlsx", ".xls", ".csv"):
                if is_orse_composicoes_file(local_file):
                    return local_file, insumos_file, analitico_file
                classified = classify_orse_bundle_files([local_file])
                if classified["composicoes"]:
                    return (
                        classified["composicoes"],
                        classified.get("insumos") or insumos_file,
                        classified.get("analitico") or analitico_file,
                    )
                _reject_foreign(local_file, role="arquivo")
                return local_file, insumos_file, analitico_file
            if local_file.is_dir():
                paths = [p for p in local_file.rglob("*") if p.is_file()]
                classified = classify_orse_bundle_files(paths)
                if classified["composicoes"]:
                    return (
                        classified["composicoes"],
                        classified.get("insumos"),
                        classified.get("analitico"),
                    )

        ref = self.reference_label(year=year, month=month)
        export_dir = Path(os.environ.get("ORSE_EXPORT_DIR", "")).expanduser()
        if export_dir.is_dir():
            period_dir = export_dir / ref
            if period_dir.is_dir():
                paths = [p for p in period_dir.rglob("*") if p.is_file()]
                classified = classify_orse_bundle_files(paths)
                if classified["composicoes"]:
                    return (
                        classified["composicoes"],
                        classified.get("insumos"),
                        classified.get("analitico"),
                    )

        for pattern in (f"orse_{ref}_composicoes.xlsx", f"orse_{ref}_insumos.xlsx"):
            candidate = dest_dir / pattern
            if candidate.is_file() and "composic" in pattern:
                ins = dest_dir / f"orse_{ref}_insumos.xlsx"
                return candidate, ins if ins.is_file() else None, None
        return None

    def _save_orse_bundle(
        self,
        *,
        bundle: Any,
        dest_dir: Path,
        year: int,
        month: int,
        uf: str,
        orse_package: Path | None,
        on_progress: Any | None = None,
        set_active: bool = False,
        import_mode: str = "orse_export",
    ) -> DownloadResult:
        def emit(pct: int, phase: str, msg: str) -> None:
            if on_progress:
                on_progress({"percent": pct, "phase": phase, "message": msg})

        from pricing.budget.price_bank_store import PriceBankStore
        from pricing.sync.sinapi_parser import export_sinapi_csv

        ref_key = self.reference_label(year=year, month=month)
        emit(50, "bank", f"Gravando price_bank {ref_key}…")
        dest_dir.mkdir(parents=True, exist_ok=True)
        csv_path = dest_dir / f"orse_{ref_key.replace('/', '-')}.csv"
        export_sinapi_csv([c.to_dict() for c in bundle.closed], csv_path)

        bank_metadata = {
            **(bundle.metadata or {}),
            "year": year,
            "month": month,
            "import_mode": import_mode,
        }
        if orse_package:
            bank_metadata["orse_package"] = str(orse_package.resolve())
            bank_metadata["orse_package_bytes"] = orse_package.stat().st_size

        manifest = PriceBankStore.for_reference(ref_key).save_bank(
            source=self.name,
            reference=ref_key,
            closed=bundle.closed,
            open_compositions=bundle.open_map,
            insumos=bundle.insumos,
            uf=uf.upper(),
            desonerado=True,
            metadata=bank_metadata,
            set_active=set_active,
        )
        open_items = sum(len(c.items) for c in bundle.open_map.values())
        emit(65, "bank", "Banco ORSE salvo")

        return DownloadResult(
            source=self.name,
            local_path=csv_path,
            reference=ref_key,
            item_count=len(bundle.closed),
            metadata={
                "reference": ref_key,
                "bank": manifest.to_dict(),
                "compositions_closed": manifest.counts.get("compositions_closed", 0),
                "compositions_open": manifest.counts.get("compositions_open", 0),
                "insumos": manifest.counts.get("insumos", 0),
                "open_items_total": open_items,
                **bank_metadata,
            },
        )

    def download_from_portal(
        self,
        *,
        dest_dir: Path,
        year: int,
        month: int,
        uf: str = "SE",
        on_progress: Any | None = None,
        set_active: bool = False,
    ) -> DownloadResult:
        """Importa ORSE via portal público CEHOP (sem ORSE 2 / Excel)."""
        from pricing.sync.orse_portal_scraper import OrsePortalScraper

        def emit(pct: int, phase: str, msg: str) -> None:
            if on_progress:
                on_progress({"percent": pct, "phase": phase, "message": msg})

        emit(3, "portal", f"Conectando ao portal CEHOP — {month:02d}/{year}…")
        scraper = OrsePortalScraper(
            year=year,
            month=month,
            on_progress=on_progress,
        )
        bundle = scraper.build_bundle()
        emit(92, "portal", "Portal CEHOP processado — gravando banco…")
        return self._save_orse_bundle(
            bundle=bundle,
            dest_dir=dest_dir,
            year=year,
            month=month,
            uf=uf,
            orse_package=None,
            on_progress=on_progress,
            set_active=set_active,
            import_mode="orse_portal",
        )

    def _ingest_export_bundle(
        self,
        *,
        dest_dir: Path,
        composicoes_path: Path,
        insumos_path: Path | None,
        analitico_path: Path | None,
        year: int,
        month: int,
        uf: str,
        orse_package: Path | None,
        on_progress: Any | None = None,
        set_active: bool = False,
    ) -> DownloadResult:
        def emit(pct: int, phase: str, msg: str) -> None:
            if on_progress:
                on_progress({"percent": pct, "phase": phase, "message": msg})

        from pricing.sync.orse_export_parser import parse_orse_export_bundle

        emit(20, "parse", f"Lendo composições — {composicoes_path.name}…")
        bundle = parse_orse_export_bundle(
            composicoes_path=composicoes_path,
            insumos_path=insumos_path,
            analitico_path=analitico_path,
        )

        return self._save_orse_bundle(
            bundle=bundle,
            dest_dir=dest_dir,
            year=year,
            month=month,
            uf=uf,
            orse_package=orse_package,
            on_progress=on_progress,
            set_active=set_active,
            import_mode="orse_export",
        )

    def download_package_only(
        self,
        *,
        dest_dir: Path,
        year: int,
        month: int,
        on_progress: Any | None = None,
    ) -> DownloadResult:
        """Baixa pacote `.ORSE` mensal da CEHOP (sem importar price_bank)."""
        package = self._download_monthly_orse(
            dest_dir=dest_dir / "packages",
            year=year,
            month=month,
            on_progress=on_progress,
        )
        ref = self.reference_label(year=year, month=month)
        return DownloadResult(
            source=self.name,
            local_path=package,
            reference=ref,
            item_count=0,
            metadata={
                "reference": ref,
                "orse_package": str(package.resolve()),
                "orse_package_bytes": package.stat().st_size,
                "package_only": True,
            },
        )

    def download(
        self,
        *,
        dest_dir: Path,
        local_file: Path | None = None,
        insumos_file: Path | None = None,
        composicoes_file: Path | None = None,
        analitico_file: Path | None = None,
        year: int | None = None,
        month: int | None = None,
        uf: str = "SE",
        package_only: bool = False,
        portal_sync: bool = False,
        on_progress: Any | None = None,
        set_active: bool = False,
        **_: Any,
    ) -> DownloadResult:
        today = date.today()
        year = year or today.year
        month = month or today.month

        if portal_sync:
            return self.download_from_portal(
                dest_dir=dest_dir,
                year=year,
                month=month,
                uf=uf,
                on_progress=on_progress,
                set_active=set_active,
            )

        if package_only:
            return self.download_package_only(
                dest_dir=dest_dir,
                year=year,
                month=month,
                on_progress=on_progress,
            )

        bundle_paths = self._resolve_export_bundle(
            local_file=local_file,
            insumos_file=insumos_file,
            composicoes_file=composicoes_file,
            analitico_file=analitico_file,
            dest_dir=dest_dir,
            year=year,
            month=month,
        )

        orse_package: Path | None = None
        if not bundle_paths:
            orse_package = self._download_monthly_orse(
                dest_dir=dest_dir / "packages",
                year=year,
                month=month,
                on_progress=on_progress,
            )
            bundle_paths = self._resolve_export_bundle(
                local_file=local_file,
                insumos_file=insumos_file,
                composicoes_file=composicoes_file,
                analitico_file=analitico_file,
                dest_dir=dest_dir,
                year=year,
                month=month,
            )

        if not bundle_paths:
            raise FileNotFoundError(
                "Pacote .ORSE baixado da CEHOP, mas faltam planilhas exportadas. "
                "No ORSE 2 (Windows): Ferramentas → Atualização da Base → aplique o .ORSE; "
                "depois Relatórios → Cadastrais → exporte Composições e Insumos (Excel). "
                "Use 'Importar pasta export ORSE' nesta tela ou defina ORSE_EXPORT_DIR no servidor."
                + (f" Pacote: {orse_package}" if orse_package else "")
            )

        composicoes_path, insumos_path, analitico_path = bundle_paths
        if composicoes_path.suffix.lower() == ".orse":
            raise ValueError(
                "Arquivo .ORSE é pacote de atualização do ORSE 2 — exporte Excel e importe a pasta."
            )

        return self._ingest_export_bundle(
            dest_dir=dest_dir,
            composicoes_path=composicoes_path,
            insumos_path=insumos_path,
            analitico_path=analitico_path,
            year=year,
            month=month,
            uf=uf,
            orse_package=orse_package,
            on_progress=on_progress,
            set_active=set_active,
        )


def is_orse_composicoes_file(path: Path) -> bool:
    from pricing.budget.orse_bundle_detect import is_orse_composicoes_file as _is

    return _is(path)


class TcpoConnector(BasePriceConnector):
    """TCPO — importação via arquivo local (sem portal único nacional)."""

    name = "tcpo"
    label = "TCPO"

    def supports_auto_download(self) -> bool:
        return False

    def download(
        self,
        *,
        dest_dir: Path,
        local_file: Path | None = None,
        **_: Any,
    ) -> DownloadResult:
        import os

        path = local_file or Path(os.environ.get("TCPO_EXPORT_PATH", ""))
        if not path.is_file():
            raise FileNotFoundError(
                "Informe local_file ou TCPO_EXPORT_PATH com planilha TCPO exportada."
            )

        from pricing.providers._tabular import parse_tabular_file
        from pricing.sync.sinapi_parser import export_sinapi_csv

        dest_dir.mkdir(parents=True, exist_ok=True)
        rows = parse_tabular_file(path)
        csv_path = dest_dir / f"tcpo_{path.stem}.csv"
        export_sinapi_csv(rows, csv_path)
        return DownloadResult(
            source=self.name,
            local_path=csv_path,
            reference=path.stem,
            item_count=len(rows),
            metadata={"source_file": str(path.resolve())},
        )


class CicroConnector(BasePriceConnector):
    name = "cicro"
    label = "CICRO/SICRO"

    def supports_auto_download(self) -> bool:
        return True

    def download(
        self,
        *,
        dest_dir: Path,
        uf: str = "AM",
        year: int | None = None,
        month: int | None = None,
        desonerado: bool = True,
        local_file: Path | None = None,
        on_progress: Any | None = None,
        set_active: bool = False,
        download_all_regions: bool = False,
        skip_existing_ufs: bool = False,
        **_: Any,
    ) -> DownloadResult:
        from datetime import date

        from pricing.budget.price_bank_store import PriceBankStore
        from pricing.sync.sinapi_parser import export_sinapi_csv
        from pricing.sync.sicro_parser import infer_sicro_reference, parse_sicro_package
        from pricing.sync.sicro_portal_resolver import (
            SICRO_PORTAL_URL,
            _session,
            download_archive,
            iter_all_state_archives,
            list_imported_sicro_ufs,
            resolve_archive_by_uf,
            sicro_reference_key,
        )

        def emit(pct: int, phase: str, msg: str) -> None:
            if on_progress:
                on_progress({"percent": pct, "phase": phase, "message": msg})

        dest_dir.mkdir(parents=True, exist_ok=True)

        if year is None or month is None:
            today = date.today()
            month = month or max(m for m in (1, 4, 7, 10) if m <= today.month) if today.month >= 1 else 1
            year = year or today.year

        if local_file and Path(local_file).exists():
            emit(10, "download", "Lendo pacote SICRO local…")
            package_path = Path(local_file)
        elif download_all_regions:
            emit(8, "download", "Listando bases SICRO no portal DNIT…")
            links = iter_all_state_archives(year=year, month=month)
            if not links:
                raise FileNotFoundError(
                    f"Nenhum arquivo SICRO {year}-{month:02d} encontrado em {SICRO_PORTAL_URL}"
                )
            imported = list_imported_sicro_ufs(year=year, month=month) if skip_existing_ufs else set()
            skipped_ufs = sorted(link.uf for link in links if link.uf in imported)
            pending = [link for link in links if link.uf not in imported]
            if skip_existing_ufs and skipped_ufs:
                emit(
                    9,
                    "download",
                    f"{len(skipped_ufs)} UF(s) já importada(s) — pulando: {', '.join(skipped_ufs[:8])}"
                    f"{'…' if len(skipped_ufs) > 8 else ''}",
                )
            if not pending:
                ref = sicro_reference_key(skipped_ufs[0] if skipped_ufs else links[0].uf, year, month)
                return DownloadResult(
                    source=self.name,
                    local_path=dest_dir,
                    reference=ref,
                    item_count=0,
                    metadata={
                        "synced_ufs": [],
                        "skipped_ufs": skipped_ufs,
                        "failed_ufs": [],
                        "sync_total": len(links),
                        "pending_total": 0,
                        "message": (
                            f"Todas as {len(skipped_ufs)} UF(s) já estão importadas para {year}-{month:02d}"
                            if skipped_ufs
                            else "Nenhuma UF pendente"
                        ),
                    },
                )
            http = _session()
            last_result: DownloadResult | None = None
            synced_ufs: list[str] = []
            failed_ufs: list[dict[str, str]] = []
            for idx, link in enumerate(pending):
                emit(
                    10 + int(70 * idx / max(len(pending), 1)),
                    "download",
                    f"Baixando SICRO {link.uf} ({idx + 1}/{len(pending)} pendente"
                    f"{f', {len(skipped_ufs)} pulada(s)' if skipped_ufs else ''})…",
                )
                try:
                    archive = download_archive(link, dest_dir, session=http)
                    last_result = self._import_sicro_package(
                        archive,
                        dest_dir=dest_dir,
                        uf=link.uf,
                        year=year,
                        month=month,
                        desonerado=desonerado,
                        set_active=set_active and idx == len(pending) - 1,
                        on_progress=on_progress,
                    )
                    synced_ufs.append(link.uf)
                except Exception as exc:
                    logger.exception("SICRO importação %s falhou", link.uf)
                    failed_ufs.append({"uf": link.uf, "error": str(exc)})
                    emit(
                        10 + int(70 * (idx + 1) / max(len(pending), 1)),
                        "download",
                        f"Falha em {link.uf} — continuando ({idx + 1}/{len(pending)})…",
                    )
                    continue
                if idx < len(pending) - 1:
                    time.sleep(2.0)
            if not last_result:
                detail = "; ".join(f"{f['uf']}: {f['error']}" for f in failed_ufs[:5])
                if skipped_ufs and not synced_ufs:
                    raise RuntimeError(
                        f"Nenhuma UF SICRO importada em {year}-{month:02d} "
                        f"({len(skipped_ufs)} já existiam). Falhas: {detail}"
                    )
                raise RuntimeError(
                    f"Nenhuma UF SICRO importada em {year}-{month:02d}. Falhas: {detail}"
                )
            last_result.metadata["synced_ufs"] = synced_ufs
            last_result.metadata["skipped_ufs"] = skipped_ufs
            last_result.metadata["failed_ufs"] = failed_ufs
            last_result.metadata["sync_total"] = len(links)
            last_result.metadata["pending_total"] = len(pending)
            return last_result
        else:
            emit(8, "download", f"Resolvendo SICRO {uf.upper()} {year}-{month:02d} no DNIT…")
            link = resolve_archive_by_uf(uf, year=year, month=month)
            if not link:
                raise FileNotFoundError(
                    f"SICRO {uf.upper()} {year}-{month:02d} não publicado — "
                    f"informe local_file ou verifique {SICRO_PORTAL_URL}"
                )
            emit(15, "download", f"Baixando {link.filename}…")
            package_path = download_archive(link, dest_dir)

        return self._import_sicro_package(
            package_path,
            dest_dir=dest_dir,
            uf=uf,
            year=year,
            month=month,
            desonerado=desonerado,
            set_active=set_active,
            on_progress=on_progress,
        )

    def _import_sicro_package(
        self,
        package_path: Path,
        *,
        dest_dir: Path,
        uf: str,
        year: int | None,
        month: int | None,
        desonerado: bool,
        set_active: bool,
        on_progress: Any | None,
    ) -> DownloadResult:
        from pricing.budget.price_bank_store import PriceBankStore
        from pricing.sync.sinapi_parser import export_sinapi_csv
        from pricing.sync.sicro_parser import infer_sicro_reference, parse_sicro_package

        def emit(pct: int, phase: str, msg: str) -> None:
            if on_progress:
                on_progress({"percent": pct, "phase": phase, "message": msg})

        inferred_uf, ref_key, y_inf, m_inf = infer_sicro_reference(package_path)
        uf_code = (uf or inferred_uf or "BR").upper()
        year = year or y_inf
        month = month or m_inf
        if not ref_key.startswith("BR-SICRO"):
            ref_key = f"BR-SICRO-{uf_code}-{year}-{month:02d}"

        emit(28, "parse", "Extraindo composições, CPUs e insumos SICRO…")
        bank = parse_sicro_package(package_path, uf=uf_code, desonerado=desonerado)
        closed = bank["closed"]
        open_map = bank["open"]
        insumos = bank["insumos"]
        emit(
            52,
            "parse",
            f"SICRO {uf_code}: {len(closed):,} composições · {len(insumos):,} insumos".replace(",", "."),
        )

        closed_rows = [c.to_dict() for c in closed]
        csv_path = dest_dir / f"sicro_{ref_key.replace('/', '-')}_fechadas.csv"
        export_sinapi_csv(closed_rows, csv_path)

        emit(58, "bank", "Gravando banco de preços SICRO…")
        manifest = PriceBankStore.for_reference(ref_key).save_bank(
            source=self.name,
            reference=ref_key,
            closed=closed,
            open_compositions=open_map,
            insumos=insumos,
            uf=uf_code,
            desonerado=desonerado,
            metadata={
                "package_path": str(package_path.resolve()),
                "format": bank.get("format", "sicro_dnit"),
                "dual_desoneracao": True,
                "region_label": bank.get("region_label"),
                "period_label": bank.get("period_label"),
                "year": year,
                "month": month,
                "portal_url": (
                    "https://www.gov.br/dnit/pt-br/assuntos/planejamento-e-pesquisa/"
                    "custos-referenciais/sistemas-de-custos/sicro/relatorios/relatorios-sicro"
                ),
            },
            set_active=set_active,
        )
        emit(65, "bank", "Banco SICRO salvo")

        open_items = sum(len(c.items) for c in open_map.values())
        return DownloadResult(
            source=self.name,
            local_path=csv_path,
            reference=ref_key,
            item_count=len(closed_rows),
            metadata={
                "uf": uf_code,
                "reference": ref_key,
                "bank": manifest.to_dict(),
                "compositions_closed": manifest.counts.get("compositions_closed", 0),
                "compositions_open": manifest.counts.get("compositions_open", 0),
                "insumos": manifest.counts.get("insumos", 0),
                "open_items_total": open_items,
                "format": "sicro_dnit",
            },
        )


class PpdSeminfConnector(BasePriceConnector):
    """DP/SEMINF — Tabela de Preço (fechadas) + Composicao-Seminf ComD/SemD (abertas)."""

    name = "ppd_seminf"
    label = "PPD / SEMINF (Manaus-AM)"
    _source_slug = "SEMINF"
    _default_uf = "AM"

    def supports_auto_download(self) -> bool:
        return False

    def download(
        self,
        *,
        dest_dir: Path,
        local_file: Path | None = None,
        open_comd_file: Path | None = None,
        open_semd_file: Path | None = None,
        year: int | None = None,
        month: int | None = None,
        uf: str | None = None,
        on_progress: Any | None = None,
        set_active: bool = False,
        **_: Any,
    ) -> DownloadResult:
        def emit(pct: int, phase: str, msg: str) -> None:
            if on_progress:
                on_progress({"percent": pct, "phase": phase, "message": msg})

        closed_path = Path(local_file) if local_file and Path(local_file).is_file() else None
        comd_path = Path(open_comd_file) if open_comd_file and Path(open_comd_file).is_file() else None
        semd_path = Path(open_semd_file) if open_semd_file and Path(open_semd_file).is_file() else None

        if not closed_path and not (comd_path and semd_path):
            raise FileNotFoundError(
                "DP/SEMINF requer Tabela_Preco (.xlsm) e/ou as duas planilhas "
                "Composicao-Seminf ComD + SemD (.xlsx)."
            )
        if (comd_path and not semd_path) or (semd_path and not comd_path):
            raise ValueError(
                "Informe as duas planilhas de composição aberta: ComD e SemD."
            )

        if closed_path and not (comd_path and semd_path):
            from pricing.budget.seminf_bundle_detect import resolve_seminf_open_siblings

            auto_comd, auto_semd = resolve_seminf_open_siblings(
                closed_path, year=year, month=month
            )
            comd_path = comd_path or auto_comd
            semd_path = semd_path or auto_semd
            if comd_path and semd_path:
                emit(8, "parse", "ComD e SemD detectados na pasta da Tabela de Preço…")

        from pricing.budget.seminf_base_parser import validate_seminf_bundle_period

        bundle_paths = [p for p in (closed_path, comd_path, semd_path) if p]
        if year and month and len(bundle_paths) >= 3:
            validate_seminf_bundle_period(bundle_paths, year=year, month=month)

        from pricing.budget.price_bank_store import CompositionClosed, PriceBankStore
        from pricing.budget.seminf_base_parser import (
            build_tp2_index_from_workbook,
            extract_seminf_base_compositions,
            infer_seminf_reference,
        )
        from pricing.budget.seminf_open_parser import (
            detect_seminf_open_desoneracao,
            merge_seminf_open_compositions,
            parse_seminf_open_workbook,
        )
        from pricing.sync.sinapi_parser import export_sinapi_csv

        region_uf = (uf or self._default_uf).upper()
        closed: list[CompositionClosed] = []
        meta: dict[str, Any] = {}
        tp2_index: dict[str, str] = {}
        ref_path = closed_path or comd_path or semd_path
        assert ref_path is not None

        if closed_path:
            if closed_path.suffix.lower() not in (".xlsm", ".xlsx", ".xls"):
                raise ValueError(f"Formato não suportado para Tabela de Preço: {closed_path.suffix}")
            emit(10, "parse", "Lendo Tabela de Preço SEMINF (fechadas, códigos regionais)…")
            row_dicts, meta = extract_seminf_base_compositions(closed_path, uf=region_uf)
            if not row_dicts:
                raise ValueError(
                    "Nenhuma composição regional SEMINF na aba Base — verifique códigos "
                    "terminados em .SEMINF (ex.: 107071.1.9.SEMINF)."
                )
            closed = [CompositionClosed(**row) for row in row_dicts]
            tp2_index = build_tp2_index_from_workbook(
                closed_path, sheet_name=str(meta.get("base_sheet") or "") or None
            )

        open_map: dict[str, Any] = {}
        open_meta: dict[str, Any] = {}
        if comd_path and semd_path:
            for path in (comd_path, semd_path):
                if path.suffix.lower() not in (".xlsx", ".xlsm", ".xls"):
                    raise ValueError(f"Formato não suportado para composição aberta: {path.suffix}")

            comd_role = detect_seminf_open_desoneracao(comd_path)
            semd_role = detect_seminf_open_desoneracao(semd_path)
            if comd_role == "semd" and semd_role == "comd":
                comd_path, semd_path = semd_path, comd_path
                comd_role, semd_role = semd_role, comd_role
            elif comd_role == "semd" or semd_role == "comd":
                raise ValueError(
                    "Arquivos ComD/SemD parecem invertidos — verifique os nomes "
                    "(Composicao-Seminf-*-ComD e *-SemD)."
                )

            emit(28, "parse", "Lendo composições abertas SEMINF (ComD)…")
            comd_map = parse_seminf_open_workbook(comd_path)
            emit(38, "parse", "Lendo composições abertas SEMINF (SemD)…")
            semd_map = parse_seminf_open_workbook(semd_path)
            if not comd_map and not semd_map:
                raise ValueError(
                    "Nenhuma composição aberta SEMINF (Banco Próprio) nas planilhas CPUs."
                )
            emit(48, "parse", "Mesclando CPUs ComD + SemD…")
            from pricing.budget.sinapi_as_index import load_sinapi_as_index_for_period

            sinapi_as_index = load_sinapi_as_index_for_period(
                year=year or meta.get("sheet_year"),
                month=month or meta.get("sheet_month"),
                uf=region_uf,
            )
            open_map = merge_seminf_open_compositions(
                comd_map,
                semd_map,
                tp2_index=tp2_index,
                sinapi_as_index=sinapi_as_index,
            )
            open_meta = {
                "open_comd_file": str(comd_path.resolve()),
                "open_semd_file": str(semd_path.resolve()),
                "open_comd_codes": len(comd_map),
                "open_semd_codes": len(semd_map),
                "open_merged_codes": len(open_map),
                "tp2_index_size": len(tp2_index),
                "sinapi_as_index_size": len(sinapi_as_index),
            }

        if not closed and not open_map:
            raise ValueError("Nenhuma composição SEMINF importada (fechada ou aberta).")

        ref_key = infer_seminf_reference(
            ref_path,
            base_sheet=str(meta.get("base_sheet") or ""),
            year=year or meta.get("sheet_year"),
            month=month or meta.get("sheet_month"),
            source_slug=self._source_slug,
        )

        if closed and not open_map:
            existing_open = PriceBankStore.for_reference(ref_key).load_open()
            if existing_open:
                raise ValueError(
                    f"A base {ref_key} já possui {len(existing_open)} composições abertas. "
                    "Esta importação só inclui a Tabela de Preço (fechadas) e apagaria as CPUs. "
                    "Use 'Selecionar pasta' com Tabela_Preco + ComD + SemD."
                )
            raise ValueError(
                "DP/SEMINF incompleto: composições abertas (ComD + SemD) não encontradas. "
                "Selecione a pasta com Tabela_Preco + Composicao-Seminf-ComD + SemD."
            )

        total_items = len(closed) + len(open_map)
        emit(55, "bank", f"Gravando {total_items:,} composições…".replace(",", "."))
        dest_dir.mkdir(parents=True, exist_ok=True)
        closed_rows = [c.to_dict() for c in closed]
        csv_path = dest_dir / f"{self.name}_{ref_key.replace('/', '-')}.csv"
        if closed_rows:
            export_sinapi_csv(closed_rows, csv_path)
        else:
            csv_path.write_text("code,description,unit,price\n", encoding="utf-8")

        bank_metadata = {
            "publisher": meta.get("publisher", "SEMINF-AM"),
            "region": meta.get("region", "Manaus/Amazonas"),
            "base_sheet": meta.get("base_sheet"),
            "base_items": meta.get("base_items"),
            "seminf_regional_codes": meta.get("seminf_regional_codes", len(closed)),
            "sinapi_codes_skipped": meta.get("sinapi_codes_skipped"),
            "import_filter": meta.get("import_filter", "seminf_only"),
            "workbook_format": meta.get("workbook_format"),
            "source_file": str(closed_path.resolve()) if closed_path else None,
            "year": year or meta.get("sheet_year"),
            "month": month or meta.get("sheet_month"),
            "import_mode": "bundle" if open_map else "base_sheet_closed",
            **open_meta,
        }

        labor_charges: dict[str, Any] = {}
        try:
            sinapi_ref = f"BR-{int(year or meta.get('sheet_year'))}-{int(month or meta.get('sheet_month')):02d}"
            labor_charges = PriceBankStore.for_reference(sinapi_ref).load_labor_charges()
        except (TypeError, ValueError, OSError):
            labor_charges = {}

        manifest = PriceBankStore.for_reference(ref_key).save_bank(
            source=self.name,
            reference=ref_key,
            closed=closed,
            open_compositions=open_map,
            insumos=[],
            uf=region_uf,
            desonerado=True,
            labor_charges=labor_charges or None,
            metadata=bank_metadata,
            set_active=set_active,
        )
        emit(65, "bank", "Banco de preços salvo")

        return DownloadResult(
            source=self.name,
            local_path=csv_path,
            reference=ref_key,
            item_count=len(closed) or len(open_map),
            metadata={
                "reference": ref_key,
                "uf": region_uf,
                "bank": manifest.to_dict(),
                "compositions_closed": manifest.counts.get("compositions_closed", 0),
                "compositions_open": manifest.counts.get("compositions_open", 0),
                "insumos": 0,
                "open_items_total": manifest.counts.get("open_items_total", 0),
                "base_sheet": meta.get("base_sheet"),
                "import_mode": bank_metadata.get("import_mode"),
            },
        )


class DpSeminfConnector(PpdSeminfConnector):
    """Alias custom registry — mesma planilha DP/SEMINF, fonte dp_seminf."""

    name = "dp_seminf"
    label = "DP/SEMINF"
    _source_slug = "DP-SEMINF"


class CustomUploadConnector(BasePriceConnector):
    """Upload tabular genérico para tipos de base cadastrados pelo usuário."""

    def __init__(self, name: str, label: str) -> None:
        self.name = name
        self.label = label

    def supports_auto_download(self) -> bool:
        return False

    def download(
        self,
        *,
        dest_dir: Path,
        local_file: Path | None = None,
        year: int | None = None,
        month: int | None = None,
        uf: str = "SP",
        on_progress: Any | None = None,
        set_active: bool = False,
        **_: Any,
    ) -> DownloadResult:
        def emit(pct: int, phase: str, msg: str) -> None:
            if on_progress:
                on_progress({"percent": pct, "phase": phase, "message": msg})

        path = Path(local_file) if local_file else None
        if not path or not path.is_file():
            raise FileNotFoundError(f"Informe arquivo local para importar {self.label}.")

        from pricing.budget.price_bank_store import CompositionClosed, PriceBankStore
        from pricing.providers._tabular import parse_tabular_file

        emit(15, "parse", f"Lendo {path.name}…")
        rows = parse_tabular_file(path)
        if not rows:
            raise ValueError(f"Nenhum item parseado em {path.name}")

        closed = [
            CompositionClosed(
                code=str(r["code"]),
                description=str(r.get("description") or ""),
                unit=str(r.get("unit") or "un"),
                price=float(r.get("price") or 0),
            )
            for r in rows
        ]

        slug = self.name.upper().replace("-", "_")
        if year and month:
            ref_key = f"BR-{slug}-{year}-{month:02d}"
        else:
            ref_key = f"BR-{slug}-{path.stem}"

        emit(45, "bank", f"Gravando {len(closed):,} composições…".replace(",", "."))
        dest_dir.mkdir(parents=True, exist_ok=True)
        csv_path = dest_dir / f"{self.name}_{path.stem}.csv"
        export_sinapi_csv([c.to_dict() for c in closed], csv_path)

        manifest = PriceBankStore.for_reference(ref_key).save_bank(
            source=self.name,
            reference=ref_key,
            closed=closed,
            open_compositions={},
            insumos=[],
            uf=uf.upper(),
            desonerado=True,
            metadata={"source_file": str(path.resolve()), "year": year, "month": month},
            set_active=set_active,
        )
        emit(65, "bank", "Banco de preços salvo")

        return DownloadResult(
            source=self.name,
            local_path=csv_path,
            reference=ref_key,
            item_count=len(closed),
            metadata={
                "reference": ref_key,
                "bank": manifest.to_dict(),
                "compositions_closed": manifest.counts.get("compositions_closed", 0),
                "compositions_open": 0,
                "insumos": 0,
                "open_items_total": 0,
            },
        )


CONNECTORS: dict[str, BasePriceConnector] = {
    SinapiConnector.name: SinapiConnector(),
    OrseConnector.name: OrseConnector(),
    TcpoConnector.name: TcpoConnector(),
    CicroConnector.name: CicroConnector(),
    PpdSeminfConnector.name: PpdSeminfConnector(),
    DpSeminfConnector.name: DpSeminfConnector(),
}


def get_connector(name: str) -> BasePriceConnector:
    key = name.lower()
    connector = CONNECTORS.get(key)
    if connector:
        return connector
    from pricing.sync.source_registry import get_source_registry

    profile = get_source_registry().get(key)
    if profile and profile.custom:
        return CustomUploadConnector(profile.name, profile.label)
    known = sorted(set(CONNECTORS) | {p.name for p in get_source_registry().list_custom()})
    raise ValueError(f"Conector desconhecido: {name}. Disponíveis: {known}")


def is_known_source(name: str) -> bool:
    key = name.lower()
    if key in CONNECTORS:
        return True
    from pricing.sync.source_registry import get_source_registry

    return get_source_registry().is_custom(key)


def list_all_source_names() -> list[str]:
    from pricing.sync.source_registry import get_source_registry

    names = set(CONNECTORS.keys())
    names.update(p.name for p in get_source_registry().list_custom())
    return sorted(names)
