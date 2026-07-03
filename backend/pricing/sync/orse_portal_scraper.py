"""Importação ORSE via portal público CEHOP (orse.cehop.se.gov.br) — sem ORSE 2."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Callable

import requests

from pricing.budget.price_bank_store import (
    CompositionClosed,
    CompositionItem,
    CompositionOpen,
    InsumoRecord,
)
from pricing.sync.orse_export_parser import OrseExportBundle

logger = logging.getLogger(__name__)

_BASE_URL = "https://orse.cehop.se.gov.br"
_USER_AGENT = "Mozilla/5.0 (compatible; IAServerSantos/1.0; +https://github.com/leysantos/ia-server-santos)"
_DEFAULT_DELAY_S = 0.2

_RE_SERVICE_ROW = re.compile(
    r"serv_nr_codigo=(\d+)[^>]*>([^<]+)</a></td>\s*"
    r"<td[^>]*><div align=\"center\"><a[^>]*>([^<]+)</a></div></td>\s*"
    r"<td[^>]*><div align=\"right\"><a[^>]*>([^<]+)</a>",
    re.IGNORECASE | re.DOTALL,
)
_RE_INSUMO_ROW = re.compile(
    r"<td class=\"CorpoTabela\"[^>]*>\s*([^<]+/(?:ORSE|SINAPI))\s*</td>\s*"
    r"<td class=\"CorpoTabela\"[^>]*>([^<]+)</td>\s*"
    r"<td class=\"CorpoTabela\"[^>]*><div align=\"center\">([^<]+)</div></td>\s*"
    r"<td class=\"CorpoTabela\"[^>]*><div align=\"right\">([^<]+)</div></td>",
    re.IGNORECASE | re.DOTALL,
)
_RE_COMPOSITION_ITEM = re.compile(
    r"insumo\.gif.*?class=\"CorpoTabela\">([^<]+)</td>\s*"
    r"<td[^>]*class=\"CorpoTabela\">([^<]+)</td>\s*"
    r"<td[^>]*class=\"CorpoTabela\"[^>]*><div align=\"center\">([^<]+)</div></td>\s*"
    r"<td[^>]*class=\"CorpoTabela\"[^>]*><div align=\"right\">([^<]+)</div></td>\s*"
    r"<td[^>]*class=\"CorpoTabela\"[^>]*><div align=\"right\">([^<]+)</div></td>\s*"
    r"<td[^>]*class=\"CorpoTabela\"[^>]*><div align=\"right\">([^<]+)</div></td>",
    re.IGNORECASE | re.DOTALL,
)
_RE_COMPOSITION_CODE = re.compile(r'class="CorpoTabela"[^>]*>(\d+/ORSE)</td>', re.IGNORECASE)
_RE_COMPOSITION_DESC = re.compile(
    r'class="CorpoTabela"[^>]*>\d+/ORSE</td>\s*<td[^>]*class="CorpoTabela"[^>]*>([^<]+)</td>',
    re.IGNORECASE | re.DOTALL,
)
_RE_TOTAL_RED = re.compile(r'<font color="#FF0000">([^<]+)</font>', re.IGNORECASE)
_RE_SELECT_OPTIONS = re.compile(
    r'<option value="([^"]*)"[^>]*>([^<]*)</option>',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _ServiceHit:
    serv_nr_codigo: str
    description: str
    unit: str
    price: float


ProgressCb = Callable[[dict[str, Any]], None]


def _parse_br_number(value: str) -> float:
    text = (value or "").strip()
    if not text:
        return 0.0
    text = text.replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _normalize_code(raw: str) -> str:
    text = (raw or "").strip().upper()
    if "/" in text:
        return text
    digits = re.sub(r"\D", "", text)
    if not digits:
        return text
    return f"{int(digits):05d}/ORSE"


def _classify_item(code: str, description: str, unit: str) -> str:
    unit_u = unit.strip().upper()
    desc_l = description.lower()
    if unit_u == "H" or "horista" in desc_l or "pedreiro" in desc_l or "servente" in desc_l:
        return "mao_obra"
    if "equip" in desc_l:
        return "equipamento"
    if "/ORSE" in code.upper() or "/SINAPI" in code.upper():
        if re.match(r"^\d+/", code):
            return "insumo"
    return "insumo"


class OrsePortalScraper:
    """Crawler do portal CEHOP — composições fechadas, CPUs e insumos."""

    def __init__(
        self,
        *,
        year: int,
        month: int,
        ordem: int = 1,
        delay_s: float = _DEFAULT_DELAY_S,
        on_progress: ProgressCb | None = None,
    ) -> None:
        self.year = year
        self.month = month
        self.ordem = ordem
        self.delay_s = max(0.05, delay_s)
        self._on_progress = on_progress
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": _USER_AGENT})

    @property
    def period_value(self) -> str:
        return f"{self.year}-{self.month}-{self.ordem}"

    def _emit(self, pct: int, phase: str, message: str, *, current: int = 0, total: int = 0) -> None:
        if self._on_progress:
            self._on_progress(
                {
                    "percent": pct,
                    "phase": phase,
                    "message": message,
                    "current": current,
                    "total": total,
                }
            )

    def _get_text(self, path: str, *, params: dict[str, str] | None = None) -> str:
        url = f"{_BASE_URL}/{path.lstrip('/')}"
        resp = self._session.get(url, params=params, timeout=90)
        resp.raise_for_status()
        time.sleep(self.delay_s)
        return resp.content.decode("latin-1", errors="replace")

    def _post_text(self, path: str, data: dict[str, str]) -> str:
        url = f"{_BASE_URL}/{path.lstrip('/')}"
        resp = self._session.post(url, data=data, timeout=90)
        resp.raise_for_status()
        time.sleep(self.delay_s)
        return resp.content.decode("latin-1", errors="replace")

    def _select_options(self, html: str, select_name: str) -> list[tuple[str, str]]:
        match = re.search(
            rf'<select name="{re.escape(select_name)}"[^>]*>(.*?)</select>',
            html,
            re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return []
        return [(v.strip(), t.strip()) for v, t in _RE_SELECT_OPTIONS.findall(match.group(1)) if v.strip()]

    def list_service_groups(self) -> list[tuple[str, str]]:
        html = self._get_text("servicosargumento.asp")
        return [(v, t) for v, t in self._select_options(html, "sltGrupoServico") if v != "0"]

    def list_insumo_groups(self) -> list[tuple[str, str]]:
        html = self._get_text("insumosargumento.asp")
        return [(v, t) for v, t in self._select_options(html, "sltGrupoInsumo") if v != "0"]

    def search_services_in_group(self, group_id: str) -> list[_ServiceHit]:
        data = {
            "sltFonte": "ORSE",
            "sltPeriodo": self.period_value,
            "sltGrupoServico": group_id,
            "rdbCriterio": "2",
            "txtDescricao": "",
            "Submit": "Consultar",
        }
        html = self._post_text("servicosargumento.asp?tarefa=consultar", data)
        hits: list[_ServiceHit] = []
        for serv_id, desc, unit, price_raw in _RE_SERVICE_ROW.findall(html):
            price = _parse_br_number(price_raw)
            if price <= 0:
                continue
            hits.append(
                _ServiceHit(
                    serv_nr_codigo=serv_id,
                    description=desc.strip(),
                    unit=unit.strip() or "un",
                    price=price,
                )
            )
        return hits

    def discover_services(self) -> dict[str, _ServiceHit]:
        groups = self.list_service_groups()
        discovered: dict[str, _ServiceHit] = {}
        total_groups = len(groups)
        self._emit(5, "discover", f"Varrendo {total_groups} categorias de serviços…", total=total_groups)
        for idx, (gid, _label) in enumerate(groups, start=1):
            for hit in self.search_services_in_group(gid):
                if hit.serv_nr_codigo not in discovered:
                    discovered[hit.serv_nr_codigo] = hit
            if idx % 5 == 0 or idx == total_groups:
                pct = 5 + round(idx / max(total_groups, 1) * 25)
                self._emit(
                    pct,
                    "discover",
                    f"Categorias de serviços {idx}/{total_groups} — {len(discovered):,} composições".replace(",", "."),
                    current=idx,
                    total=total_groups,
                )
        return discovered

    def fetch_open_composition(self, serv_nr_codigo: str) -> CompositionOpen | None:
        params = {
            "font_sg_fonte": "ORSE",
            "serv_nr_codigo": serv_nr_codigo,
            "peri_nr_ano": str(self.year),
            "peri_nr_mes": str(self.month),
            "peri_nr_ordem": str(self.ordem),
        }
        html = self._get_text("composicao.asp", params=params)
        code_m = _RE_COMPOSITION_CODE.search(html)
        desc_m = _RE_COMPOSITION_DESC.search(html)
        total_m = _RE_TOTAL_RED.search(html)
        if not code_m or not desc_m:
            return None

        code = _normalize_code(code_m.group(1))
        description = desc_m.group(1).strip()
        total_price = _parse_br_number(total_m.group(1) if total_m else "0")

        items: list[CompositionItem] = []
        for raw_code, desc, unit, coef_raw, unit_price_raw, partial_raw in _RE_COMPOSITION_ITEM.findall(html):
            coef = _parse_br_number(coef_raw) or 1.0
            unit_price = _parse_br_number(unit_price_raw)
            partial = _parse_br_number(partial_raw) or (unit_price * coef)
            item_code = _normalize_code(raw_code) if "/" not in raw_code else raw_code.strip().upper()
            items.append(
                CompositionItem(
                    item_type=_classify_item(item_code, desc, unit),
                    code=item_code,
                    description=desc.strip(),
                    unit=unit.strip() or "un",
                    coefficient=coef,
                    unit_price=unit_price,
                    partial_cost=partial,
                    unit_price_sem=unit_price,
                    partial_cost_sem=partial,
                )
            )

        if total_price <= 0 and items:
            total_price = sum(i.partial_cost for i in items)

        return CompositionOpen(
            code=code,
            description=description,
            unit="un",
            total_price=total_price,
            total_price_sem=total_price,
            items=items,
        )

    def search_insumos_in_group(self, group_id: str) -> list[InsumoRecord]:
        data = {
            "sltFOnte": "ORSE",
            "sltPeriodo": self.period_value,
            "sltGrupoInsumo": group_id,
            "rdbCriterio": "2",
            "txtDescricao": "",
            "Submit": "Consultar",
        }
        html = self._post_text("insumosargumento.asp?tarefa=consultar", data)
        out: list[InsumoRecord] = []
        for code_raw, desc, unit, price_raw in _RE_INSUMO_ROW.findall(html):
            price = _parse_br_number(price_raw)
            if price <= 0:
                continue
            code = _normalize_code(code_raw) if "/" not in code_raw else code_raw.strip().upper()
            out.append(
                InsumoRecord(
                    code=code,
                    description=desc.strip(),
                    unit=unit.strip() or "un",
                    price=price,
                    price_sem_desoneracao=price,
                    origin="ORSE",
                )
            )
        return out

    def discover_insumos(self) -> dict[str, InsumoRecord]:
        groups = self.list_insumo_groups()
        insumos: dict[str, InsumoRecord] = {}
        total_groups = len(groups)
        self._emit(72, "insumos", f"Varrendo {total_groups} categorias de insumos…", total=total_groups)
        for idx, (gid, _label) in enumerate(groups, start=1):
            for ins in self.search_insumos_in_group(gid):
                insumos.setdefault(ins.code, ins)
            if idx % 10 == 0 or idx == total_groups:
                pct = 72 + round(idx / max(total_groups, 1) * 18)
                self._emit(
                    min(90, pct),
                    "insumos",
                    f"Insumos {idx}/{total_groups} — {len(insumos):,} itens".replace(",", "."),
                    current=idx,
                    total=total_groups,
                )
        return insumos

    def build_bundle(self) -> OrseExportBundle:
        services = self.discover_services()
        if not services:
            raise ValueError(
                f"Nenhum serviço ORSE encontrado para {self.month:02d}/{self.year} no portal CEHOP."
            )

        closed: list[CompositionClosed] = []
        open_map: dict[str, CompositionOpen] = {}
        serv_ids = sorted(services.keys(), key=lambda x: int(x))
        total_serv = len(serv_ids)

        self._emit(32, "cpu", f"Baixando CPUs — 0/{total_serv}…", current=0, total=total_serv)
        for idx, serv_id in enumerate(serv_ids, start=1):
            hit = services[serv_id]
            open_comp = self.fetch_open_composition(serv_id)
            if open_comp:
                code = open_comp.code
                open_comp.unit = hit.unit or open_comp.unit
                open_map[code] = open_comp
                price = hit.price if hit.price > 0 else open_comp.total_price
            else:
                code = _normalize_code(serv_id)
                price = hit.price

            closed.append(
                CompositionClosed(
                    code=code,
                    description=hit.description,
                    unit=hit.unit,
                    price=price,
                    price_sem_desoneracao=price,
                )
            )

            if idx % 25 == 0 or idx == total_serv:
                pct = 32 + round(idx / max(total_serv, 1) * 38)
                self._emit(
                    pct,
                    "cpu",
                    f"CPUs {idx}/{total_serv} — {len(open_map):,} abertas".replace(",", "."),
                    current=idx,
                    total=total_serv,
                )

        insumos_map = self.discover_insumos()

        # Enriquecer catálogo com insumos vistos nas CPUs (ex.: SINAPI referenciados)
        for comp in open_map.values():
            for item in comp.items:
                if item.code in insumos_map:
                    continue
                if item.unit_price <= 0:
                    continue
                insumos_map[item.code] = InsumoRecord(
                    code=item.code,
                    description=item.description,
                    unit=item.unit,
                    price=item.unit_price,
                    price_sem_desoneracao=item.unit_price,
                    origin="ORSE" if item.code.endswith("/ORSE") else "SINAPI",
                )

        if not open_map:
            raise ValueError("Portal CEHOP não retornou composições abertas (CPU).")
        if not insumos_map:
            raise ValueError("Portal CEHOP não retornou insumos.")

        return OrseExportBundle(
            closed=closed,
            open_map=open_map,
            insumos=list(insumos_map.values()),
            metadata={
                "import_mode": "orse_portal",
                "portal_base": _BASE_URL,
                "year": self.year,
                "month": self.month,
                "period": self.period_value,
            },
        )
