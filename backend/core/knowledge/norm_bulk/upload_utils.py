"""Utilitários para uploads multipart (Starlette ≠ FastAPI UploadFile)."""

from __future__ import annotations

from typing import Any

from starlette.datastructures import FormData, UploadFile as StarletteUploadFile


def is_upload_file(value: Any) -> bool:
    """Starlette form retorna UploadFile próprio — não usar fastapi.UploadFile em isinstance."""
    return isinstance(value, StarletteUploadFile)


def extract_upload_files(form: FormData, field: str = "files") -> list[StarletteUploadFile]:
    return [
        value
        for key, value in form.multi_items()
        if key == field and is_upload_file(value)
    ]
