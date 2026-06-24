"""Registro persistente de tipos de base de preços (built-in + customizados)."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import KNOWLEDGE_DIR

REGISTRY_PATH = KNOWLEDGE_DIR / "price_base_sources.json"
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")
_RESERVED = frozenset({"sinapi", "orse", "tcpo", "cicro", "ppd_seminf", "dp_seminf", "custom", "new"})


@dataclass
class SourceProfile:
    name: str
    label: str
    download_url: str = ""
    custom: bool = False
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_source_name(raw: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", (raw or "").strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    if not slug or not _NAME_RE.match(slug):
        raise ValueError(
            "Identificador inválido — use letras minúsculas, números e _ (ex.: pd_seminf, sicro_sp)"
        )
    if slug in _RESERVED:
        raise ValueError(f"Identificador '{slug}' é reservado pelo sistema")
    return slug


class PriceBaseSourceRegistry:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or REGISTRY_PATH

    def _load_raw(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"sources": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save_raw(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data["updated_at"] = _now_iso()
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_profiles(self) -> dict[str, SourceProfile]:
        raw = self._load_raw()
        out: dict[str, SourceProfile] = {}
        for key, value in (raw.get("sources") or {}).items():
            if not isinstance(value, dict):
                continue
            out[key.lower()] = SourceProfile(
                name=key.lower(),
                label=str(value.get("label") or key),
                download_url=str(value.get("download_url") or ""),
                custom=bool(value.get("custom")),
                created_at=str(value.get("created_at") or ""),
            )
        return out

    def get(self, name: str) -> SourceProfile | None:
        return self.load_profiles().get(name.lower())

    def list_custom(self) -> list[SourceProfile]:
        return sorted(
            [p for p in self.load_profiles().values() if p.custom],
            key=lambda p: p.label.lower(),
        )

    def is_custom(self, name: str) -> bool:
        profile = self.get(name)
        return bool(profile and profile.custom)

    def get_download_url(self, name: str) -> str:
        profile = self.get(name)
        return profile.download_url if profile else ""

    def upsert_download_url(self, name: str, download_url: str) -> SourceProfile:
        """Persiste URL de download para qualquer fonte (built-in ou custom)."""
        key = name.lower()
        profiles = self.load_profiles()
        existing = profiles.get(key)
        if existing:
            existing.download_url = download_url.strip()
            profiles[key] = existing
        else:
            profiles[key] = SourceProfile(
                name=key,
                label=key.upper(),
                download_url=download_url.strip(),
                custom=False,
            )
        self._write_profiles(profiles)
        return profiles[key]

    def create_custom(self, *, name: str, label: str, download_url: str = "") -> SourceProfile:
        key = normalize_source_name(name)
        profiles = self.load_profiles()
        if key in profiles:
            raise ValueError(f"Tipo de base '{key}' já existe")
        from pricing.sync.connectors import CONNECTORS

        if key in CONNECTORS:
            raise ValueError(f"Identificador '{key}' conflita com fonte integrada")
        profile = SourceProfile(
            name=key,
            label=label.strip() or key,
            download_url=download_url.strip(),
            custom=True,
            created_at=_now_iso(),
        )
        profiles[key] = profile
        self._write_profiles(profiles)
        return profile

    def update_custom(self, name: str, *, label: str | None = None, download_url: str | None = None) -> SourceProfile:
        key = name.lower()
        profiles = self.load_profiles()
        profile = profiles.get(key)
        if not profile or not profile.custom:
            raise ValueError(f"Tipo customizado '{key}' não encontrado")
        if label is not None:
            profile.label = label.strip() or profile.label
        if download_url is not None:
            profile.download_url = download_url.strip()
        profiles[key] = profile
        self._write_profiles(profiles)
        return profile

    def delete_custom(self, name: str) -> bool:
        key = name.lower()
        profiles = self.load_profiles()
        profile = profiles.get(key)
        if not profile or not profile.custom:
            return False
        del profiles[key]
        self._write_profiles(profiles)
        return True

    def _write_profiles(self, profiles: dict[str, SourceProfile]) -> None:
        self._save_raw(
            {
                "sources": {k: v.to_dict() for k, v in sorted(profiles.items())},
            }
        )


_registry: PriceBaseSourceRegistry | None = None


def get_source_registry() -> PriceBaseSourceRegistry:
    global _registry
    if _registry is None:
        _registry = PriceBaseSourceRegistry()
    return _registry
