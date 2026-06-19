"""
Knowledge Path Resolver — armazenamento flat industrial.

Filesystem (único):
  backend/knowledge/raw/documents/{arquivo.pdf}

Disciplina, tipo, tags → metadata (.knowledge.json + catalog.jsonl).
Layers (canonical, structured, embeddings) → pipeline futuro, não pastas.

Compatibilidade:
  get_path("nbr"), get_knowledge_path("ESTRUTURAL", "raw") → KNOWLEDGE_DOCUMENTS_DIR
"""

from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path

from config.settings import DATA_DIR, KNOWLEDGE_DIR, KNOWLEDGE_DOCUMENTS_DIR
from core.knowledge.content_types import KB_SUBDIR_TO_PRIMARY_PATH, KNOWLEDGE_CONTENT_TYPES
from core.knowledge.disciplines import DISCIPLINE_SLUGS, slug_for_discipline
from core.knowledge.metadata import build_metadata_record, sidecar_path, write_metadata

KNOWLEDGE_DISCIPLINE_DIR = KNOWLEDGE_DOCUMENTS_DIR  # alias compat

STORAGE_LAYER = "raw"
DISCIPLINE_LAYERS = ("raw", "canonical", "structured", "embeddings")

BASE_NBR = "nbr"
BASE_SINAPI = "sinapi"
BASE_TCPO = "tcpo"
BASE_TDR = "tdr"
BASE_CATALOGOS = "catalogos"
BASE_REGIONAL = "regional"
BASE_BUDGET_MODELS = "budget_models"

DOMAIN_ALIASES: dict[str, str] = {
    "nbr": BASE_NBR,
    "cost": BASE_SINAPI,
    "composition": BASE_TCPO,
    "tdr": BASE_TDR,
    "catalog": BASE_CATALOGOS,
    "project": BASE_TDR,
    "manual": BASE_CATALOGOS,
    "regional": BASE_REGIONAL,
    BASE_SINAPI: BASE_SINAPI,
    BASE_TCPO: BASE_TCPO,
    BASE_CATALOGOS: BASE_CATALOGOS,
}

CANONICAL_SUBDIRS: dict[str, str] = {
    BASE_NBR: "nbrs",
    BASE_SINAPI: "sinapi",
    BASE_TCPO: "tcpo",
    BASE_TDR: "tdrs",
    BASE_CATALOGOS: "catalogos",
    BASE_REGIONAL: "regional",
    BASE_BUDGET_MODELS: "modelos_orcamento",
}

KB_SUBDIR_TO_PRIMARY_PATH = {
    subdir: ("_flat", STORAGE_LAYER) for subdir in CANONICAL_SUBDIRS.values()
}

LEGACY_READ_ONLY: dict[str, list[Path]] = {}

_SKIP_NAMES = {".gitkeep", "README.md", "catalog.jsonl"}
_INGESTABLE_SUFFIXES = {".pdf", ".csv", ".xlsx", ".xls", ".json", ".md", ".txt", ".docx"}


def get_documents_dir() -> Path:
    return KNOWLEDGE_DOCUMENTS_DIR


def normalize_discipline_slug(discipline: str) -> str:
    return slug_for_discipline(discipline)


def normalize_base_key(domain_or_base: str) -> str:
    key = (domain_or_base or "").strip().lower()
    return DOMAIN_ALIASES.get(key, key)


def get_knowledge_path(
    discipline: str = "",
    layer: str = STORAGE_LAYER,
    content_type: str | None = None,
) -> Path:
    """Sempre retorna knowledge/raw/documents/ (discipline/layer são metadata)."""
    if layer not in DISCIPLINE_LAYERS:
        raise ValueError(
            f"Layer inválida: {layer}. Use: {', '.join(DISCIPLINE_LAYERS)}"
        )
    path = get_documents_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_path(domain: str) -> Path:
    """Compat — todas as bases apontam para raw/documents/."""
    normalize_base_key(domain)  # valida domínio
    return get_documents_dir()


def get_canonical_path(base_key: str) -> Path:
    return get_path(base_key)


def canonical_base_paths() -> dict[str, Path]:
    return {key: get_documents_dir() for key in CANONICAL_SUBDIRS}


