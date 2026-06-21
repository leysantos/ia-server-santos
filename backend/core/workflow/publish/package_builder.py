"""Empacotamento ZIP de entrega workflow."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any


def build_delivery_zip(
    *,
    manifest: dict[str, Any],
    files: list[tuple[str, bytes]],
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "manifest.json",
            __import__("json").dumps(manifest, ensure_ascii=False, indent=2),
        )
        for arcname, data in files:
            zf.writestr(arcname, data)
    return buffer.getvalue()


def collect_local_project_files(project_dir: Path, prefixes: list[str] | None = None) -> list[tuple[str, bytes]]:
    if not project_dir.exists():
        return []
    out: list[tuple[str, bytes]] = []
    for path in sorted(project_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(project_dir).as_posix()
        if prefixes and not any(rel.startswith(p) for p in prefixes):
            continue
        if path.suffix.lower() in {".dwg", ".dxf", ".ifc", ".pdf", ".docx", ".xlsx", ".png", ".jpg"}:
            out.append((f"originais/{rel}", path.read_bytes()))
    return out
