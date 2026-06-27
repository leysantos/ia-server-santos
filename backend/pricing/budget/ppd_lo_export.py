from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from pricing.budget.ppd_pdf_prepare import cleanup_prepared_workbook, prepare_single_sheet_pdf_workbook

logger = logging.getLogger(__name__)

_LO_TIMEOUT_SEC = 180

_WSL_WINDOWS_LO = (
    Path("/mnt/c/Program Files/LibreOffice/program/soffice.exe"),
    Path("/mnt/c/Program Files (x86)/LibreOffice/program/soffice.exe"),
)


def find_libreoffice() -> Path | None:
    for env_key in ("LIBREOFFICE_PATH", "SOFFICE_PATH"):
        raw = (os.environ.get(env_key) or "").strip()
        if raw:
            candidate = Path(raw)
            if candidate.exists():
                return candidate

    for name in ("libreoffice", "soffice"):
        found = shutil.which(name)
        if found:
            return Path(found)

    for candidate in (
        Path("/usr/bin/libreoffice"),
        Path("/usr/bin/soffice"),
        Path("/snap/bin/libreoffice"),
        *_WSL_WINDOWS_LO,
    ):
        if candidate.exists():
            return candidate
    return None


def libreoffice_info() -> dict[str, str | bool]:
    lo = find_libreoffice()
    if not lo:
        return {"available": False, "path": "", "version": ""}
    version = ""
    try:
        proc = subprocess.run(
            [str(lo), "--version"],
            check=True,
            timeout=30,
            capture_output=True,
            text=True,
        )
        version = (proc.stdout or proc.stderr or "").strip().split("\n")[0]
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("LibreOffice --version falhou: %s", exc)
    return {"available": True, "path": str(lo), "version": version}


def libreoffice_available() -> bool:
    return find_libreoffice() is not None


def _require_libreoffice() -> Path:
    lo = find_libreoffice()
    if not lo:
        raise RuntimeError(
            "LibreOffice não encontrado no servidor. "
            "Instale com: sudo apt install libreoffice-calc"
        )
    return lo


def _run_lo_pdf(lo: Path, source: Path, outdir: Path) -> Path:
    cmd = [
        str(lo),
        "--headless",
        "--norestore",
        "--invisible",
        "--convert-to",
        "pdf",
        "--outdir",
        str(outdir),
        str(source),
    ]
    logger.info("LibreOffice PDF: %s", " ".join(cmd))
    subprocess.run(cmd, check=True, timeout=_LO_TIMEOUT_SEC, capture_output=True)
    candidates = sorted(outdir.glob("*.pdf"))
    if not candidates:
        raise RuntimeError("LibreOffice não gerou arquivo PDF")
    return candidates[0]


def export_sheet_pdf(path: Path, *, sheet: str = "PLANILHA", last_data_row: int | None = None) -> bytes:
    """Exporta uma única aba (MCQ ou PLANILHA) respeitando área de impressão do template."""
    lo = _require_libreoffice()
    prepared: Path | None = None
    try:
        prepared = prepare_single_sheet_pdf_workbook(path, sheet, last_data_row=last_data_row)
        outdir = prepared.parent / "out"
        outdir.mkdir(parents=True, exist_ok=True)
        pdf_path = _run_lo_pdf(lo, prepared, outdir)
        return pdf_path.read_bytes()
    finally:
        if prepared is not None:
            cleanup_prepared_workbook(prepared)


def export_workbook_bytes_to_pdf(
    data: bytes,
    *,
    sheet: str = "PLANILHA",
    last_data_row: int | None = None,
) -> bytes:
    with tempfile.TemporaryDirectory(prefix="ppd-lo-") as tmp:
        path = Path(tmp) / "workbook.xlsm"
        path.write_bytes(data)
        return export_sheet_pdf(path, sheet=sheet, last_data_row=last_data_row)
