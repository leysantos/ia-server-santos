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
    ORSE (Sergipe) — sem API pública tabular.
    Use `local_file` apontando para CSV/XLSX exportado do ORSE ou
    ORSE_EXPORT_PATH no ambiente.
    """

    name = "orse"
    label = "ORSE (Sergipe)"

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

        path = local_file or Path(os.environ.get("ORSE_EXPORT_PATH", ""))
        if not path.is_file():
            raise FileNotFoundError(
                "ORSE não possui download HTTP público. "
                "Exporte composições/insumos do ORSE (CSV/XLSX) e informe "
                "local_file ou ORSE_EXPORT_PATH."
            )

        from pricing.providers._tabular import parse_tabular_file

        dest_dir.mkdir(parents=True, exist_ok=True)
        rows = parse_tabular_file(path)
        if not rows:
            raise ValueError(f"Nenhum item parseado em {path.name}")

        from pricing.sync.sinapi_parser import export_sinapi_csv

        ref = path.stem
        csv_path = dest_dir / f"orse_{ref}.csv"
        export_sinapi_csv(rows, csv_path)
        return DownloadResult(
            source=self.name,
            local_path=csv_path,
            reference=ref,
            item_count=len(rows),
            metadata={"source_file": str(path.resolve())},
        )


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
        return False

    def download(
        self,
        *,
        dest_dir: Path,
        local_file: Path | None = None,
        **_: Any,
    ) -> DownloadResult:
        import os

        path = local_file or Path(os.environ.get("CICRO_EXPORT_PATH", ""))
        if not path.is_file():
            raise FileNotFoundError(
                "Informe local_file ou CICRO_EXPORT_PATH com planilha SICRO/CICRO."
            )

        from pricing.providers._tabular import parse_tabular_file
        from pricing.sync.sinapi_parser import export_sinapi_csv

        dest_dir.mkdir(parents=True, exist_ok=True)
        rows = parse_tabular_file(path)
        csv_path = dest_dir / f"cicro_{path.stem}.csv"
        export_sinapi_csv(rows, csv_path)
        return DownloadResult(
            source=self.name,
            local_path=csv_path,
            reference=path.stem,
            item_count=len(rows),
            metadata={"source_file": str(path.resolve())},
        )


class PpdSeminfConnector(BasePriceConnector):
    """PPD/SEMINF Manaus — planilha regional (.xlsm) com códigos SINAPI e preços locais."""

    name = "ppd_seminf"
    label = "PPD / SEMINF (Manaus-AM)"

    def supports_auto_download(self) -> bool:
        return False

    def download(
        self,
        *,
        dest_dir: Path,
        local_file: Path | None = None,
        year: int | None = None,
        month: int | None = None,
        on_progress: Any | None = None,
        set_active: bool = False,
        **_: Any,
    ) -> DownloadResult:
        def emit(pct: int, phase: str, msg: str) -> None:
            if on_progress:
                on_progress({"percent": pct, "phase": phase, "message": msg})

        path = Path(local_file) if local_file else None
        if not path or not path.is_file():
            raise FileNotFoundError(
                "PPD/SEMINF requer arquivo local — exporte a planilha MC_OR (.xlsm/.xlsx)."
            )
        if path.suffix.lower() not in (".xlsm", ".xlsx", ".xls"):
            raise ValueError(f"Formato não suportado para PPD/SEMINF: {path.suffix}")

        from core.knowledge.regional_budget_indexer import extract_regional_budget_model
        from pricing.budget.price_bank_store import CompositionClosed, PriceBankStore

        emit(12, "parse", "Lendo planilha PPD/SEMINF…")
        model = extract_regional_budget_model(path)
        if model.get("error"):
            raise ValueError(
                f"Falha ao interpretar planilha: {model.get('error')} "
                f"({model.get('service_count', 0)} serviços)"
            )

        closed: list[CompositionClosed] = []
        for etapa in model.get("etapas") or []:
            for svc in etapa.get("services") or []:
                code = str(svc.get("sinapi_code") or svc.get("code") or "").strip()
                if not code:
                    continue
                price = float(svc.get("unit_price") or 0)
                closed.append(
                    CompositionClosed(
                        code=code,
                        description=str(svc.get("description") or ""),
                        unit=str(svc.get("unit") or "un"),
                        price=price,
                        price_sem_desoneracao=price,
                        regional={"AM": {"comd": price, "semd": price}},
                    )
                )
        if not closed:
            raise ValueError("Nenhum serviço com código detectado na planilha PPD/SEMINF")

        if year and month:
            ref_key = f"BR-SEMINF-{year}-{month:02d}"
        else:
            ref_key = f"BR-SEMINF-{path.stem}"

        emit(45, "bank", f"Gravando {len(closed):,} composições…".replace(",", "."))
        dest_dir.mkdir(parents=True, exist_ok=True)
        from pricing.sync.sinapi_parser import export_sinapi_csv

        closed_rows = [c.to_dict() for c in closed]
        csv_path = dest_dir / f"ppd_seminf_{ref_key.replace('/', '-')}.csv"
        export_sinapi_csv(closed_rows, csv_path)

        manifest = PriceBankStore.for_reference(ref_key).save_bank(
            source=self.name,
            reference=ref_key,
            closed=closed,
            open_compositions={},
            insumos=[],
            uf="AM",
            desonerado=True,
            metadata={
                "publisher": model.get("publisher", "SEMINF-AM"),
                "region": model.get("region", "Manaus/Amazonas"),
                "projeto": model.get("projeto", path.stem),
                "source_file": str(path.resolve()),
                "year": year,
                "month": month,
            },
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
                "uf": "AM",
                "bank": manifest.to_dict(),
                "compositions_closed": manifest.counts.get("compositions_closed", 0),
                "compositions_open": 0,
                "insumos": 0,
                "open_items_total": 0,
            },
        )


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
