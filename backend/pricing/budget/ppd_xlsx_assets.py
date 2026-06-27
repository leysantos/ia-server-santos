from __future__ import annotations

import io
import logging
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

_PRESERVE_PREFIXES = (
    "xl/media/",
    "xl/drawings/",
    "xl/printerSettings/",
)


def _preserve_zip_member(name: str) -> bool:
    if any(name.startswith(prefix) for prefix in _PRESERVE_PREFIXES):
        return True
    return "vmlDrawing" in name


def merge_workbook_preserving_assets(original: Path | bytes, modified: Path | bytes) -> bytes:
    """
    Mescla workbook salvo pelo openpyxl com assets do original (logo no cabeçalho,
    vmlDrawing, printerSettings) que o openpyxl remove ao gravar.
    """
    orig_bytes = original if isinstance(original, bytes) else original.read_bytes()
    mod_bytes = modified if isinstance(modified, bytes) else modified.read_bytes()

    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(mod_bytes), "r") as zmod, zipfile.ZipFile(
        io.BytesIO(orig_bytes), "r"
    ) as zorig:
        preserve = {n for n in zorig.namelist() if _preserve_zip_member(n)}
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
            for name in zmod.namelist():
                if name in preserve:
                    continue
                zout.writestr(name, zmod.read(name))
            for name in sorted(preserve):
                zout.writestr(name, zorig.read(name))
    logger.debug("merge_workbook_preserving_assets: preserved %s zip members", len(preserve))
    return out.getvalue()
