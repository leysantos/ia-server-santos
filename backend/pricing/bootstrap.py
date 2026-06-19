from __future__ import annotations

import os
from pathlib import Path

from pricing.providers._tabular import parse_tabular_file
from pricing.providers.cicro_provider import CicroProvider
from pricing.providers.excel_provider import ExcelPriceProvider
from pricing.providers.orse_provider import OrseProvider
from pricing.providers.sinapi_provider import SinapiProvider
from pricing.providers.tcpo_provider import TcpoProvider
from pricing.registry.provider_registry import ProviderRegistry

_REGISTERED = False

_DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"
_SUPPORTED_EXT = (".csv", ".xlsx", ".xls", ".json")


def _provider_classes():
    return (
        SinapiProvider,
        OrseProvider,
        TcpoProvider,
        CicroProvider,
        ExcelPriceProvider,
    )


def reset_providers() -> None:
    """Reinicia registry — somente testes."""
    global _REGISTERED
    _REGISTERED = False
    ProviderRegistry.clear()


def ensure_providers_registered() -> None:
    """Registra providers no registry (idempotente)."""
    global _REGISTERED
    if _REGISTERED:
        return
    for cls in _provider_classes():
        ProviderRegistry.register(cls())
    _REGISTERED = True


def _collect_files(base: Path, provider_name: str) -> list[Path]:
    """Coleta arquivos de base: arquivo único ou diretório com múltiplos."""
    files: list[Path] = []
    for ext in _SUPPORTED_EXT:
        single = base / f"{provider_name}{ext}"
        if single.is_file():
            files.append(single)
            return files

    subdir = base / provider_name
    if subdir.is_dir():
        for path in sorted(subdir.iterdir()):
            if path.is_file() and path.suffix.lower() in _SUPPORTED_EXT:
                files.append(path)
    return files


def _merge_load_provider(provider, paths: list[Path]) -> int:
    merged: list[dict] = []
    loaded_from: list[str] = []
    for path in paths:
        rows = parse_tabular_file(path)
        merged.extend(rows)
        loaded_from.append(str(path))
    if not merged:
        return 0
    provider.load(str(paths[0]))
    provider._data = merged  # noqa: SLF001
    if provider._source:  # noqa: SLF001
        provider._source.item_count = len(merged)  # noqa: SLF001
        provider._source.metadata = {  # noqa: SLF001
            **(provider._source.metadata or {}),
            "merged_files": loaded_from,
        }
    return len(merged)


def load_default_bases(data_dir: Path | None = None) -> dict[str, int]:
    """
    Carrega bases de preços:
    - pricing/data/{provider}.csv (arquivo único)
    - pricing/data/{provider}/*.csv (múltiplos arquivos mesclados)
    - PRICING_DATA_DIR aponta para diretório customizado
    """
    ensure_providers_registered()
    base = data_dir or Path(os.environ.get("PRICING_DATA_DIR", _DEFAULT_DATA_DIR))
    loaded: dict[str, int] = {}
    if not base.exists():
        return loaded

    for provider in ProviderRegistry.all():
        paths = _collect_files(base, provider.name)
        if paths:
            count = _merge_load_provider(provider, paths)
            if count:
                loaded[provider.name] = count
    return loaded


def reload_all_bases(data_dir: Path | None = None) -> dict[str, int]:
    """Recarrega todas as bases do disco."""
    for provider in ProviderRegistry.all():
        provider._data = []  # noqa: SLF001
        provider._source = None  # noqa: SLF001
    return load_default_bases(data_dir)


def upload_base_file(provider_name: str, dest_path: Path, merge: bool = True) -> dict[str, int | str]:
    """Carrega arquivo e opcionalmente mescla com base existente."""
    ensure_providers_registered()
    provider = ProviderRegistry.get(provider_name)
    if not provider:
        raise ValueError(f"Provider '{provider_name}' não registrado")

    new_rows = parse_tabular_file(dest_path)
    if merge and provider.is_loaded:
        merged = list(provider._data) + new_rows  # noqa: SLF001
    else:
        merged = new_rows

    from pricing.models.price_source import PriceSource

    provider._data = merged  # noqa: SLF001
    provider._source = PriceSource(  # noqa: SLF001
        name=provider.name,
        label=provider.label,
        item_count=len(merged),
        path=str(dest_path),
        metadata={"last_upload": str(dest_path), "merge": merge},
    )
    return {"provider": provider_name, "item_count": len(merged), "path": str(dest_path)}
