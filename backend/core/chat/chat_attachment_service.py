"""Preparação de anexos do chat — extração de conteúdo e contexto para o prompt."""

from __future__ import annotations

import json
import logging
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from config.settings import DATA_DIR
from core.chat.chat_attachment_routing import resolve_auto_llm_model_for_attachments
from core.project_rag.project_file_extractors import (
    PROJECT_INDEXABLE_SUFFIXES,
    extract_project_file_segments,
    is_indexable_project_file,
)
from core.project_review.vision_analysis_service import (
    IMAGE_SUFFIXES,
    VisionAnalysisService,
    extract_analysis,
    is_visual_file,
    suggest_mode_for_file,
)

logger = logging.getLogger(__name__)

CHAT_ATTACHMENTS_DIR = DATA_DIR / "chat_attachments"
MAX_FILES = 10
MAX_FILE_BYTES = 30 * 1024 * 1024
MAX_TOTAL_CONTEXT_CHARS = 50_000
MAX_SEGMENT_CHARS = 12_000
ATTACHMENT_TTL_HOURS = 4

# Leitura como texto para extensões comuns não indexadas pelo project RAG
_PLAIN_TEXT_SUFFIXES = frozenset({
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".cpp", ".c", ".h",
    ".sql", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".xml", ".html", ".css", ".sh",
    ".bat", ".ps1", ".env", ".log",
})


@dataclass
class PreparedChatAttachment:
    id: str
    filename: str
    size_bytes: int
    format_key: str
    model_hint: str | None = None
    preview: str = ""
    error: str | None = None
    path: Path | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "filename": self.filename,
            "size_bytes": self.size_bytes,
            "format": self.format_key,
            "model_hint": self.model_hint,
            "preview": self.preview,
            "error": self.error,
            "meta": self.meta,
        }


def _ensure_store() -> Path:
    CHAT_ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
    return CHAT_ATTACHMENTS_DIR


def _read_plain_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _format_segments(segments: list, *, max_chars: int) -> str:
    parts: list[str] = []
    used = 0
    for seg in segments:
        block = seg.text.strip()
        if seg.section:
            block = f"[{seg.section}] {block}"
        if used + len(block) > max_chars:
            remaining = max_chars - used
            if remaining > 200:
                parts.append(_truncate(block, remaining))
            break
        parts.append(block)
        used += len(block) + 2
    return "\n\n".join(parts)


def _vision_summary(path: Path) -> str | None:
    if not is_visual_file(path):
        return None
    try:
        service = VisionAnalysisService()
        availability = service.check_availability()
        if not availability.get("vision_models_ready"):
            return None
        mode = suggest_mode_for_file(path)
        payload = service.analyze_file(path, mode=mode)
        analysis = extract_analysis(payload)
        if not analysis:
            return None
        chunks: list[str] = []
        for key in ("resumo_tecnico", "disciplina", "observacoes", "nao_conformidades", "recomendacoes"):
            val = analysis.get(key)
            if isinstance(val, str) and val.strip():
                chunks.append(f"{key}: {val.strip()}")
            elif isinstance(val, list) and val:
                chunks.append(f"{key}: " + "; ".join(str(x) for x in val[:8]))
        if chunks:
            return _truncate("\n".join(chunks), MAX_SEGMENT_CHARS)
    except Exception as exc:
        logger.warning("Vision summary failed for %s: %s", path.name, exc)
    return None


def _extract_file_content(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()

    if is_indexable_project_file(path):
        segments, fmt = extract_project_file_segments(path)
        return _format_segments(segments, max_chars=MAX_SEGMENT_CHARS), fmt

    if suffix in _PLAIN_TEXT_SUFFIXES or suffix in {".txt", ".md", ".json", ".rtf"}:
        raw = _read_plain_text(path)
        return _truncate(raw, MAX_SEGMENT_CHARS), suffix.lstrip(".") or "text"

    # Fallback genérico — tenta texto; senão metadados
    try:
        raw = _read_plain_text(path)
        if raw.strip() and sum(c.isprintable() or c in "\n\r\t" for c in raw) / max(len(raw), 1) > 0.85:
            return _truncate(raw, MAX_SEGMENT_CHARS), suffix.lstrip(".") or "text"
    except Exception:
        pass

    size_kb = path.stat().st_size // 1024
    return (
        f"Arquivo anexado: {path.name} ({size_kb} KB). "
        f"Formato {suffix or 'desconhecido'} — conteúdo binário não extraído como texto.",
        suffix.lstrip(".") or "binary",
    )


def _resolve_model_hint(paths: list[Path], fmt_keys: list[str]) -> str | None:
    try:
        from models.ollama_client import OllamaClient

        names = set(OllamaClient().list_models() or [])
    except Exception:
        names = set()
    return resolve_auto_llm_model_for_attachments(paths, installed_models=names)


def prepare_uploaded_file(filename: str, data: bytes) -> PreparedChatAttachment:
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"Arquivo muito grande (máx. {MAX_FILE_BYTES // (1024 * 1024)} MB): {filename}")

    attachment_id = str(uuid.uuid4())
    safe_name = Path(filename).name or "anexo"
    store = _ensure_store()
    folder = store / attachment_id
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / safe_name
    dest.write_bytes(data)

    prepared = PreparedChatAttachment(
        id=attachment_id,
        filename=safe_name,
        size_bytes=len(data),
        format_key=dest.suffix.lower().lstrip(".") or "file",
        path=dest,
    )

    try:
        content, fmt = _extract_file_content(dest)
        prepared.format_key = fmt

        vision_block = _vision_summary(dest)
        if vision_block:
            content = f"{content}\n\n--- Análise visual (multimodal) ---\n{vision_block}"
            prepared.meta["vision"] = True

        prepared.preview = _truncate(content, 400)
        prepared.meta["content"] = content
    except Exception as exc:
        logger.exception("Failed to extract chat attachment %s", safe_name)
        prepared.error = str(exc)
        prepared.meta["content"] = f"[Anexo {safe_name} — falha na extração: {exc}]"

    return prepared


