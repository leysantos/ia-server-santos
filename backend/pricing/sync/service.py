"""Orquestra download → ingestão knowledge → FAISS → providers."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from config.settings import KNOWLEDGE_DIR
from pricing.sync.connectors import CONNECTORS, get_connector, is_known_source
from pricing.sync.state import PriceSyncStateStore, SourceSyncRecord

logger = logging.getLogger(__name__)

_SYNC_CACHE = KNOWLEDGE_DIR / "sync" / "price_bases"
_service: "PriceSyncService | None" = None

# Bases tabulares de preço — operacionais via price_bank, não via catálogo/FAISS RAG.
_PRICE_SOURCES = frozenset({"sinapi", "tcpo", "orse", "cicro", "ppd_seminf"})


def _is_price_bank_source(name: str) -> bool:
    if name in _PRICE_SOURCES:
        return True
    from pricing.sync.source_registry import get_source_registry

    return get_source_registry().is_custom(name)


class PriceSyncService:
    def __init__(self, state_store: PriceSyncStateStore | None = None) -> None:
        self.state = state_store or PriceSyncStateStore()

    def list_sources(self) -> list[dict[str, Any]]:
        from pricing.sync.source_registry import get_source_registry

        records = self.state.load()
        registry = get_source_registry()
        profiles = registry.load_profiles()
        out: list[dict[str, Any]] = []

        seen: set[str] = set()
        for name, connector in sorted(CONNECTORS.items()):
            seen.add(name)
            rec = records.get(name)
            profile = profiles.get(name)
            out.append(
                {
                    "name": name,
                    "label": connector.label,
                    "auto_download": connector.supports_auto_download(),
                    "download_url": profile.download_url if profile else "",
                    "custom": False,
                    "can_delete": False,
                    "last_sync": rec.to_dict() if rec else None,
                }
            )

        for profile in registry.list_custom():
            if profile.name in seen:
                continue
            rec = records.get(profile.name)
            out.append(
                {
                    "name": profile.name,
                    "label": profile.label,
                    "auto_download": False,
                    "download_url": profile.download_url,
                    "custom": True,
                    "can_delete": True,
                    "last_sync": rec.to_dict() if rec else None,
                }
            )

        out.sort(key=lambda s: s["label"].lower())
        return out

    def status(self) -> dict[str, Any]:
        from pricing.budget.price_bank_store import PriceBankStore

        records = self.state.load()
        bank = PriceBankStore().stats()
        return {
            "sources": {k: v.to_dict() for k, v in records.items()},
            "available": sorted(CONNECTORS.keys()),
            "bank": bank,
        }

    def bank_stats(self, reference: str | None = None) -> dict[str, Any]:
        from pricing.budget.price_bank_index import PriceBankIndex
        from pricing.budget.price_bank_store import PriceBankStore

        ref = PriceBankIndex.resolve_reference(reference)
        stats = PriceBankStore.for_reference(ref).stats()
        idx = PriceBankIndex.load()
        stats["references"] = idx.list_references()
        stats["active_reference"] = idx.active_reference
        return stats

    def get_open_composition(
        self,
        code: str,
        *,
        uf: str = "SP",
        reference: str | None = None,
    ) -> dict[str, Any] | None:
        from pricing.budget.price_bank_index import PriceBankIndex
        from pricing.budget.price_bank_store import PriceBankStore

        ref = PriceBankIndex.resolve_reference(reference)
        return PriceBankStore.for_reference(ref).get_open_composition(code, uf=uf.upper())

    def list_references(self) -> list[dict[str, Any]]:
        from pricing.budget.price_bank_store import PriceBankStore

        return PriceBankStore.list_all_references()

    def bank_inventory(self) -> dict[str, Any]:
        """Inventário agrupado por fonte + totais globais do price_bank."""
        from pricing.budget.price_bank_index import PriceBankIndex

        idx = PriceBankIndex.load()
        totals: dict[str, int] = {
            "compositions_closed": 0,
            "compositions_open": 0,
            "insumos": 0,
            "open_items_total": 0,
        }
        by_source: dict[str, dict[str, Any]] = {}

        for entry in idx.references:
            src = (entry.source or "sinapi").lower()
            counts = entry.counts or {}
            for key in totals:
                totals[key] += int(counts.get(key) or 0)

            if src not in by_source:
                connector = CONNECTORS.get(src)
                from pricing.sync.source_registry import get_source_registry

                profile = get_source_registry().get(src)
                label = (
                    connector.label
                    if connector
                    else (profile.label if profile else src.upper())
                )
                by_source[src] = {
                    "source": src,
                    "label": label,
                    "auto_download": connector.supports_auto_download() if connector else False,
                    "periods": [],
                }
            by_source[src]["periods"].append(
                {
                    "reference": entry.reference,
                    "label": entry.label,
                    "synced_at": entry.synced_at,
                    "default_uf": entry.default_uf,
                    "active": entry.reference == idx.active_reference,
                    "counts": counts,
                    "metadata": entry.metadata,
                }
            )

        for group in by_source.values():
            group["periods"].sort(key=lambda p: p["reference"], reverse=True)

        sources_meta = self.list_sources()
        known = {g["source"] for g in by_source.values()}
        for meta in sources_meta:
            if meta["name"] not in known:
                by_source[meta["name"]] = {
                    "source": meta["name"],
                    "label": meta["label"],
                    "auto_download": meta["auto_download"],
                    "periods": [],
                    "last_sync": meta.get("last_sync"),
                }

        groups = sorted(by_source.values(), key=lambda g: g["label"])
        return {
            "totals": totals,
            "period_count": len(idx.references),
            "source_count": len([g for g in groups if g.get("periods")]),
            "groups": groups,
            "sources": sources_meta,
            "active_reference": idx.active_reference,
        }

    def set_active_reference(self, reference: str) -> str:
        from pricing.budget.price_bank_store import PriceBankStore

        return PriceBankStore.set_active_reference(reference)

    def delete_reference(self, reference: str) -> dict[str, Any]:
        from pricing.budget.price_bank_purge import delete_price_bank_reference

        return delete_price_bank_reference(reference)

    def create_custom_source(
        self, *, name: str, label: str, download_url: str = ""
    ) -> dict[str, Any]:
        from pricing.sync.source_registry import get_source_registry

        profile = get_source_registry().create_custom(
            name=name, label=label, download_url=download_url
        )
        return profile.to_dict()

    def update_source_config(
        self,
        name: str,
        *,
        download_url: str | None = None,
        label: str | None = None,
    ) -> dict[str, Any]:
        from pricing.sync.source_registry import get_source_registry

        registry = get_source_registry()
        key = name.lower()
        if registry.is_custom(key):
            profile = registry.update_custom(key, label=label, download_url=download_url)
        elif download_url is not None:
            profile = registry.upsert_download_url(key, download_url)
        else:
            raise ValueError(f"Fonte '{key}' não permite alterar rótulo")
        return profile.to_dict()

    def delete_custom_source(self, name: str) -> dict[str, Any]:
        from pricing.sync.source_registry import get_source_registry

        removed = get_source_registry().delete_custom(name)
        if not removed:
            raise ValueError(f"Tipo customizado '{name}' não encontrado")
        return {"deleted": name.lower()}

    def purge_sinapi_faiss(self, reference: str | None = None) -> dict[str, Any]:
        from pricing.budget.price_bank_purge import purge_sinapi_faiss_chunks

        return purge_sinapi_faiss_chunks(reference=reference)

    def sync(
        self,
        source: str,
        *,
        index_faiss: bool = False,
        reload_providers: bool = True,
        set_active: bool = False,
        on_progress: Any | None = None,
        **connector_options: Any,
    ) -> dict[str, Any]:
        name = source.lower()
        connector = get_connector(name)

        def emit(
            percent: int,
            phase: str,
            message: str,
            *,
            current: int = 0,
            total: int = 0,
        ) -> None:
            if on_progress:
                on_progress(
                    {
                        "phase": phase,
                        "percent": min(100, max(0, int(percent))),
                        "message": message,
                        "current": current,
                        "total": total,
                    }
                )

        record = SourceSyncRecord(source=name, status="running")
        self.state.update(record)

        try:
            emit(3, "start", f"Iniciando importação {connector.label}…")

            def connector_progress(data: dict[str, Any]) -> None:
                inner = int(data.get("percent") or 0)
                phase = str(data.get("phase") or "download")
                scaled = 5 + round(inner * 0.6)
                emit(
                    scaled,
                    phase,
                    str(data.get("message") or ""),
                    current=int(data.get("current") or 0),
                    total=int(data.get("total") or 0),
                )

            emit(5, "download", "Obtendo arquivo da base…")
            download = connector.download(
                dest_dir=_SYNC_CACHE / name,
                on_progress=connector_progress,
                set_active=set_active,
                **connector_options,
            )
            emit(68, "bank", "Banco de preços gravado")

            ingest: dict[str, Any] = {"status": "skipped", "reason": "price_bank_only"}
            faiss_summary: dict[str, Any] | None = None
            if _is_price_bank_source(name):
                emit(72, "ingest", "Banco operacional — sem catálogo RAG")
                if index_faiss:
                    logger.warning(
                        "index_faiss ignorado para %s — use price_bank + composition_index",
                        name,
                    )
            else:
                emit(72, "ingest", "Registrando no catálogo de conhecimento…")
                ingest = self._ingest_file(
                    download.local_path,
                    content_type=name,
                    name=f"{connector.label} {download.reference}",
                    description=f"Sincronizado automaticamente — ref {download.reference}",
                    set_active=set_active,
                )
                emit(80, "ingest", "Catálogo atualizado")
                if index_faiss:
                    emit(84, "index", "Indexando FAISS (base de custos)…")
                    faiss_summary = self._index_knowledge_base(name)
                    emit(92, "index", "Indexação FAISS concluída")

            provider_summary: dict[str, Any] | None = None
            if reload_providers:
                emit(94, "providers", "Recarregando provedores de preço…")
                provider_summary = self._reload_providers(name, download.local_path)
                emit(98, "providers", "Provedores atualizados")

            closed_n = int((download.metadata or {}).get("compositions_closed") or download.item_count or 0)
            open_n = int((download.metadata or {}).get("compositions_open") or 0)
            ins_n = int((download.metadata or {}).get("insumos") or 0)
            emit(
                100,
                "done",
                f"Concluído — {closed_n:,} fechadas, {open_n:,} abertas, {ins_n:,} insumos".replace(",", "."),
                current=closed_n,
                total=closed_n,
            )

            record = SourceSyncRecord(
                source=name,
                status="ok",
                reference=download.reference,
                item_count=download.item_count or ingest.get("price_item_count", 0),
                document_id=str(ingest.get("document_id", "")),
                path=str(ingest.get("target", download.local_path)),
                metadata={
                    **download.metadata,
                    "ingest_status": ingest.get("status"),
                    "faiss": faiss_summary,
                    "providers": provider_summary,
                },
            )
            self.state.update(record)
            return {
                "source": name,
                "status": "ok",
                "reference": download.reference,
                "item_count": record.item_count,
                "document_id": record.document_id,
                "path": record.path,
                "download": {
                    "local_path": str(download.local_path),
                    "metadata": download.metadata,
                },
                "ingest": ingest,
                "faiss": faiss_summary,
                "providers": provider_summary,
            }
        except Exception as exc:
            logger.exception("Falha sync %s: %s", name, exc)
            record = SourceSyncRecord(
                source=name,
                status="error",
                error=str(exc),
            )
            self.state.update(record)
            raise

    def sync_all(
        self,
        *,
        sources: list[str] | None = None,
        skip_manual: bool = True,
        **options: Any,
    ) -> dict[str, Any]:
        targets = sources or sorted(CONNECTORS.keys())
        results: dict[str, Any] = {"ok": [], "skipped": [], "errors": []}
        for name in targets:
            connector = get_connector(name)
            if skip_manual and not connector.supports_auto_download():
                results["skipped"].append(
                    {"source": name, "reason": "requer arquivo local (ORSE/TCPO/CICRO)"}
                )
                continue
            try:
                results["ok"].append(self.sync(name, **options))
            except Exception as exc:
                results["errors"].append({"source": name, "error": str(exc)})
        return results

    @staticmethod
    def _ingest_file(
        path: Path,
        *,
        content_type: str,
        name: str,
        description: str,
        set_active: bool,
    ) -> dict[str, Any]:
        from core.knowledge.ingestion import DisciplineIngester

        ingester = DisciplineIngester()
        return ingester.ingest(
            path,
            content_type_hint=content_type,
            discipline_hint="orcamento",
            copy=True,
            force=True,
            name=name,
            description=description,
            register_price_base=set_active,
        )

    @staticmethod
    def _index_knowledge_base(base_key: str) -> dict[str, Any]:
        from core.knowledge.knowledge_indexer import KnowledgeIndexer

        indexer = KnowledgeIndexer()
        return indexer.index_base(base_key, force=True)

    @staticmethod
    def _reload_providers(source: str, csv_path: Path) -> dict[str, Any]:
        from pricing.bootstrap import ensure_providers_registered
        from pricing.registry.provider_registry import ProviderRegistry

        ensure_providers_registered()
        provider_name = source if source in ("sinapi", "orse", "tcpo", "cicro") else "sinapi"

        from pricing.budget.price_bank_index import PriceBankIndex
        from pricing.budget.price_bank_store import PriceBankStore

        ref = PriceBankIndex.resolve_reference(None)
        bank_rows = PriceBankStore.for_reference(ref).closed_as_provider_rows()
        if bank_rows and provider_name == "sinapi":
            rows_for_provider = bank_rows
        else:
            from pricing.providers._tabular import parse_tabular_file

            rows_for_provider = parse_tabular_file(csv_path)

        pricing_data = Path(__file__).resolve().parents[1] / "data" / provider_name
        pricing_data.mkdir(parents=True, exist_ok=True)
        dest = pricing_data / csv_path.name
        shutil.copy2(csv_path, dest)

        from pricing.models.price_source import PriceSource

        provider = ProviderRegistry.get(provider_name)
        if provider and rows_for_provider:
            provider._data = rows_for_provider  # noqa: SLF001
            provider._source = PriceSource(  # noqa: SLF001
                name=provider_name,
                label=provider.label,
                item_count=len(rows_for_provider),
                path=str(dest),
            )
        result = {"provider": provider_name, "item_count": len(rows_for_provider), "path": str(dest)}
        item_count = len(rows_for_provider)

        if provider_name == "sinapi" and rows_for_provider:
            try:
                from pricing.budget.composition_index import get_composition_index

                index = get_composition_index()
                if len(rows_for_provider) > 800:
                    index.schedule_rebuild(rows_for_provider, label=csv_path.stem, source="sinapi")
                else:
                    index.rebuild(rows_for_provider, label=csv_path.stem, source="sinapi")
            except Exception as exc:
                logger.warning("FAISS composições após sync: %s", exc)

        return {**result, "item_count": item_count}


def get_price_sync_service() -> PriceSyncService:
    global _service
    if _service is None:
        _service = PriceSyncService()
    return _service
