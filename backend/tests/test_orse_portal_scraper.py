"""Testes do scraper do portal CEHOP ORSE."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pricing.sync.connectors import OrseConnector
from pricing.sync.orse_portal_scraper import OrsePortalScraper, _parse_br_number


def test_parse_br_number():
    assert _parse_br_number("14,00") == 14.0
    assert _parse_br_number("25.349,44") == 25349.44
    assert _parse_br_number("250,32") == 250.32


SAMPLE_COMPOSITION_HTML = """
<td class="CorpoTabela">00123/ORSE</td>
<td class="CorpoTabela">Forma curva para estruturas</td>
<img src="imagens/insumo.gif" width="16" height="16">
<td class="CorpoTabela">01569/ORSE</td>
<td class="CorpoTabela">Madeira mista serrada</td>
<td class="CorpoTabela"><div align="center">m</div></td>
<td class="CorpoTabela"><div align="right">1,2</div></td>
<td class="CorpoTabela"><div align="right">6,69</div></td>
<td class="CorpoTabela"><div align="right">8,03</div></td>
<font color="#FF0000">250,32</font>
"""

SAMPLE_SERVICE_SEARCH_HTML = """
<a href="composicao.asp?serv_nr_codigo=123">Forma curva</a></td>
<td><div align="center"><a href="#">m2</a></div></td>
<td><div align="right"><a href="#">250,32</a></div></td>
"""

SAMPLE_INSUMO_HTML = """
<td class="CorpoTabela">08792/ORSE</td>
<td class="CorpoTabela">Equipamento de sondagem</td>
<td class="CorpoTabela"><div align="center">un</div></td>
<td class="CorpoTabela"><div align="right">1.234,56</div></td>
"""


def test_fetch_open_composition_parses_items():
    scraper = OrsePortalScraper(year=2026, month=4, delay_s=0)
    with patch.object(scraper, "_get_text", return_value=SAMPLE_COMPOSITION_HTML):
        comp = scraper.fetch_open_composition("123")
    assert comp is not None
    assert comp.code == "00123/ORSE"
    assert comp.description == "Forma curva para estruturas"
    assert comp.total_price == 250.32
    assert len(comp.items) == 1
    assert comp.items[0].code == "01569/ORSE"
    assert comp.items[0].coefficient == 1.2


def test_search_services_in_group():
    scraper = OrsePortalScraper(year=2026, month=4, delay_s=0)
    with patch.object(scraper, "_post_text", return_value=SAMPLE_SERVICE_SEARCH_HTML):
        hits = scraper.search_services_in_group("45")
    assert len(hits) == 1
    assert hits[0].serv_nr_codigo == "123"
    assert hits[0].price == 250.32


def test_search_insumos_in_group():
    scraper = OrsePortalScraper(year=2026, month=4, delay_s=0)
    with patch.object(scraper, "_post_text", return_value=SAMPLE_INSUMO_HTML):
        rows = scraper.search_insumos_in_group("5")
    assert len(rows) == 1
    assert rows[0].code == "08792/ORSE"
    assert rows[0].price == 1234.56


@patch.object(OrsePortalScraper, "discover_insumos")
@patch.object(OrsePortalScraper, "fetch_open_composition")
@patch.object(OrsePortalScraper, "discover_services")
def test_build_bundle(mock_discover, mock_fetch, mock_insumos):
    from pricing.budget.price_bank_store import CompositionOpen, InsumoRecord

    mock_discover.return_value = {
        "123": MagicMock(
            serv_nr_codigo="123",
            description="Forma curva",
            unit="m2",
            price=250.32,
        )
    }
    mock_fetch.return_value = CompositionOpen(
        code="00123/ORSE",
        description="Forma curva",
        unit="m2",
        total_price=250.32,
        total_price_sem=250.32,
        items=[],
    )
    mock_insumos.return_value = {
        "08792/ORSE": InsumoRecord(
            code="08792/ORSE",
            description="Equipamento",
            unit="un",
            price=100.0,
            price_sem_desoneracao=100.0,
            origin="ORSE",
        )
    }

    bundle = OrsePortalScraper(year=2026, month=4, delay_s=0).build_bundle()
    assert len(bundle.closed) == 1
    assert bundle.closed[0].code == "00123/ORSE"
    assert len(bundle.open_map) == 1
    assert len(bundle.insumos) == 1
    assert bundle.metadata.get("import_mode") == "orse_portal"


@patch.object(OrseConnector, "download_from_portal")
def test_orse_connector_portal_flag(mock_portal, tmp_path):
    mock_portal.return_value = MagicMock(reference="BR-ORSE-2026-04", item_count=1)
    connector = OrseConnector()
    connector.download(
        dest_dir=tmp_path,
        year=2026,
        month=4,
        portal_sync=True,
    )
    mock_portal.assert_called_once()
