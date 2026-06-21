"""Tests for catalog norm statistics."""

from pathlib import Path

from core.knowledge.catalog_stats import compute_norm_catalog_stats
from core.knowledge.metadata import write_metadata


def test_compute_norm_catalog_stats_editions(tmp_path: Path):
    rows = []
    for name in (
        "NBR 6118 - 2014 - Projeto.pdf",
        "NBR 6118 - 2001 - Projeto.pdf",
        "NBR 9050 - 2020 - Acessibilidade.pdf",
        "NR-10.pdf",
    ):
        pdf = tmp_path / name
        pdf.write_bytes(b"%PDF-1.4")
        meta = {"content_type": "nbrs"}
        if name.startswith("NBR 6118 - 2001"):
            meta["edition_outdated"] = True
            meta["norm_kind"] = "NBR"
            meta["nbr_code"] = "6118"
            meta["edition_year"] = 2001
        elif name.startswith("NBR 6118"):
            meta["norm_kind"] = "NBR"
            meta["nbr_code"] = "6118"
            meta["edition_year"] = 2014
        elif name.startswith("NBR 9050"):
            meta["norm_kind"] = "NBR"
            meta["nbr_code"] = "9050"
            meta["edition_year"] = 2020
        else:
            meta["norm_kind"] = "NR"
            meta["norm_code"] = "10"
        write_metadata(pdf, meta)
        rows.append(
            {
                "content_type": "nbrs",
                "path": str(pdf),
                "filename": name,
            }
        )

    stats = compute_norm_catalog_stats(rows)

    assert stats["total"] == 4
    assert stats["historical_count"] == 1
    assert stats["current_count"] == 3
    assert stats["nbr_count"] == 3
    assert stats["nr_count"] == 1
    assert stats["unique_codes"] == 2
    assert stats["multi_edition_codes"] == 1
    assert stats["unique_editions"] == 3
    assert stats["distinct_years"] == 3