def get_supplementary_paths(base_key: str) -> list[Path]:
    return []


def ensure_discipline_dir(
    discipline: str = "",
    layer: str = STORAGE_LAYER,
    content_type: str | None = None,
) -> Path:
    return get_knowledge_path(discipline, layer, content_type)


def ensure_all_discipline_scaffold() -> list[Path]:
    """Garante knowledge/raw/documents/ (+ raw/ pai)."""
    docs = get_documents_dir()
    docs.mkdir(parents=True, exist_ok=True)
    (KNOWLEDGE_DIR / STORAGE_LAYER).mkdir(parents=True, exist_ok=True)
    gitkeep = docs / ".gitkeep"
    if not any(p for p in docs.iterdir() if p.name != ".gitkeep"):
        gitkeep.touch(exist_ok=True)
    return [docs]


def discipline_scaffold_specs() -> dict[str, frozenset[str]]:
    """Compat tests — uma única zona de storage."""
    return {"documents": frozenset({STORAGE_LAYER})}


def _is_content_type_dir(name: str) -> bool:
    return name in KNOWLEDGE_CONTENT_TYPES


def _is_ingestable_file(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix.lower() in _INGESTABLE_SUFFIXES
        and not path.name.endswith(".knowledge.json")
    )


def migrate_legacy_layout_to_documents(*, dry_run: bool = False) -> dict[str, list[str]]:
    """
    Consolida arquivos de knowledge/{disciplina}/... e knowledge_base/ → raw/documents/.
    Preserva sidecar ou cria metadata mínima.
    """
    log: dict[str, list[str]] = {"moved": [], "skipped": [], "removed_dirs": []}
    docs = get_documents_dir()
    if not dry_run:
        docs.mkdir(parents=True, exist_ok=True)

    sources: list[tuple[Path, str | None, str | None]] = []

    # layout antigo: knowledge/{slug}/raw/...
    if KNOWLEDGE_DIR.exists():
        for path in KNOWLEDGE_DIR.rglob("*"):
            if not _is_ingestable_file(path):
                continue
            if path.name in _SKIP_NAMES:
                continue
            rel_parts = path.relative_to(KNOWLEDGE_DIR).parts
            if rel_parts[:2] == ("raw", "documents"):
                continue
            # não migrar arquivos soltos na raiz de knowledge/
            if len(rel_parts) == 1:
                continue
            slug = rel_parts[0] if rel_parts and rel_parts[0] in DISCIPLINE_SLUGS else None
            layer = "raw"
            content_type = None
            if len(rel_parts) >= 3 and _is_content_type_dir(rel_parts[2]):
                content_type = rel_parts[2]
            elif len(rel_parts) >= 2 and rel_parts[1] in DISCIPLINE_LAYERS:
                layer = rel_parts[1]
                if len(rel_parts) >= 3 and _is_content_type_dir(rel_parts[2]):
                    content_type = rel_parts[2]
            sources.append((path, slug, content_type))

    # knowledge_base legado
    legacy_kb = KNOWLEDGE_DIR.parent / "knowledge_base"
    if legacy_kb.exists():
        for path in legacy_kb.rglob("*"):
            if _is_ingestable_file(path):
                ct = path.parent.name if _is_content_type_dir(path.parent.name) else None
                sources.append((path, None, ct))

    for src, slug, content_type in sources:
        dest = docs / src.name
        if dest.exists() and dest.stat().st_size != src.stat().st_size:
            dest = docs / f"{uuid.uuid4().hex[:8]}_{src.name}"
        entry = f"{src} → {dest.name}"
        if dry_run:
            log["moved"].append(f"would_move:{entry}")
            continue
        if not dest.exists():
            shutil.copy2(src, dest)
        if not sidecar_path(dest).exists():
            from core.knowledge.content_types import default_content_type_for_discipline

            disc_slug = slug or "geral"
            ct = content_type or default_content_type_for_discipline(disc_slug)
            write_metadata(
                dest,
                build_metadata_record(
                    discipline_slugs=[disc_slug],
                    layer=STORAGE_LAYER,
                    content_type=ct,
                    source="migrate_legacy_layout",
                    confidence=0.9,
                    filename=dest.name,
                ),
            )
        log["moved"].append(entry)

    return log


