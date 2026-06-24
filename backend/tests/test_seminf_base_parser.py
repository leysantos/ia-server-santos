"""Testes importação base DP/SEMINF (aba Base_Mês-Ano, só códigos *.SEMINF)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TABELA_PRECO_XLSM = (
    Path(__file__).resolve().parents[2]
    / "bases-de-precos"
    / "DP-SEMINF"
    / "Tabela_Preco-Abril2026-10-06-2026.xlsm"
)
COMD_XLSX = (
    Path(__file__).resolve().parents[2]
    / "bases-de-precos"
    / "DP-SEMINF"
    / "Composicao-Seminf-Abril2026-ComD-10-06-2026.xlsx"
)
SEMD_XLSX = (
    Path(__file__).resolve().parents[2]
    / "bases-de-precos"
    / "DP-SEMINF"
    / "Composicao-Seminf-Abril2026-SemD-10-06-2026.xlsx"
)
MC_OR_XLSM = (
    Path(__file__).resolve().parents[2]
    / "bases-de-precos"
    / "DP-SEMINF"
    / "00_MOD_MC_OR_R00-Nivel-1-2-Abril2026-10-06-2026v8.1.xlsm"
)


def _fixture_xlsm() -> Path | None:
    if TABELA_PRECO_XLSM.exists():
        return TABELA_PRECO_XLSM
    if MC_OR_XLSM.exists():
        return MC_OR_XLSM
    return None
SINAPI_REF = "BR-2026-04"
PRICE_TOLERANCE = 0.02


def test_parse_base_sheet_period():
    from pricing.budget.seminf_base_parser import parse_base_sheet_period

    year, month = parse_base_sheet_period("Base_Abril-2026-copia")
    assert year == 2026
    assert month == 4

    year2, month2 = parse_base_sheet_period("Base_Março2026")
    assert year2 == 2026
    assert month2 == 3

    year3, month3 = parse_base_sheet_period("Tabela_Preco-Abril2026-10-06-2026")
    assert year3 == 2026
    assert month3 == 4


def test_detect_workbook_format():
    from pricing.budget.seminf_base_parser import detect_workbook_format

    assert detect_workbook_format(
        Path("Tabela_Preco-Abril2026.xlsm"),
        ["Base_Abril-2026-copia"],
    ) == "tabela_preco"
    assert detect_workbook_format(
        Path("00_MOD_MC_OR_R00.xlsm"),
        ["ETAPAS", "PLANILHA", "Base_Abril-2026-copia"],
    ) == "mc_or"


def test_pick_base_sheet_prefers_copia():
    from pricing.budget.seminf_base_parser import pick_base_sheet_name

    assert pick_base_sheet_name(["Base_Abril-2026-ORIGINAL", "Base_Abril-2026-copia"]) == (
        "Base_Abril-2026-copia"
    )


def test_is_seminf_regional_code():
    from pricing.budget.seminf_base_parser import is_seminf_regional_code, is_sinapi_national_code

    assert is_seminf_regional_code("107071.1.9.SEMINF")
    assert not is_seminf_regional_code("104658")
    assert is_sinapi_national_code("104658")
    assert not is_sinapi_national_code("107071.1.9.SEMINF")


def test_seminf_sinapi_price_parity_april_2026():
    """Códigos SINAPI na aba Base SEMINF devem bater com BR-2026-04 UF AM (Caixa)."""
    from pricing.budget.ppd_parser import extract_price_base_rows
    from pricing.budget.price_bank_store import PriceBankStore
    from pricing.budget.seminf_base_parser import is_seminf_regional_code, is_sinapi_national_code

    xlsm = _fixture_xlsm()
    if not xlsm:
        return
    ref_path = Path(__file__).resolve().parents[1] / "knowledge" / "price_bank" / SINAPI_REF
    if not ref_path.is_dir():
        return

    seminf_rows = extract_price_base_rows(xlsm)
    sinapi_sheet = {
        str(r["code"]).strip(): r
        for r in seminf_rows
        if is_sinapi_national_code(str(r.get("code") or ""))
    }

    store = PriceBankStore.for_reference(SINAPI_REF)
    bank = {}
    for row in store.load_closed():
        code = str(row.get("code", "")).strip()
        reg = row.get("regional") or {}
        if "AM" in reg:
            com = float(reg["AM"].get("comd") or reg["AM"].get("com") or 0)
            sem = float(reg["AM"].get("semd") or reg["AM"].get("sem") or com)
        else:
            com = float(row.get("price") or 0)
            sem = float(row.get("price_sem_desoneracao") or com)
        bank[code] = (com, sem)

    common = set(sinapi_sheet) & set(bank)
    assert len(common) >= 8000
    mismatches = 0
    for code in common:
        s = sinapi_sheet[code]
        s_com = float(s.get("price") or 0)
        s_sem = float((s.get("metadata") or {}).get("price_sem_desoneracao") or s_com)
        b_com, b_sem = bank[code]
        if abs(s_com - b_com) > PRICE_TOLERANCE or abs(s_sem - b_sem) > PRICE_TOLERANCE:
            mismatches += 1
    assert mismatches == 0

    seminf_count = sum(1 for r in seminf_rows if is_seminf_regional_code(str(r.get("code") or "")))
    assert seminf_count > 500


def test_extract_seminf_base_compositions_fixture():
    from pricing.budget.seminf_base_parser import extract_seminf_base_compositions

    xlsm = _fixture_xlsm()
    if not xlsm:
        return

    rows, meta = extract_seminf_base_compositions(xlsm)
    assert 500 < len(rows) < 900
    assert meta["base_sheet"] == "Base_Abril-2026-copia"
    assert meta["sheet_year"] == 2026
    assert meta["sheet_month"] == 4
    assert meta["import_filter"] == "seminf_only"
    if xlsm == TABELA_PRECO_XLSM:
        assert meta["workbook_format"] == "tabela_preco"
    assert meta["sinapi_codes_skipped"] > 8000
    assert all(".SEMINF" in r["code"].upper() for r in rows)
    assert rows[0]["price"] > 0
    assert rows[0]["regional"]["AM"]["comd"] > 0


def _bundle_fixtures() -> tuple[Path, Path, Path] | None:
    if TABELA_PRECO_XLSM.exists() and COMD_XLSX.exists() and SEMD_XLSX.exists():
        return TABELA_PRECO_XLSM, COMD_XLSX, SEMD_XLSX
    return None


def test_normalize_seminf_code():
    from pricing.budget.seminf_open_parser import normalize_seminf_code

    assert normalize_seminf_code(" 97674.3.9.SEMINF ") == "97674.3.9.SEMINF"
    assert normalize_seminf_code("100725.3.9SEMINF") == "100725.3.9.SEMINF"
    assert normalize_seminf_code("100320.1.9.SEMIINF") == "100320.1.9.SEMINF"


def test_parse_seminf_open_workbook_fixture():
    from pricing.budget.seminf_open_parser import parse_seminf_open_workbook

    if not COMD_XLSX.exists():
        return
    open_map = parse_seminf_open_workbook(COMD_XLSX)
    assert 500 < len(open_map) < 900
    sample = open_map["97674.3.9.SEMINF"]
    assert sample["total"] > 0
    assert len(sample["items"]) >= 2
    assert sample["items"][0]["unit_price"] > 0
    # composição com insumos SINAPI (ex. 100013)
    rich = open_map.get("100013.3.9.SEMINF")
    assert rich and len(rich["items"]) >= 5
    assert any(i.get("item_type") == "insumo" for i in rich["items"])


def test_merge_seminf_open_comd_semd_fixture():
    from pricing.budget.seminf_open_parser import (
        merge_seminf_open_compositions,
        parse_seminf_open_workbook,
    )

    if not COMD_XLSX.exists() or not SEMD_XLSX.exists():
        return
    comd = parse_seminf_open_workbook(COMD_XLSX)
    semd = parse_seminf_open_workbook(SEMD_XLSX)
    merged = merge_seminf_open_compositions(comd, semd)
    assert 500 < len(merged) < 900
    comp = merged["97674.3.9.SEMINF"]
    assert comp.total_price > 0
    assert comp.total_price_sem > comp.total_price
    assert comp.items[0].unit_price_sem >= comp.items[0].unit_price


def test_dp_seminf_bundle_import_fixture(tmp_path):
    from pricing.sync.connectors import DpSeminfConnector

    bundle = _bundle_fixtures()
    if not bundle:
        return
    closed, comd, semd = bundle

    connector = DpSeminfConnector()
    result = connector.download(
        dest_dir=tmp_path,
        local_file=closed,
        open_comd_file=comd,
        open_semd_file=semd,
        set_active=False,
    )
    assert 500 < result.metadata.get("compositions_closed", 0) < 900
    assert 500 < result.metadata.get("compositions_open", 0) < 900
    assert result.metadata.get("open_items_total", 0) > 1000
    assert result.reference == "BR-DP-SEMINF-2026-04"


def test_find_seminf_bundle_in_dir_fixture():
    from pricing.budget.seminf_bundle_detect import (
        classify_seminf_bundle_files,
        is_open_comd_file,
        is_tabela_preco_file,
        normalize_filename_token,
    )
    from pricing.budget.seminf_base_parser import find_seminf_bundle_in_dir

    assert normalize_filename_token("Composição-Seminf-Abril2026-ComD") == "composicaoseminfabril2026comd"
    assert normalize_filename_token("Tabela_Preços-Abril2026") == "tabelaprecosabril2026"
    assert is_tabela_preco_file(Path("Tabela_Preços-Abril2026.xlsm"))
    assert is_open_comd_file(Path("Composição-Seminf-Abril2026-ComD.xlsx"))

    folder = TABELA_PRECO_XLSM.parent
    if not folder.is_dir():
        return
    bundle = find_seminf_bundle_in_dir(folder, year=2026, month=4)
    assert bundle["closed"].name.startswith("Tabela_Preco")
    assert "ComD" in bundle["open_comd"].name
    assert "SemD" in bundle["open_semd"].name

    classified = classify_seminf_bundle_files(list(folder.glob("*")), year=2026, month=4)
    assert classified["closed"] is not None


def test_validate_seminf_bundle_period_mismatch():
    from pricing.budget.seminf_base_parser import validate_seminf_bundle_period

    if not TABELA_PRECO_XLSM.exists():
        return
    try:
        validate_seminf_bundle_period([TABELA_PRECO_XLSM], year=2025, month=1)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "2026" in str(exc) or "04" in str(exc)


def test_infer_seminf_reference_from_sinapi():
    from pricing.budget.seminf_open_refresh import infer_seminf_reference_from_sinapi

    assert infer_seminf_reference_from_sinapi("BR-2026-05") == "BR-DP-SEMINF-2026-05"
    assert infer_seminf_reference_from_sinapi("BR-2026-04", source_slug="SEMINF") == "BR-SEMINF-2026-04"


def test_tp2_index_from_tabela_preco_fixture():
    from pricing.budget.seminf_base_parser import build_tp2_index_from_workbook
    from pricing.budget.seminf_open_parser import merge_seminf_open_compositions, parse_seminf_open_workbook

    if not TABELA_PRECO_XLSM.exists() or not COMD_XLSX.exists() or not SEMD_XLSX.exists():
        return

    tp2_index = build_tp2_index_from_workbook(TABELA_PRECO_XLSM)
    assert tp2_index.get("88309") == "AS"
    assert len(tp2_index) > 3000

    merged = merge_seminf_open_compositions(
        parse_seminf_open_workbook(COMD_XLSX),
        parse_seminf_open_workbook(SEMD_XLSX),
        tp2_index=tp2_index,
    )
    comp = merged["97674.3.9.SEMINF"]
    as_items = [i for i in comp.items if i.tp2 == "AS"]
    assert as_items
    assert any(i.code.strip() == "88309" for i in as_items)


def test_validate_seminf_refresh_source_rejects_future_fonte():
    from pricing.budget.seminf_open_refresh import validate_seminf_refresh_source

    with pytest.raises(ValueError, match="mês anterior"):
        validate_seminf_refresh_source("BR-DP-SEMINF-2026-04", "BR-DP-SEMINF-2026-03")


def test_validate_seminf_refresh_source_allows_backfill():
    from pricing.budget.seminf_open_refresh import validate_seminf_refresh_source

    assert validate_seminf_refresh_source(
        "BR-DP-SEMINF-2026-04", "BR-DP-SEMINF-2026-03", allow_backfill=True
    )


def test_seminf_refresh_prices_fixture(tmp_path):
    from pricing.sync.connectors import DpSeminfConnector
    from pricing.budget.seminf_open_refresh import (
        apply_seminf_open_refresh,
        fork_seminf_price_base,
        seminf_root_reference,
    )
    from pricing.budget.price_bank_store import PriceBankStore

    bundle = _bundle_fixtures()
    if not bundle:
        return
    closed, comd, semd = bundle

    connector = DpSeminfConnector()
    connector.download(
        dest_dir=tmp_path,
        local_file=closed,
        open_comd_file=comd,
        open_semd_file=semd,
        set_active=False,
    )

    root = "BR-DP-SEMINF-2026-04"
    assert seminf_root_reference(f"{root}-R01") == root

    result = fork_seminf_price_base(
        root,
        sinapi_reference="BR-2026-05",
        uf="AM",
        set_active=False,
    )
    assert result.reference == "BR-DP-SEMINF-2026-05"
    assert result.parent_reference == root
    assert PriceBankStore.for_reference(root).load_manifest() is not None
    assert PriceBankStore.for_reference(result.reference).load_open()

    result2 = apply_seminf_open_refresh(root, sinapi_reference="BR-2026-05", uf="AM", set_active=False)
    assert result2.reference == "BR-DP-SEMINF-2026-05"


def test_dp_seminf_connector_import_fixture(tmp_path, monkeypatch):
    from pricing.budget import price_bank_index as pbi
    from pricing.sync.connectors import DpSeminfConnector

    monkeypatch.setattr(pbi, "PRICE_BANK_ROOT", tmp_path / "price_bank")
    pbi.PRICE_BANK_ROOT.mkdir(parents=True, exist_ok=True)

    xlsm = _fixture_xlsm()
    if not xlsm:
        return

    connector = DpSeminfConnector()
    result = connector.download(
        dest_dir=tmp_path,
        local_file=xlsm,
        year=2026,
        month=4,
        set_active=False,
    )
    assert 500 < result.metadata.get("compositions_closed", 0) < 900
    assert 500 < result.metadata.get("compositions_open", 0) < 900
    assert result.metadata.get("import_mode") == "bundle"
    assert result.reference == "BR-DP-SEMINF-2026-04"
    assert result.metadata.get("base_sheet") == "Base_Abril-2026-copia"


def test_dp_seminf_closed_only_without_siblings_raises(tmp_path, monkeypatch):
    import shutil

    from pricing.budget import price_bank_index as pbi
    from pricing.sync.connectors import DpSeminfConnector

    monkeypatch.setattr(pbi, "PRICE_BANK_ROOT", tmp_path / "price_bank")
    pbi.PRICE_BANK_ROOT.mkdir(parents=True, exist_ok=True)

    xlsm = _fixture_xlsm()
    if not xlsm:
        return

    isolated = tmp_path / "isolated" / xlsm.name
    isolated.parent.mkdir(parents=True)
    shutil.copy(xlsm, isolated)

    connector = DpSeminfConnector()
    with pytest.raises(ValueError, match="ComD \\+ SemD"):
        connector.download(dest_dir=tmp_path / "out", local_file=isolated, set_active=False)


def test_dp_seminf_blocks_destructive_reimport(tmp_path, monkeypatch):
    import shutil

    from pricing.budget import price_bank_index as pbi
    from pricing.budget.price_bank_store import PriceBankStore
    from pricing.sync.connectors import DpSeminfConnector

    monkeypatch.setattr(pbi, "PRICE_BANK_ROOT", tmp_path / "price_bank")
    pbi.PRICE_BANK_ROOT.mkdir(parents=True, exist_ok=True)

    bundle = _bundle_fixtures()
    if not bundle:
        return
    closed, comd, semd = bundle

    connector = DpSeminfConnector()
    connector.download(
        dest_dir=tmp_path / "full",
        local_file=closed,
        open_comd_file=comd,
        open_semd_file=semd,
        set_active=False,
    )
    ref = "BR-DP-SEMINF-2026-04"
    assert PriceBankStore.for_reference(ref).load_open()

    isolated = tmp_path / "isolated" / closed.name
    isolated.parent.mkdir(parents=True)
    shutil.copy(closed, isolated)

    with pytest.raises(ValueError, match="apagaria as CPUs"):
        connector.download(dest_dir=tmp_path / "partial", local_file=isolated, set_active=False)
