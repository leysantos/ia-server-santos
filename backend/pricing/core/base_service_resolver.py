from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from pricing.budget.budget_model_catalog import get_budget_model_catalog
from pricing.budget.composition_index import get_composition_index, rebuild_composition_index_from_provider
from pricing.core.price_matcher import PriceMatcher
from pricing.core.pricing_engine import PricingEngine
from pricing.models.price_item import PriceItem
from pricing.registry.provider_registry import ProviderRegistry

logger = logging.getLogger(__name__)

_LLM_PICK_PROMPT = """Você é engenheiro de orçamento municipal (PPD/SINAPI/SEMINF).

Serviço planejado na WBS:
- Nome: {line_name}
- Busca na base: {query}
- Unidade esperada: {unit}
{context_block}
Abaixo estão composições REAIS existentes na base de preços importada (código | descrição completa | un | preço).
Escolha a composição que um orçamentista humano usaria para ESTE serviço específico.

REGRAS:
- Escolha SOMENTE um código da lista, ou NONE se nenhuma composição for adequada.
- NÃO invente código.
- Prefira descrição que corresponda ao serviço (ex.: escavação para escavação, não estaca).
- NONE é preferível a código errado.

{candidates}

Responda SOMENTE o código numérico ou NONE."""


@dataclass
class ResolveResult:
    query: str
    unit: str | None
    item: PriceItem | None = None
    method: str = "none"
    score: float = 0.0
    llm_model: str | None = None
    candidates: list[dict[str, Any]] = field(default_factory=list)
    faiss_available: bool = False
    llm_pool_size: int = 0


