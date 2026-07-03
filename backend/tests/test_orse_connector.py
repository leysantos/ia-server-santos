"""ORSE connector and export parser tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pricing.budget.orse_bundle_detect import (
    classify_orse_bundle_files,
    detect_orse_bundle_from_paths,
    is_foreign_price_base_file,
    is_orse_composicoes_file,
)
from pricing.sync.connectors import OrseConnector
from pricing.sync.orse_export_parser import parse_orse_export_bundle


def test_orse_monthly_url_april_2026():
    assert OrseConnector.monthly_filename(year=2026, month=4) == "20260401-00.ORSE"
    assert (
        OrseConnector.monthly_download_url(year=2026, month=4)
        == "https://orse.cehop.se.gov.br/downloads/20260401-00.ORSE"
    )


def test_orse_bundle_detect_names(tmp_path: Path):
    ins = tmp_path / "Insumos_ORSE_abril.xlsx"
    comp = tmp_path / "Composicoes_ORSE_abril.xlsx"
    ana = tmp_path / "Analitico_ORSE_abril.xlsx"
    ins.write_bytes(b"x")
    comp.write_bytes(b"x")
    ana.write_bytes(b"x")
    classified = classify_orse_bundle_files([ins, comp, ana])
    assert classified["insumos"] is not None
    assert classified["composicoes"] is not None
    assert classified["analitico"] is not None


def test_orse_bundle_rejects_seminf_composicoes(tmp_path: Path):
    seminf = tmp_path / "open_comd_Composicao-Seminf-Abril2026-ComD.xlsx"
    seminf.write_bytes(b"x")
    assert is_foreign_price_base_file(seminf) is True
    assert is_orse_composicoes_file(seminf) is False
    classified = classify_orse_bundle_files([seminf])
    assert classified["composicoes"] is None


def test_orse_bundle_detect_error_without_composicoes():
    result = detect_orse_bundle_from_paths([Path("Insumos.xlsx")])
    assert "error" in result


def test_orse_parse_composicoes_csv(tmp_path: Path):
    comp = tmp_path / "composicoes.csv"
    comp.write_text(
        "codigo,descricao,unidade,preco\n1001,Alvenaria bloco,m2,88.10\n",
        encoding="utf-8",
    )
    ins = tmp_path / "insumos.csv"
    ins.write_text(
        "codigo,descricao,unidade,preco\n2001,Cimento CP II,kg,0.85\n",
        encoding="utf-8",
    )
    ana = tmp_path / "analitico.csv"
    ana.write_text(
        "codigo,descricao,unidade,preco,coeficiente\n"
        "1001,Servico teste,m2,88.10,0\n"
        "2001,Cimento,kg,0.85,1.5\n",
        encoding="utf-8",
    )
    bundle = parse_orse_export_bundle(
        composicoes_path=comp,
        insumos_path=ins,
        analitico_path=ana,
    )
    assert len(bundle.closed) == 1
    assert bundle.closed[0].code == "1001"
    assert len(bundle.insumos) == 1
    assert bundle.insumos[0].code == "2001"
    assert len(bundle.open_map) == 1


def test_orse_parse_rejects_seminf_codes(tmp_path: Path):
    comp = tmp_path / "composicoes.csv"
    comp.write_text(
        "codigo,descricao,unidade,preco\n97674.3.9.SEMINF,Demo,m2,10\n",
        encoding="utf-8",
    )
    ins = tmp_path / "insumos.csv"
    ins.write_text("codigo,descricao,unidade,preco\n2001,Cimento,kg,1\n", encoding="utf-8")
    ana = tmp_path / "analitico.csv"
    ana.write_text("codigo,descricao,unidade,preco\n1001,Serv,m2,10\n", encoding="utf-8")
    with pytest.raises(ValueError, match="SEMINF"):
        parse_orse_export_bundle(composicoes_path=comp, insumos_path=ins, analitico_path=ana)


@patch.object(OrseConnector, "_download_monthly_orse")
def test_orse_ingest_bundle(mock_dl: MagicMock, tmp_path: Path):
    mock_dl.return_value = tmp_path / "pkg.ORSE"
    mock_dl.return_value.write_bytes(b"x" * 2048)
    comp = tmp_path / "composicoes.csv"
    comp.write_text("codigo,descricao,unidade,preco\n1001,Servico,m2,10.0\n", encoding="utf-8")
    ins = tmp_path / "insumos.csv"
    ins.write_text("codigo,descricao,unidade,preco\n2001,Cimento,kg,1.0\n", encoding="utf-8")
    ana = tmp_path / "analitico.csv"
    ana.write_text(
        "codigo,descricao,unidade,preco,coeficiente\n"
        "1001,Servico,m2,10.0,0\n"
        "2001,Cimento,kg,1.0,1.5\n",
        encoding="utf-8",
    )
    connector = OrseConnector()
    result = connector.download(
        dest_dir=tmp_path / "cache",
        composicoes_file=comp,
        insumos_file=ins,
        analitico_file=ana,
        year=2026,
        month=4,
        uf="SE",
    )
    assert result.item_count == 1
    assert result.reference == "BR-ORSE-2026-04"
    assert result.metadata.get("compositions_closed") == 1
    assert result.metadata.get("insumos") == 1
    assert result.metadata.get("compositions_open") == 1


@patch.object(OrseConnector, "_download_monthly_orse")
def test_orse_package_only(mock_dl: MagicMock, tmp_path: Path):
    pkg = tmp_path / "20260401-00.ORSE"
    pkg.write_bytes(b"x" * 5000)
    mock_dl.return_value = pkg
    connector = OrseConnector()
    result = connector.download(
        dest_dir=tmp_path / "cache",
        year=2026,
        month=4,
        package_only=True,
    )
    assert result.item_count == 0
    assert result.metadata.get("package_only") is True
