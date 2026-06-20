"""Pipeline OCR e extração estruturada (Módulo C)."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_STAMP_PATTERNS = [
    re.compile(r"\b(ARQ|EST|HID|ELE|PCI)\b[\s\-./]*[\d\-/]+", re.I),
    re.compile(r"\bESCALA\s*[:\-]?\s*1\s*:\s*\d+", re.I),
    re.compile(r"\bPROJETO\s*:\s*.+", re.I),
]
_SCALE_PATTERN = re.compile(r"1\s*:\s*(\d+)", re.I)


def extract_structured(path: Path) -> dict[str, Any]:
    """Extrai texto, tabelas e metadados de PDF/imagem."""
    path = Path(path).resolve()
    ext = path.suffix.lower()
    result: dict[str, Any] = {
        "format": ext.lstrip("."),
        "texto": "",
        "tabelas": [],
        "carimbos": [],
        "notas": [],
        "legendas": [],
        "cotas": [],
        "escalas": [],
        "quadros": [],
    }

    if ext == ".pdf":
        _extract_pdf(path, result)
    elif ext in {".png", ".jpg", ".jpeg"}:
        _extract_image_ocr(path, result)
    else:
        result["texto"] = _read_plain_text(path)

    _post_process(result)
    return result


def _extract_pdf(path: Path, result: dict[str, Any]) -> None:
    texts: list[str] = []

    try:
        import fitz

        doc = fitz.open(path)
        try:
            for page in doc:
                texts.append(page.get_text("text"))
        finally:
            doc.close()
    except ImportError:
        logger.debug("PyMuPDF ausente — fallback pypdf")
    except Exception as exc:
        logger.warning("PyMuPDF falhou em %s: %s", path.name, exc)

    if not texts:
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            texts = [(p.extract_text() or "") for p in reader.pages]
        except Exception as exc:
            logger.warning("pypdf falhou em %s: %s", path.name, exc)

    try:
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables() or []
                for table in tables:
                    if table:
                        result["tabelas"].append({"rows": table})
    except ImportError:
        pass
    except Exception as exc:
        logger.debug("pdfplumber: %s", exc)

    try:
        import camelot

        tables = camelot.read_pdf(str(path), pages="1-end", flavor="lattice")
        for t in tables:
            result["tabelas"].append({"rows": t.df.values.tolist(), "source": "camelot"})
    except ImportError:
        pass
    except Exception:
        pass

    result["texto"] = "\n".join(texts)


def _extract_image_ocr(path: Path, result: dict[str, Any]) -> None:
    try:
        from paddleocr import PaddleOCR

        ocr = PaddleOCR(use_angle_cls=True, lang="pt", show_log=False)
        raw = ocr.ocr(str(path), cls=True)
        lines: list[str] = []
        for block in raw or []:
            for line in block or []:
                if line and len(line) > 1:
                    lines.append(str(line[1][0]))
        result["texto"] = "\n".join(lines)
        result["ocr_engine"] = "paddleocr"
        return
    except ImportError:
        pass
    except Exception as exc:
        logger.debug("PaddleOCR: %s", exc)

    try:
        import cv2

        img = cv2.imread(str(path))
        if img is not None:
            result["texto"] = ""
            result["ocr_engine"] = "opencv_metadata_only"
            result["image_shape"] = list(img.shape)
    except ImportError:
        result["texto"] = ""
        result["ocr_engine"] = "none"


def _read_plain_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:500_000]
    except Exception:
        return ""


def _post_process(result: dict[str, Any]) -> None:
    text = result.get("texto") or ""
    for pat in _STAMP_PATTERNS:
        for m in pat.finditer(text):
            stamp = m.group(0).strip()
            if stamp not in result["carimbos"]:
                result["carimbos"].append(stamp)

    for m in _SCALE_PATTERN.finditer(text):
        scale = f"1:{m.group(1)}"
        if scale not in result["escalas"]:
            result["escalas"].append(scale)

    for label in ("NOTA", "LEGENDA", "OBS"):
        for line in text.splitlines():
            if line.upper().startswith(label):
                bucket = "notas" if label == "NOTA" else "legendas"
                if line.strip() not in result[bucket]:
                    result[bucket].append(line.strip())

    cota_hits = re.findall(r"\b\d+[,.]?\d*\s*(m|cm|mm)\b", text, re.I)
    result["cotas"] = list(dict.fromkeys(cota_hits))[:50]

    for table in result.get("tabelas", []):
        rows = table.get("rows") or []
        if rows:
            result["quadros"].append({"rows": len(rows), "cols": len(rows[0]) if rows[0] else 0})
