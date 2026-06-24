"""Testes — parser e portal SICRO DNIT."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pricing.sync.sicro_parser import infer_sicro_reference, parse_sicro_folder
from pricing.sync.sicro_portal_resolver import (
    build_month_page_url,
    month_folder,
    resolve_archive_on_page,
)


SICRO_SAMPLE = Path(__file__).resolve().parent.parent.parent / "bases-de-precos" / "am-01-2026"


def test_infer_sicro_reference_from_folder():
    uf, ref, year, month = infer_sicro_reference(SICRO_SAMPLE)
    assert uf == "AM"
    assert ref == "BR-SICRO-AM-2026-01"
    assert year == 2026
    assert month == 1


def test_parse_sicro_am_sample_folder():
    if not SICRO_SAMPLE.is_dir():
        return
    bank = parse_sicro_folder(SICRO_SAMPLE, uf="AM", desonerado=True)
    assert len(bank["closed"]) > 5000
    assert len(bank["insumos"]) > 2000
    assert len(bank["open"]) > 1000
    first = bank["closed"][0]
    assert first.code
    assert first.price > 0
    assert first.description


def test_parse_sicro_cpu_2003178_all_sections():
    if not SICRO_SAMPLE.is_dir():
        return
    from pricing.sync.sicro_parser import _pick_file, _parse_analytical_compositions

    path = _pick_file(SICRO_SAMPLE, "analítico de composições", exclude=("desoneração", "desoneracao"))
    assert path is not None
    comp = _parse_analytical_compositions(path).get("2003178")
    assert comp is not None
    types = {i.item_type for i in comp.items}
    assert "mao_obra" in types
    assert "atividade" in types
    assert "tempo_fixo" in types
    assert len(comp.items) >= 8
    assert comp.total_price == 408.51
    assert any(i.code == "4805756" for i in comp.items)


def test_parse_sicro_open_has_items():
    if not SICRO_SAMPLE.is_dir():
        return
    bank = parse_sicro_folder(SICRO_SAMPLE, uf="AM")
    comp = bank["open"].get("0307731")
    assert comp is not None
    assert comp.items
    assert comp.total_price > 0
    types = {i.item_type for i in comp.items}
    assert "mao_obra" in types or "insumo" in types


def test_month_folder_quarterly():
    assert month_folder(1) == "janeiro"
    assert month_folder(4) == "abril"
    assert month_folder(7) == "julho"
    assert month_folder(10) == "outubro"


def test_build_month_page_url_amazonas():
    url = build_month_page_url(
        region="norte",
        state_slug="amazonas",
        year=2026,
        month=1,
    )
    assert "norte/amazonas/2026/janeiro/janeiro-2026" in url


def test_resolve_archive_on_page_amazonas():
    url = build_month_page_url(
        region="norte",
        state_slug="amazonas",
        year=2026,
        month=1,
    )
    link = resolve_archive_on_page(url)
    assert link is not None
    assert link.uf == "AM"
    assert link.filename.startswith("am-01-2026")
    assert link.reference == "BR-SICRO-AM-2026-01"


def test_list_imported_sicro_ufs_filters_period(tmp_path, monkeypatch):
    from pricing.budget.price_bank_index import PriceBankIndex, PriceBankReferenceEntry
    from pricing.budget.price_bank_store import CLOSED_NAME, PriceBankStore
    from pricing.sync.sicro_portal_resolver import list_imported_sicro_ufs, sicro_reference_key

    ref_am = sicro_reference_key("AM", 2026, 1)
    ref_sp = sicro_reference_key("SP", 2026, 4)
    store_am = PriceBankStore.for_reference(ref_am)
    store_am.root.mkdir(parents=True, exist_ok=True)
    (store_am.root / CLOSED_NAME).write_text("[]", encoding="utf-8")
    store_am.manifest_path.write_text(
        '{"source":"cicro","reference":"' + ref_am + '","uf":"AM","desonerado":true,"synced_at":"x","counts":{},"metadata":{}}',
        encoding="utf-8",
    )

    idx = PriceBankIndex.load()
    idx.references = [
        PriceBankReferenceEntry(
            reference=ref_am,
            source="cicro",
            synced_at="x",
            default_uf="AM",
            counts={"compositions_closed": 1},
        ),
        PriceBankReferenceEntry(
            reference=ref_sp,
            source="cicro",
            synced_at="x",
            default_uf="SP",
            counts={"compositions_closed": 1},
        ),
    ]
    idx.save()

    imported = list_imported_sicro_ufs(year=2026, month=1)
    assert imported == {"AM"}


def test_download_archive_retries_on_incomplete_read(tmp_path, monkeypatch):
    from http.client import IncompleteRead
    from unittest.mock import MagicMock

    from pricing.sync.sicro_portal_resolver import SicroArchiveLink, download_archive

    link = SicroArchiveLink(
        url="https://example.test/am-01-2026.7z",
        filename="am-01-2026.7z",
        uf="AM",
        year=2026,
        month=1,
        region="norte",
        state_slug="amazonas",
    )
    payload = b"x" * 4096
    calls = {"n": 0}

    class FakeResponse:
        def __init__(self, body: bytes, *, fail_stream: bool):
            self.status_code = 200
            self.headers = {"Content-Length": str(len(body))}
            self._body = body
            self._fail_stream = fail_stream

        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size=0):
            if self._fail_stream:
                raise IncompleteRead(b"partial", len(self._body))
            yield self._body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    session = MagicMock()

    def fake_get(*_args, **_kwargs):
        calls["n"] += 1
        fail = calls["n"] == 1
        return FakeResponse(payload, fail_stream=fail)

    session.get.side_effect = fake_get
    monkeypatch.setattr("pricing.sync.sicro_portal_resolver.time.sleep", lambda _s: None)
    out = download_archive(link, tmp_path, session=session)
    assert out.exists()
    assert out.read_bytes() == payload
    assert calls["n"] == 2