def prune_knowledge_orphans(*, dry_run: bool = False) -> dict[str, list[str]]:
    """Remove pastas por disciplina/layer; mantém raw/documents/."""
    from core.knowledge.disciplines import DEPRECATED_SLUG_DIRS

    log: dict[str, list[str]] = {
        "removed_dirs": [],
        "skipped_nonempty": [],
        "migrate": {},
    }

    log["migrate"] = migrate_legacy_layout_to_documents(dry_run=dry_run)

    if not KNOWLEDGE_DIR.exists():
        return log

    keep = {STORAGE_LAYER, "README.md", "catalog.jsonl"}

    for child in sorted(KNOWLEDGE_DIR.iterdir()):
        if child.name in keep or child.is_file():
            continue
        if child.name in DEPRECATED_SLUG_DIRS or child.name in DISCIPLINE_SLUGS:
            rel = str(child.relative_to(KNOWLEDGE_DIR))
            if dry_run:
                log["removed_dirs"].append(f"would_remove:{rel}")
            else:
                shutil.rmtree(child)
                log["removed_dirs"].append(rel)

    # limpar layers vazias fora de raw/documents
    raw_dir = KNOWLEDGE_DIR / STORAGE_LAYER
    if raw_dir.is_dir():
        for sub in sorted(raw_dir.iterdir()):
            if sub.name == "documents":
                continue
            if sub.is_dir():
                rel = str(sub.relative_to(KNOWLEDGE_DIR))
                if dry_run:
                    log["removed_dirs"].append(f"would_remove:{rel}")
                else:
                    shutil.rmtree(sub, ignore_errors=True)
                    log["removed_dirs"].append(rel)

    for junk in ("migration_log.json",):
        p = KNOWLEDGE_DIR / junk
        if p.is_file() and not dry_run:
            p.unlink()
            log["removed_dirs"].append(junk)

    return log


def legacy_kb_subdir_to_full_path(subdir: str) -> tuple[str, str, str]:
    return "geral", STORAGE_LAYER, subdir


def legacy_kb_subdir_to_discipline(subdir: str) -> tuple[str, str]:
    return "geral", STORAGE_LAYER


def get_discipline_read_paths_for_base(base_key: str) -> list[tuple[Path, str]]:
    """Indexação: única pasta raw/documents/."""
    return [(get_documents_dir(), "documents")]


def is_legacy_path(path: Path) -> bool:
    try:
        path.resolve().relative_to(DATA_DIR.resolve())
        return True
    except ValueError:
        return False


def is_discipline_path(path: Path) -> bool:
    try:
        path.resolve().relative_to(KNOWLEDGE_DIR.resolve())
        return True
    except ValueError:
        return False


is_canonical_path = is_discipline_path


def get_legacy_read_paths(base_key: str) -> list[Path]:
    return list(LEGACY_READ_ONLY.get(normalize_base_key(base_key), []))


def get_all_read_paths(
    base_key: str,
    *,
    include_legacy: bool = True,
    include_discipline: bool = True,
    discipline_first: bool = True,
) -> list[tuple[Path, str]]:
    paths = [(get_documents_dir(), "documents")] if include_discipline else []
    legacy_block = [
        (path, "legacy_readonly")
        for path in get_legacy_read_paths(base_key)
    ] if include_legacy else []
    ordered = paths + legacy_block if discipline_first else legacy_block + paths
    seen: set[str] = set()
    unique: list[tuple[Path, str]] = []
    for path, tier in ordered:
        key = str(path.resolve())
        if key not in seen:
            seen.add(key)
            unique.append((path, tier))
    return unique


def ensure_canonical_dir(base_key: str) -> Path:
    path = get_documents_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def iter_layer_paths(slug: str = "") -> list[Path]:
    return [get_documents_dir()]


def file_dedup_key(path: Path) -> str:
    stat = path.stat()
    return f"{path.name.lower()}|{stat.st_size}"


def file_content_hash(path: Path, chunk_size: int = 65536) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def file_hash_dedup_key(path: Path) -> str:
    return f"sha256:{file_content_hash(path)}"


def assert_write_target(path: Path) -> None:
    from core.knowledge.legacy_guard import assert_ingest_target

    assert_ingest_target(path)
