from __future__ import annotations

import json
import re
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pricing.bootstrap import _DEFAULT_DATA_DIR
from pricing.budget.ppd_parser import extract_price_base_rows
from pricing.providers._tabular import parse_tabular_file

_CUSTOM_DIR = _DEFAULT_DATA_DIR / "custom_bases"
_SUPPORTED = {".csv", ".xlsx", ".xls", ".json", ".xlsm", ".xml", ".pdf", ".txt"}


@dataclass
class PriceBaseEntry:
    id: str
    name: str
    filename: str
    format: str
    item_count: int
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    active: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PriceBaseStore:
    """Registro de bases de preço nomeadas pelo usuário."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or _CUSTOM_DIR
        self.root.mkdir(parents=True, exist_ok=True)
        self._index_file = self.root / "index.json"

    def _load_index(self) -> list[dict[str, Any]]:
        if not self._index_file.exists():
            return []
        return json.loads(self._index_file.read_text(encoding="utf-8"))

    def _save_index(self, entries: list[dict[str, Any]]) -> None:
        self._index_file.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_bases(self) -> list[PriceBaseEntry]:
        return [PriceBaseEntry(**e) for e in self._load_index()]

    def get(self, base_id: str) -> PriceBaseEntry | None:
        for e in self._load_index():
            if e["id"] == base_id:
                return PriceBaseEntry(**e)
        return None

    def _slugify(name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        return slug[:40] or "base"

    def import_file(self, name: str, source_path: Path) -> tuple[PriceBaseEntry, list[dict]]:
        suffix = source_path.suffix.lower()
        if suffix not in _SUPPORTED:
            raise ValueError(f"Formato não suportado: {suffix}")

        rows = _parse_price_rows(source_path, suffix)
        if not rows:
            raise ValueError("Nenhum item de preço encontrado no arquivo")

        base_id = uuid.uuid4().hex[:10]
        dest_dir = self.root / base_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / source_path.name
        shutil.copy2(source_path, dest_file)

        items_file = dest_dir / "items.json"
        items_file.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

        entries = self._load_index()
        for e in entries:
            e["active"] = False

        entry = PriceBaseEntry(
            id=base_id,
            name=name.strip() or source_path.stem,
            filename=source_path.name,
            format=suffix.lstrip("."),
            item_count=len(rows),
            active=True,
        )
        entries.append(entry.to_dict())
        self._save_index(entries)
        return entry, rows

    def activate(self, base_id: str) -> list[dict]:
        entries = self._load_index()
        rows: list[dict] = []
        found = False
        for e in entries:
            e["active"] = e["id"] == base_id
            if e["id"] == base_id:
                found = True
                items_path = self.root / base_id / "items.json"
                if items_path.exists():
                    rows = json.loads(items_path.read_text(encoding="utf-8"))
        if not found:
            raise KeyError(f"Base não encontrada: {base_id}")
        self._save_index(entries)
        return rows

    def get_active_rows(self) -> tuple[PriceBaseEntry | None, list[dict]]:
        for e in self._load_index():
            if e.get("active"):
                entry = PriceBaseEntry(**e)
                items_path = self.root / entry.id / "items.json"
                if items_path.exists():
                    return entry, json.loads(items_path.read_text(encoding="utf-8"))
        return None, []

    def delete(self, base_id: str) -> PriceBaseEntry | None:
        entries = self._load_index()
        removed: dict[str, Any] | None = None
        kept: list[dict[str, Any]] = []
        for e in entries:
            if e["id"] == base_id:
                removed = e
            else:
                kept.append(e)

        if removed is None:
            raise KeyError(f"Base não encontrada: {base_id}")

        was_active = bool(removed.get("active"))
        dest_dir = self.root / base_id
        if dest_dir.exists():
            shutil.rmtree(dest_dir)

        if was_active and kept:
            kept[-1]["active"] = True

        self._save_index(kept)
        return PriceBaseEntry(**removed)


def _parse_price_rows(path: Path, suffix: str) -> list[dict]:
    if suffix in (".xlsm", ".xlsx", ".xls"):
        ppd_rows = extract_price_base_rows(path)
        if ppd_rows:
            return ppd_rows
        return parse_tabular_file(path)

    if suffix == ".xml":
        return _parse_xml_prices(path)

    if suffix == ".pdf":
        return _parse_pdf_prices(path)

    if suffix == ".txt":
        return _parse_text_prices(path)

    return parse_tabular_file(path)


def _parse_xml_prices(path: Path) -> list[dict]:
    import xml.etree.ElementTree as ET

    tree = ET.parse(path)
    root = tree.getroot()
    rows: list[dict] = []
    for item in root.iter():
        tag = item.tag.split("}")[-1].lower()
        if tag not in ("item", "insumo", "servico", "composicao", "row"):
            continue
        code = item.findtext("codigo") or item.findtext("code") or item.get("codigo", "")
        desc = item.findtext("descricao") or item.findtext("description") or item.findtext("nome", "")
        unit = item.findtext("unidade") or item.findtext("unit") or "un"
        price_raw = item.findtext("preco") or item.findtext("price") or item.findtext("valor") or "0"
        if not str(desc or code).strip():
            continue
        try:
            price = float(str(price_raw).replace(",", "."))
        except ValueError:
            price = 0.0
        rows.append({"code": str(code).strip(), "description": str(desc).strip(), "unit": unit, "price": price})
    return rows


def _parse_pdf_prices(path: Path) -> list[dict]:
    from memory.pdf_indexer import PDFIndexer

    pages = PDFIndexer.extract_text(path)
    text = "\n".join(t for _, t in pages)
    return _parse_text_prices_from_string(text)


def _parse_text_prices(path: Path) -> list[dict]:
    return _parse_text_prices_from_string(path.read_text(encoding="utf-8", errors="ignore"))


def _parse_text_prices_from_string(text: str) -> list[dict]:
    """Heurística: linhas com código numérico + descrição + preço."""
    rows: list[dict] = []
    pattern = re.compile(
        r"^(\d{4,8})\s+(.+?)\s+(\d+(?:[.,]\d+)?)\s*$",
        re.MULTILINE,
    )
    for m in pattern.finditer(text):
        rows.append(
            {
                "code": m.group(1),
                "description": m.group(2).strip(),
                "unit": "un",
                "price": float(m.group(3).replace(",", ".")),
            }
        )
    return rows


STORE = PriceBaseStore()
