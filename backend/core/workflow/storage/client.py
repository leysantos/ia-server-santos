"""Armazenamento de artefatos workflow — MinIO (S3) com fallback local."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from config.settings import BASE_DIR, get_settings
from core.workflow.storage.paths import build_storage_key

logger = logging.getLogger(__name__)

WORKFLOW_LOCAL_ROOT = BASE_DIR / "data" / "workflow"


class WorkflowStorage(ABC):
    backend: str = "abstract"

    @abstractmethod
    def put_bytes(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        ...

    @abstractmethod
    def put_file(self, key: str, local_path: Path, *, content_type: str | None = None) -> str:
        ...

    @abstractmethod
    def get_bytes(self, key: str) -> bytes:
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        ...

    def presigned_get_url(self, key: str, *, expires: int = 3600) -> str | None:
        """URL temporária de download (MinIO). Local retorna None."""
        return None

    def uri(self, key: str) -> str:
        return key


class LocalWorkflowStorage(WorkflowStorage):
    backend = "local"

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or WORKFLOW_LOCAL_ROOT
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / key

    def put_bytes(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return str(dest)

    def put_file(self, key: str, local_path: Path, *, content_type: str | None = None) -> str:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(local_path.read_bytes())
        return str(dest)

    def get_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def uri(self, key: str) -> str:
        return str(self._path(key))


class MinioWorkflowStorage(WorkflowStorage):
    backend = "minio"

    def __init__(self) -> None:
        import boto3
        from botocore.client import Config

        settings = get_settings()
        scheme = "https" if settings.minio_secure else "http"
        self.bucket = settings.minio_bucket
        self.public_base = settings.minio_public_url or f"{scheme}://{settings.minio_endpoint}/{self.bucket}"
        self._client = boto3.client(
            "s3",
            endpoint_url=f"{scheme}://{settings.minio_endpoint}",
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except Exception:
            try:
                self._client.create_bucket(Bucket=self.bucket)
            except Exception as exc:
                logger.warning("MinIO create_bucket skip: %s", exc)

    def put_bytes(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        extra: dict[str, Any] = {}
        if content_type:
            extra["ContentType"] = content_type
        self._client.put_object(Bucket=self.bucket, Key=key, Body=data, **extra)
        return self.uri(key)

    def put_file(self, key: str, local_path: Path, *, content_type: str | None = None) -> str:
        extra: dict[str, Any] = {}
        if content_type:
            extra["ContentType"] = content_type
        with local_path.open("rb") as fh:
            self._client.put_object(Bucket=self.bucket, Key=key, Body=fh, **extra)
        return self.uri(key)

    def get_bytes(self, key: str) -> bytes:
        obj = self._client.get_object(Bucket=self.bucket, Key=key)
        return obj["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def uri(self, key: str) -> str:
        return f"{self.public_base.rstrip('/')}/{key}"

    def presigned_get_url(self, key: str, *, expires: int = 3600) -> str | None:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires,
        )


_storage: WorkflowStorage | None = None


def get_workflow_storage() -> WorkflowStorage:
    global _storage
    if _storage is not None:
        return _storage

    settings = get_settings()
    if settings.minio_enabled:
        try:
            _storage = MinioWorkflowStorage()
            logger.info("Workflow storage: MinIO (%s)", settings.minio_bucket)
            return _storage
        except Exception as exc:
            logger.warning("MinIO indisponível, fallback local: %s", exc)

    _storage = LocalWorkflowStorage()
    logger.info("Workflow storage: local (%s)", WORKFLOW_LOCAL_ROOT)
    return _storage


def store_artifact(
    *,
    tenant: str | None,
    project_id: str,
    discipline: str | None,
    revision: str | None,
    version: str | None,
    filename: str,
    data: bytes,
    content_type: str | None = None,
) -> dict[str, str]:
    key = build_storage_key(
        tenant=tenant,
        project_id=project_id,
        discipline=discipline,
        revision=revision,
        version=version,
        filename=filename,
    )
    storage = get_workflow_storage()
    uri = storage.put_bytes(key, data, content_type=content_type)
    return {"key": key, "uri": uri, "backend": storage.backend}


def sanitize_storage_key(key: str) -> str:
    return key.lstrip("/").replace("..", "")


def artifact_download_path(key: str) -> str:
    """Path relativo da API para download (funciona local e MinIO via redirect)."""
    from urllib.parse import quote

    return f"/workflow/artifacts/download?key={quote(sanitize_storage_key(key), safe='')}"


def stream_artifact(key: str) -> tuple[bytes, str]:
    """Lê bytes do artefato — usado pelo endpoint de download."""
    storage = get_workflow_storage()
    safe = sanitize_storage_key(key)
    data = storage.get_bytes(safe)
    filename = Path(safe).name
    return data, filename

