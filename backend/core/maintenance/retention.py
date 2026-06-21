"""Retenção de backups — mantém apenas os conjuntos mais recentes."""

from __future__ import annotations

import json
import re
from pathlib import Path

STAMP_RE = re.compile(r"(\d{8}-\d{6})")
ARTIFACT_FOLDERS = ("app", "database", "knowledge", "faiss", "config")


def extract_stamp(filename: str) -> str | None:
    match = STAMP_RE.search(filename)
    return match.group(1) if match else None


def collect_stamps(root: Path) -> list[str]:
    stamps: set[str] = set()
    for folder in ARTIFACT_FOLDERS:
        directory = root / folder
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            if path.is_file():
                stamp = extract_stamp(path.name)
                if stamp:
                    stamps.add(stamp)
    return sorted(stamps, reverse=True)


def delete_stamp(root: Path, stamp: str) -> list[str]:
    removed: list[str] = []
    for folder in ARTIFACT_FOLDERS:
        directory = root / folder
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            if path.is_file() and stamp in path.name:
                path.unlink(missing_ok=True)
                removed.append(str(path))
    manifest = root / "logs" / f"manifest-{stamp}.json"
    if manifest.is_file():
        manifest.unlink(missing_ok=True)
        removed.append(str(manifest))
    return removed


def apply_retention(root: Path, *, keep_latest: int) -> dict[str, list[str]]:
    """Remove conjuntos antigos; retorna stamps mantidos e arquivos apagados."""
    if keep_latest < 1:
        keep_latest = 1
    stamps = collect_stamps(root)
    keep = set(stamps[:keep_latest])
    removed: list[str] = []
    for old in stamps[keep_latest:]:
        removed.extend(delete_stamp(root, old))
    logs_dir = root / "logs"
    if logs_dir.is_dir():
        for path in logs_dir.glob("manifest-*.json"):
            stamp = path.stem.replace("manifest-", "")
            if stamp and stamp not in keep:
                path.unlink(missing_ok=True)
                removed.append(str(path))
    return {"kept_stamps": sorted(keep, reverse=True), "removed": removed}
