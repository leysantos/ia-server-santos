"""Testes do módulo Norm Pack Studio (gap analysis legal)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.knowledge.norm_packs.presets import NORM_PACKS, get_norm_pack
from core.knowledge.norm_packs.service import NormPackService


def test_list_norm_packs_includes_legal_notice():
    data = NormPackService().list_packs()
    assert "legal_notice" in data
    assert "ABNT" in data["legal_notice"]
    assert len(data["packs"]) == len(NORM_PACKS)


def test_get_unknown_pack_raises():
    with pytest.raises(ValueError, match="desconhecido"):
        get_norm_pack("pacote_inexistente")


def test_discipline_packs_cover_agents():
    from core.knowledge.norm_packs.presets import NORM_PACKS

    expected_slugs = {
        "disc_arquitetura",
        "disc_estruturas",
        "disc_hidrossanitario",
        "disc_drenagem",
        "disc_eletrica",
        "disc_telecom",
        "disc_incendio",
        "disc_geotecnia",
        "disc_transportes",
        "disc_infraestrutura",
        "disc_saneamento",
        "disc_topografia",
    }
    assert expected_slugs.issubset(set(NORM_PACKS.keys()))


def test_analyze_pack_missing_items():
    svc = NormPackService()
    with patch("core.knowledge.norm_packs.service._chunk_nbr_codes", return_value={}):
        with patch("core.knowledge.norm_packs.service.read_catalog", return_value=[]):
            with patch("core.knowledge.norm_packs.service._disk_by_nbr", return_value={}):
                result = svc.analyze_pack("documentacao_projetos")
    assert result["pack_id"] == "documentacao_projetos"
    assert result["summary"]["missing"] == result["summary"]["total"]
    assert all(i["legal_source"] == "missing" for i in result["items"])


def test_analyze_pack_indexed_when_chunks_present():
    svc = NormPackService()
    pack = get_norm_pack("disc_estruturas")
    codes = {item.nbr_code for item in pack.items}
    chunk_counts = {code: 5 for code in codes}

    with patch("core.knowledge.norm_packs.service._chunk_nbr_codes", return_value=chunk_counts):
        with patch("core.knowledge.norm_packs.service.read_catalog", return_value=[]):
            with patch("core.knowledge.norm_packs.service._disk_by_nbr", return_value={}):
                result = svc.analyze_pack("disc_estruturas")

    assert result["summary"]["indexed"] == len(pack.items)
    assert result["summary"]["coverage_pct"] == 100.0


def test_index_pack_skips_missing():
    svc = NormPackService()
    with patch.object(svc, "analyze_pack") as mock_analyze:
        mock_analyze.return_value = {
            "items": [
                {
                    "nbr_code": "8196",
                    "status": "missing",
                    "chunk_count": 0,
                    "discipline": "DOCUMENTACAO",
                    "legal_source": "missing",
                    "file_path": None,
                }
            ],
            "summary": {
                "total": 1,
                "indexed": 0,
                "not_indexed": 0,
                "missing": 1,
                "critical_missing": 1,
                "coverage_pct": 0.0,
            },
        }
        mock_store = MagicMock()
        with patch("core.knowledge.norm_packs.service.get_multi_index_store") as mock_multi:
            mock_multi.return_value.get_store.return_value = mock_store
            mock_multi.return_value.embedder = MagicMock()
            result = svc.index_pack("documentacao_projetos")

    assert result["indexed_chunks"] == 0
    assert result["results"][0]["status"] == "missing"
    mock_store.save.assert_called_once()


def test_preview_pack_returns_indexed_chunks():
    from memory.models import DocumentChunk

    svc = NormPackService()
    chunk = DocumentChunk(
        text="Texto da norma sobre cotagem em desenho técnico.",
        source="NBR 10126",
        doc_type="nbr",
        page=3,
        metadata={"nbr_code": "10126", "filename": "NBR 10126.pdf", "legal_source": "abnt_licensed_pdf"},
    )
    mock_store = MagicMock()
    mock_store.chunks = [chunk]

    with patch("core.knowledge.norm_packs.service.get_multi_index_store") as mock_multi:
        mock_multi.return_value.get_store.return_value = mock_store
        with patch.object(svc, "analyze_pack") as mock_analyze:
            mock_analyze.return_value = {
                "items": [
                    {
                        "nbr_code": "10126",
                        "title": "Cotagem",
                        "status": "indexed",
                        "chunk_count": 1,
                        "filename": "NBR 10126.pdf",
                        "legal_source": "abnt_licensed_pdf",
                    }
                ],
            }
            result = svc.preview_pack("documentacao_projetos", nbr_code="10126")

    assert result["indexed_count"] == 1
    assert result["items"][0]["chunks"][0]["text"].startswith("Texto da norma")
    assert result["items"][0]["chunks"][0]["page"] == 3


def test_preview_pack_uses_latest_edition():
    from memory.models import DocumentChunk

    from core.knowledge.norm_packs.service import _chunks_for_nbr

    old_chunk = DocumentChunk(
        text="Texto da edição 1980.",
        source="NBR 6118 - 1980",
        doc_type="nbr",
        page=1,
        metadata={
            "nbr_code": "6118",
            "filename": "NBR 6118 - 1980 - Projeto.pdf",
            "edition_year": 1980,
        },
    )
    new_chunk = DocumentChunk(
        text="Texto da edição 2014.",
        source="NBR 6118 - 2014",
        doc_type="nbr",
        page=2,
        metadata={
            "nbr_code": "6118",
            "filename": "NBR 6118 - 2014 - Projeto.pdf",
            "edition_year": 2014,
        },
    )
    mock_store = MagicMock()
    mock_store.chunks = [old_chunk, new_chunk]

    with patch("core.knowledge.norm_packs.service.get_multi_index_store") as mock_multi:
        mock_multi.return_value.get_store.return_value = mock_store
        previews = _chunks_for_nbr("6118")

    assert len(previews) == 1
    assert "2014" in previews[0]["text"]
    assert previews[0]["edition_year"] == 2014
    assert "1980" not in previews[0]["text"]


def test_disk_by_nbr_picks_latest_edition(tmp_path: Path):
    from core.knowledge.norm_packs.service import _disk_by_nbr

    (tmp_path / "NBR 6118 - 1980 - Projeto.pdf").write_bytes(b"%PDF")
    latest = tmp_path / "NBR 6118 - 2014 - Projeto.pdf"
    latest.write_bytes(b"%PDF")

    by_code = _disk_by_nbr(tmp_path)
    assert by_code["6118"].name == latest.name


def test_catalog_by_nbr_picks_latest_edition():
    from core.knowledge.norm_packs.service import _catalog_by_nbr

    rows = [
        {
            "filename": "NBR 6118 - 1980 - Projeto.pdf",
            "path": "/knowledge/raw/documents/NBR 6118 - 1980 - Projeto.pdf",
            "catalog_ts": "2026-06-22T20:00:00",
        },
        {
            "filename": "NBR 6118 - 2014 - Projeto.pdf",
            "path": "/knowledge/raw/documents/NBR 6118 - 2014 - Projeto.pdf",
            "catalog_ts": "2026-06-20T10:00:00",
        },
    ]
    by_code = _catalog_by_nbr(rows)
    assert "2014" in by_code["6118"]["filename"]