def save_prepared_attachment(prepared: PreparedChatAttachment, *, model_hint: str | None = None) -> PreparedChatAttachment:
    meta_path = CHAT_ATTACHMENTS_DIR / prepared.id / "meta.json"
    prepared.model_hint = model_hint
    meta_path.write_text(
        json.dumps(
            {
                **prepared.to_dict(),
                "path": str(prepared.path) if prepared.path else None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return prepared


def load_attachment(attachment_id: str) -> PreparedChatAttachment | None:
    meta_path = CHAT_ATTACHMENTS_DIR / attachment_id / "meta.json"
    if not meta_path.is_file():
        return None
    try:
        raw = json.loads(meta_path.read_text(encoding="utf-8"))
        path_str = raw.get("path")
        return PreparedChatAttachment(
            id=raw["id"],
            filename=raw.get("filename") or "anexo",
            size_bytes=int(raw.get("size_bytes") or 0),
            format_key=raw.get("format") or raw.get("format_key") or "file",
            model_hint=raw.get("model_hint"),
            preview=raw.get("preview") or "",
            error=raw.get("error"),
            path=Path(path_str) if path_str else None,
            meta=raw.get("meta") or {},
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def load_attachments(ids: list[str]) -> list[PreparedChatAttachment]:
    loaded: list[PreparedChatAttachment] = []
    for attachment_id in ids:
        item = load_attachment(attachment_id)
        if item:
            loaded.append(item)
    return loaded


def build_attachment_context(attachments: list[PreparedChatAttachment]) -> str:
    if not attachments:
        return ""

    blocks: list[str] = []
    total = 0
    for att in attachments:
        content = str(att.meta.get("content") or att.preview or "").strip()
        if not content:
            content = f"[Anexo {att.filename} sem conteúdo textual extraído]"
        header = f"### Anexo: {att.filename} ({att.format_key})"
        block = f"{header}\n{content}"
        if total + len(block) > MAX_TOTAL_CONTEXT_CHARS:
            remaining = MAX_TOTAL_CONTEXT_CHARS - total
            if remaining > 300:
                blocks.append(_truncate(block, remaining))
            break
        blocks.append(block)
        total += len(block) + 4

    if not blocks:
        return ""
    return (
        "---\n"
        "CONTEÚDO DOS ARQUIVOS ANEXADOS PELO USUÁRIO (use como contexto da pergunta):\n\n"
        + "\n\n".join(blocks)
        + "\n---\n\n"
    )


def compose_message_with_attachments(text: str, attachment_ids: list[str] | None) -> tuple[str, list[PreparedChatAttachment], str | None]:
    """Retorna (texto enriquecido, anexos carregados, model_hint agregado)."""
    attachments = load_attachments(attachment_ids or [])
    if not attachments:
        return text, [], None

    context = build_attachment_context(attachments)
    enriched = f"{context}Pergunta do usuário:\n{text}" if context else text

    paths = [a.path for a in attachments if a.path and a.path.is_file()]
    hint = _resolve_model_hint(paths, [a.format_key for a in attachments])
    if not hint:
        hints = [a.model_hint for a in attachments if a.model_hint]
        hint = hints[0] if hints else None

    names = ", ".join(a.filename for a in attachments)
    if names and names not in text:
        enriched = f"[Arquivos anexados: {names}]\n\n{enriched}"

    return enriched, attachments, hint


def resolve_prompt_with_attachments(
    text: str,
    attachment_ids: list[str] | None,
    llm_model: str | None = None,
) -> tuple[str, str | None]:
    """
    Enriquece o prompt com conteúdo dos anexos e resolve modelo quando auto/omitido.
    Retorna (texto_enriquecido, llm_model_efetivo).
    """
    purge_stale_attachments()
    enriched, _, hint = compose_message_with_attachments(text, attachment_ids)
    effective = (llm_model or "").strip() or None
    if effective in (None, "auto") and hint:
        effective = hint
    return enriched, effective


def purge_stale_attachments() -> int:
    """Remove anexos mais antigos que ATTACHMENT_TTL_HOURS."""
    store = _ensure_store()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=ATTACHMENT_TTL_HOURS)
    removed = 0
    for folder in store.iterdir():
        if not folder.is_dir():
            continue
        meta_path = folder / "meta.json"
        try:
            mtime = datetime.fromtimestamp(meta_path.stat().st_mtime, tz=timezone.utc) if meta_path.is_file() else None
            if mtime and mtime < cutoff:
                shutil.rmtree(folder, ignore_errors=True)
                removed += 1
        except OSError:
            continue
    return removed


def chat_upload_accept_suffixes() -> frozenset[str]:
    return PROJECT_INDEXABLE_SUFFIXES | _PLAIN_TEXT_SUFFIXES