class BaseServiceResolver:
    """
    Resolve serviços a partir das bases carregadas.

    Com LLM (modo engenheiro): busca ampla na base → LLM escolhe composição → validação.
    Sem LLM: match lexical validado (auto-accept se score alto).
    """

    MIN_AUTO_SCORE = 0.78
    MIN_LLM_PICK_SCORE = 0.40
    RETRIEVAL_MIN_SCORE = 0.24
    FUZZY_SCAN_CAP = 80
    FAISS_RETRIEVE_K = 30
    LLM_POOL_MAX = 30
    UI_CANDIDATES = 5

    def __init__(self, engine: PricingEngine | None = None, llm_client: Any | None = None) -> None:
        self.engine = engine or PricingEngine()
        self.matcher = PriceMatcher()
        self.llm = llm_client
        self._composition_index = get_composition_index()

    def loaded_sources(self) -> list[str]:
        return [p.name for p in ProviderRegistry.all() if p.is_loaded and len(getattr(p, "_data", [])) > 0]

    def ensure_faiss_index(self) -> dict[str, Any]:
        return rebuild_composition_index_from_provider()

    def resolve(
        self,
        query: str,
        unit: str | None = None,
        source_priority: list[str] | None = None,
        use_llm: bool = True,
    ) -> Optional[PriceItem]:
        return self.resolve_with_details(
            query, unit=unit, source_priority=source_priority, use_llm=use_llm
        ).item

    def resolve_with_details(
        self,
        query: str,
        unit: str | None = None,
        source_priority: list[str] | None = None,
        use_llm: bool = True,
        line_name: str | None = None,
        line_code: str | None = None,
        scope: str | None = None,
        service_context: str | None = None,
        budget_prompt_text: str | None = None,
    ) -> ResolveResult:
        result = ResolveResult(query=query, unit=unit)
        if not query or not query.strip():
            return result

        priority = self._effective_priority(source_priority)
        if not priority:
            return result

        if line_code and str(line_code).strip() not in ("", "-", "--"):
            item = self._lookup_by_code(str(line_code).strip(), priority)
            if item:
                result.item = item
                result.score = 1.0
                result.method = "code"
                result.candidates = [self._candidate_dict(item, 1.0)]
                return result

        anchor = (line_name or query).strip()
        wbs = get_budget_model_catalog().lookup(anchor, scope=scope or "")
        if wbs:
            item = self._lookup_by_code(wbs["base_code"], priority)
            if item and self.matcher.accepts_match(
                line_name, query, item.description, unit, item.unit, score=0.9
            ):
                result.item = item
                result.score = 0.95
                result.method = "model_wbs"
                result.candidates = [self._candidate_dict(item, 0.95)]
                return result

        self.ensure_faiss_index()
        provider_rows = self._count_loaded_rows(priority)
        faiss_count = self._composition_index.store.count()
        result.faiss_available = faiss_count > 0 and (
            provider_rows <= 800 or faiss_count >= provider_rows * 0.5
        )

        search_text = f"{line_name or ''} {query}".strip()
        faiss_hits = (
            self._composition_index.search(search_text, unit=unit, top_k=self.FAISS_RETRIEVE_K)
            if result.faiss_available
            else []
        )

        fuzzy_items = self._collect_fuzzy_candidates(line_name, query, unit, priority)
        ranked = self._merge_candidates(faiss_hits, fuzzy_items, line_name, query, unit)

        if not ranked:
            result.method = "unresolved"
            return result

        llm_pool = ranked[: self.LLM_POOL_MAX]
        result.llm_pool_size = len(llm_pool)
        result.candidates = [
            self._candidate_dict(item, score) for score, item in llm_pool[: self.UI_CANDIDATES]
        ]

        best_score, best_item = ranked[0]

        if use_llm and self.llm:
            picked, model, pick_score = self._llm_pick(
                line_name,
                query,
                unit,
                llm_pool,
                service_context=service_context,
                budget_prompt_text=budget_prompt_text,
            )
            if picked:
                if pick_score >= self.MIN_LLM_PICK_SCORE and self.matcher.accepts_match(
                    line_name, query, picked.description, unit, picked.unit, pick_score
                ):
                    result.item = picked
                    result.score = pick_score
                    result.method = "llm"
                    result.llm_model = model
                    return result
                logger.info(
                    "LLM pick rejeitado na validação linha=%r code=%s score=%.2f",
                    line_name,
                    picked.code,
                    pick_score,
                )

        validated = [
            (score, item)
            for score, item in ranked
            if self.matcher.accepts_match(
                line_name, query, item.description, unit, item.unit, score
            )
        ]

        if validated and validated[0][0] >= self.MIN_AUTO_SCORE:
            score, item = validated[0]
            result.item = item
            result.score = score
            result.method = "faiss" if faiss_hits else "fuzzy"
            return result

        if not use_llm and validated:
            score, item = validated[0]
            if score >= 0.55:
                result.item = item
                result.score = score
                result.method = "fuzzy"
                return result

        logger.info(
            "Sem match confiável linha=%r query=%r best=%s score=%.2f pool=%s",
            line_name,
            query,
            best_item.code,
            best_score,
            len(llm_pool),
        )
        result.method = "unresolved"
        return result

    def _lookup_by_code(self, code: str, priority: list[str]) -> Optional[PriceItem]:
        for provider in ProviderRegistry.iter_priority(priority):
            if not provider.is_loaded:
                continue
            item = provider.get_by_code_flexible(code)
            if item:
                return item
        return None

    @staticmethod
    def _candidate_dict(item: PriceItem, score: float) -> dict[str, Any]:
        return {
            "code": item.code,
            "description": item.description[:160],
            "unit": item.unit,
            "price": item.price,
            "score": round(score, 4),
            "source": item.source,
        }

    def _effective_priority(self, source_priority: list[str] | None) -> list[str]:
        loaded = self.loaded_sources()
        if not loaded:
            return []
        if source_priority:
            return [s for s in source_priority if s in loaded]
        return loaded

    def _count_loaded_rows(self, priority: list[str]) -> int:
        total = 0
        for provider in ProviderRegistry.iter_priority(priority):
            if provider.is_loaded:
                total += len(getattr(provider, "_data", []) or [])
        return total

    def _collect_fuzzy_candidates(
        self,
        line_name: str | None,
        query: str,
        unit: str | None,
        priority: list[str],
    ) -> list[tuple[float, PriceItem]]:
        scored: list[tuple[float, PriceItem]] = []
        seen: set[str] = set()

        for provider in ProviderRegistry.iter_priority(priority):
            if not provider.is_loaded:
                continue
            for row in getattr(provider, "_data", []) or []:
                item = provider._row_to_item(row)  # noqa: SLF001
                key = f"{item.source}:{item.code}"
                if key in seen:
                    continue
                seen.add(key)
                score = self.matcher.composite_score(
                    line_name, query, item.description, unit, item.unit
                )
                if score >= self.RETRIEVAL_MIN_SCORE:
                    scored.append((score, item))

        scored.sort(key=lambda x: (-x[0], x[1].price))
        return scored[: self.FUZZY_SCAN_CAP]

    def _merge_candidates(
        self,
        faiss_hits: list[tuple[PriceItem, float]],
        fuzzy_scored: list[tuple[float, PriceItem]],
        line_name: str | None,
        query: str,
        unit: str | None,
    ) -> list[tuple[float, PriceItem]]:
        by_code: dict[str, tuple[float, PriceItem]] = {}

        for item, faiss_score in faiss_hits:
            lexical = self.matcher.composite_score(
                line_name, query, item.description, unit, item.unit
            )
            if lexical < 0.22:
                continue
            combined = round(0.30 * faiss_score + 0.70 * lexical, 4)
            by_code[item.code] = (combined, item)

        for score, item in fuzzy_scored:
            rescore = self.matcher.composite_score(
                line_name, query, item.description, unit, item.unit
            )
            existing = by_code.get(item.code)
            best = max(score, rescore)
            if existing and existing[0] >= best:
                continue
            by_code[item.code] = (best, item)

        merged = list(by_code.values())
        merged.sort(key=lambda x: (-x[0], x[1].price))
        return merged

    def _llm_pick(
        self,
        line_name: str | None,
        query: str,
        unit: str | None,
        scored: list[tuple[float, PriceItem]],
        service_context: str | None = None,
        budget_prompt_text: str | None = None,
    ) -> tuple[Optional[PriceItem], Optional[str], float]:
        if not self.llm or not scored:
            return None, None, 0.0
        try:
            if not getattr(self.llm, "ping", lambda: True)():
                return None, None, 0.0
        except Exception:
            return None, None, 0.0

        lines = []
        code_map: dict[str, PriceItem] = {}
        score_map: dict[str, float] = {}
        for score, item in scored:
            desc = item.description.replace("\n", " ")[:220]
            lines.append(
                f"{item.code} | {desc} | {item.unit} | R$ {item.price:.2f}"
            )
            code_map[str(item.code)] = item
            score_map[str(item.code)] = score

        context_block = ""
        if service_context and service_context.strip():
            context_block = f"- Contexto: {service_context.strip()}\n"

        prompt = _LLM_PICK_PROMPT.format(
            line_name=line_name or query,
            query=query,
            unit=unit or "nao especificada",
            context_block=context_block,
            candidates="\n".join(lines),
        )
        try:
            from core.models.budget_model_routing import budget_generate

            raw, model = budget_generate(
                prompt,
                user_text=budget_prompt_text or query or (line_name or ""),
                task="pricing",
                client=self.llm,
                line_name=line_name,
                query=query,
                service_context=service_context,
            )
        except Exception as exc:
            logger.warning("LLM pick falhou: %s", exc)
            return None, None, 0.0

        code = self._extract_code(raw)
        if not code or code.upper() == "NONE":
            return None, model, 0.0
        item = code_map.get(code)
        if not item:
            return None, model, 0.0
        return item, model, score_map.get(code, 0.0)

    @staticmethod
    def _extract_code(text: str) -> str | None:
        cleaned = text.strip()
        if cleaned.upper() == "NONE":
            return None
        match = re.search(r"\b(\d{4,8})\b", cleaned)
        return match.group(1) if match else None
