"""Catálogo de serviços WBS extraídos de modelos PPD importados (código + descrição exatos)."""

from __future__ import annotations

import json
import logging
import re
import threading
from pathlib import Path
from typing import Any, Optional

from pricing.budget.budget_model_extractor import budget_model_sidecar_path
from pricing.core.price_matcher import PriceMatcher

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_catalog: Optional["BudgetModelCatalog"] = None


def _norm_name(name: str) -> str:
    return PriceMatcher().normalize(name)


def _extract_base_code(raw: str) -> str:
    """106913.22.9.SEMINF → 106913; 100656 → 100656."""
    code = (raw or "").strip()
    if not code:
        return ""
    if "." in code:
        return code.split(".")[0]
    return code


class BudgetModelCatalog:
    """Índice nome de serviço → código SINAPI/SEMINF dos modelos importados."""

    def __init__(self) -> None:
        self._entries: list[dict[str, Any]] = []
        self._matcher = PriceMatcher()
        self.reload()

    def reload(self) -> None:
        from core.knowledge.catalog import read_catalog

        entries: list[dict[str, Any]] = []
        seen: set[str] = set()

        for row in read_catalog():
            if row.get("content_type") not in ("modelos_orcamento", "sinapi", "tcpo"):
                continue
            path = Path(row.get("path", ""))
            if not path.is_file():
                continue
            sidecar = budget_model_sidecar_path(path)
            if not sidecar.is_file():
                continue
            try:
                model = json.loads(sidecar.read_text(encoding="utf-8"))
            except Exception:
                continue
            model_name = row.get("name") or path.stem
            for etapa in model.get("etapas") or []:
                for svc in etapa.get("services") or []:
                    name = str(svc.get("name") or "").strip()
                    raw_code = str(svc.get("sinapi_code") or svc.get("code") or "").strip()
                    if not name or not raw_code:
                        continue
                    base_code = _extract_base_code(raw_code)
                    key = f"{base_code}|{_norm_name(name)}"
                    if key in seen:
                        continue
                    seen.add(key)
                    entries.append(
                        {
                            "name": name,
                            "name_norm": _norm_name(name),
                            "code": raw_code,
                            "base_code": base_code,
                            "unit": svc.get("unit") or "",
                            "etapa": etapa.get("name") or "",
                            "model": model_name,
                            "obra_type": model.get("obra_type"),
                        }
                    )

        self._entries = entries
        logger.info("BudgetModelCatalog: %s serviços WBS indexados", len(entries))

    def lookup(
        self,
        line_name: str,
        *,
        scope: str = "",
        min_score: float = 0.55,
    ) -> Optional[dict[str, Any]]:
        if not line_name or not self._entries:
            return None

        scope_l = (scope or "").lower()
        candidates = self._entries
        if scope_l:
            filtered = [
                e
                for e in self._entries
                if scope_l in e["model"].lower()
                or scope_l in (e.get("etapa") or "").lower()
                or (
                    any(k in scope_l for k in ("passarela", "ponte"))
                    and any(k in e["model"].lower() for k in ("passarela", "ponte"))
                )
            ]
            if filtered:
                candidates = filtered

        best: tuple[float, dict[str, Any]] | None = None
        for entry in candidates:
            score = self._matcher.match_score(
                line_name, entry["name"], None, entry.get("unit") or None
            )
            if score >= min_score and (best is None or score > best[0]):
                best = (score, entry)

        return best[1] if best else None


def reload_budget_model_catalog() -> None:
    global _catalog
    with _lock:
        if _catalog is not None:
            _catalog.reload()
        else:
            _catalog = BudgetModelCatalog()


def get_budget_model_catalog() -> BudgetModelCatalog:
    global _catalog
    with _lock:
        if _catalog is None:
            _catalog = BudgetModelCatalog()
        return _catalog
