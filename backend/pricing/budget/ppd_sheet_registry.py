from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PpdSheetSpec:
    key: str
    print_start_col: str
    print_end_col: str
    data_cols: tuple[int, ...]
    footer_pad: int
    preserve_orientation: bool = True
    needs_mcq: bool = False
    needs_base: bool = False
    pdf_prefix: str = ""


SHEET_ALIASES: dict[str, str] = {
    "PLANILHA": "ORC_SINTETICO",
    "OR": "ORC_SINTETICO",
    "ORC_SINTETICO": "ORC_SINTETICO",
    "SINTETICO": "ORC_SINTETICO",
    "ORC_ANALITICO": "ORC_ANALITICO",
    "ANALITICO": "ORC_ANALITICO",
    "MCQ": "MCQ",
    "CRONOGRAMA": "CRONOGRAMA",
    "ESP_TECNICA": "ESP_TECNICA",
    "ESP": "ESP_TECNICA",
}

EXPORTABLE_SHEETS: dict[str, PpdSheetSpec] = {
    "MCQ": PpdSheetSpec(
        key="MCQ",
        print_start_col="H",
        print_end_col="L",
        data_cols=(8, 9, 10, 11, 12),
        footer_pad=6,
        needs_base=True,
        pdf_prefix="PPD_MC",
    ),
    "ORC_SINTETICO": PpdSheetSpec(
        key="ORC_SINTETICO",
        print_start_col="H",
        print_end_col="R",
        data_cols=(8, 9, 10, 11, 12),
        footer_pad=12,
        needs_mcq=True,
        needs_base=True,
        pdf_prefix="PPD_OR",
    ),
    "PLANILHA": PpdSheetSpec(
        key="PLANILHA",
        print_start_col="H",
        print_end_col="R",
        data_cols=(8, 9, 10, 11, 12),
        footer_pad=12,
        needs_mcq=True,
        needs_base=True,
        pdf_prefix="PPD_OR",
    ),
    "ORC_ANALITICO": PpdSheetSpec(
        key="ORC_ANALITICO",
        print_start_col="H",
        print_end_col="R",
        data_cols=(8, 9, 10, 11, 12),
        footer_pad=12,
        needs_mcq=True,
        needs_base=True,
        pdf_prefix="PPD_ORA",
    ),
    "CRONOGRAMA": PpdSheetSpec(
        key="CRONOGRAMA",
        print_start_col="A",
        print_end_col="AI",
        data_cols=(1, 2, 3),
        footer_pad=8,
        pdf_prefix="PPD_CRON",
    ),
    "ESP_TECNICA": PpdSheetSpec(
        key="ESP_TECNICA",
        print_start_col="A",
        print_end_col="F",
        data_cols=(1,),
        footer_pad=4,
        pdf_prefix="PPD_ESP",
    ),
}


def normalize_sheet_key(name: str) -> str:
    return SHEET_ALIASES.get(name.strip().upper(), name.strip().upper())


def resolve_workbook_sheet(sheetnames: list[str], requested: str) -> str | None:
    """Resolve nome pedido (ex. planilha) para nome real na workbook."""
    target = normalize_sheet_key(requested)
    by_upper = {n.upper(): n for n in sheetnames}
    if target in by_upper:
        return by_upper[target]
    if target == "ORC_SINTETICO" and "PLANILHA" in by_upper:
        return by_upper["PLANILHA"]
    if target == "PLANILHA" and "ORC_SINTETICO" in by_upper:
        return by_upper["ORC_SINTETICO"]
    return None


def sheet_spec_for(workbook_sheet_name: str) -> PpdSheetSpec | None:
    key = workbook_sheet_name.upper()
    if key in EXPORTABLE_SHEETS:
        return EXPORTABLE_SHEETS[key]
    if key == "PLANILHA":
        return EXPORTABLE_SHEETS["PLANILHA"]
    return None


def list_exportable_sheets(sheetnames: list[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for name in sheetnames:
        spec = sheet_spec_for(name)
        if not spec or spec.key in seen:
            continue
        seen.add(spec.key)
        out.append(
            {
                "sheet": name,
                "key": spec.key,
                "pdf_prefix": spec.pdf_prefix,
            }
        )
    return out
