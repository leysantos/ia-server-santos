"""Serviço híbrido de matching de preços (código → vetorial/regras → LLM)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from pricing.budget.composition_index import get_composition_index
from pricing.budget.price_matching_catalog import (
    BASE_PRIORITY,
    CatalogEntry,
    MIN_AUTO_MATCH_SCORE,
    MIN_IMPORTED_CODE_DESC_SCORE,
    MIN_SUGGEST_MATCH_SCORE,
    description_match_score,
    distill_search_queries,
    effective_base_order,
    is_hard_mismatch,
    load_catalog,
    search_catalog,
    units_compatible,
)

logger = logging.getLogger(__name__)

_CODE_PATTERN = re.compile(
    r"\b(SINAPI|SICRO|SEMINF|ORSE|PPD)\s*[:\-]?\s*([0-9][0-9./\-]*)\b",
    re.IGNORECASE,
)
_BARE_CODE = re.compile(r"\b(\d{4,6})(?:/ORSE)?\b", re.IGNORECASE)


@dataclass
class MatchResult:
    entry: CatalogEntry | None
    score: float
    level: str
    candidates: list[dict[str, Any]]
    model_used: str | None = None
    unit_compatible: bool = True
    hard_reject: bool = False
    import_description: str = ""

    def to_payload(self) -> dict[str, Any]:
        entry = self.entry
        hard = self.hard_reject or (
            entry is not None
            and self.import_description
            and is_hard_mismatch(self.import_description, entry.description)
        )
        auto_accept = (
            entry is not None
            and self.unit_compatible
            and self.score >= MIN_AUTO_MATCH_SCORE
            and not hard
        )
        suggest_accept = (
            entry is not None
            and self.score >= MIN_SUGGEST_MATCH_SCORE
            and not hard
        )
        accepted = auto_accept or suggest_accept
        return {
            "base": entry.base if accepted else None,
            "codigo_base": entry.code if accepted else None,
            "descricao_base": entry.description if accepted else None,
            "valor_unitario": entry.price if accepted else None,
            "reference": entry.reference if accepted else None,
            "score_confianca": round(self.score, 4) if self.score else None,
            "match_level": self.level,
            "modelo_utilizado": self.model_used,
            "candidates": self.candidates,
            "unit_compatible": self.unit_compatible,
            "status": "matched" if auto_accept else ("review" if accepted else "review"),
        }


def extract_code_from_description(description: str) -> tuple[str | None, str | None]:
    text = description or ""
    m = _CODE_PATTERN.search(text)
    if m:
        base = m.group(1).upper().replace("PPD", "SEMINF")
        return base, m.group(2).strip()
    m2 = _BARE_CODE.search(text)
    if m2:
        return None, m2.group(1)
    return None, None


def _base_order(price_bases: list[dict[str, Any]] | None = None) -> list[str]:
    return effective_base_order(price_bases)


def _lookup_by_code(
    code: str,
    base_hint: str | None,
    *,
    uf: str,
    unit: str,
    price_bases: list[dict[str, Any]] | None = None,
) -> CatalogEntry | None:
    _entries, by_code = load_catalog(uf=uf, price_bases=price_bases)
    keys = [code.strip(), code.strip().upper()]
    if base_hint == "ORSE" and code.isdigit():
        keys.append(f"{code.zfill(5)}/ORSE")
    candidates: list[CatalogEntry] = []
    for key in keys:
        candidates.extend(by_code.get(key, []))

    order = _base_order(price_bases)
    if base_hint and base_hint in order:
        order = [base_hint] + [b for b in order if b != base_hint]

    for base in order:
        for entry in candidates:
            if entry.base != base:
                continue
            if unit and not units_compatible(unit, entry.unit):
                continue
            return entry
    return candidates[0] if candidates else None


def _validated_code_match(
    description: str,
    entry: CatalogEntry,
    *,
    unit: str,
) -> tuple[CatalogEntry | None, float, bool]:
    """Aceita lookup por código só se a descrição da base for compatível (≥75%)."""
    desc_score = description_match_score(
        description,
        entry.description,
        unit=unit,
        catalog_unit=entry.unit,
    )
    unit_ok = not unit or units_compatible(unit, entry.unit)
    if desc_score >= MIN_IMPORTED_CODE_DESC_SCORE and unit_ok:
        score = min(0.99, 0.82 + desc_score * 0.17)
        if score >= MIN_AUTO_MATCH_SCORE:
            return entry, score, unit_ok
    if desc_score >= MIN_IMPORTED_CODE_DESC_SCORE and not unit_ok:
        return None, desc_score * 0.85, unit_ok
    return None, desc_score, unit_ok


def _text_candidates(
    description: str,
    *,
    uf: str,
    unit: str,
    limit: int = 10,
    price_bases: list[dict[str, Any]] | None = None,
    require_unit: bool = True,
    min_score: float = 0.38,
) -> list[tuple[float, CatalogEntry]]:
    hits: list[tuple[float, CatalogEntry]] = []
    seen: set[str] = set()
    order = _base_order(price_bases)
    search_unit = unit if require_unit else None
    queries = distill_search_queries(description)

    for query in queries:
        for label in order:
            for entry in search_catalog(
                query,
                unit=search_unit,
                base=label,
                limit=limit,
                uf=uf,
                price_bases=price_bases,
                min_score=min_score,
            ):
                key = f"{entry.base}:{entry.code}"
                if key in seen:
                    continue
                seen.add(key)
                sim = description_match_score(
                    description,
                    entry.description,
                    unit=unit,
                    catalog_unit=entry.unit,
                )
                if is_hard_mismatch(description, entry.description):
                    continue
                hits.append((sim, entry))

    if not hits and description.strip():
        tokens = [t for t in re.findall(r"[a-z0-9]{4,}", description.lower()) if len(t) >= 4]
        for token in tokens[:6]:
            for label in order:
                for entry in search_catalog(
                    token,
                    unit=search_unit,
                    base=label,
                    limit=5,
                    uf=uf,
                    price_bases=price_bases,
                    min_score=max(0.28, min_score - 0.05),
                ):
                    key = f"{entry.base}:{entry.code}"
                    if key in seen:
                        continue
                    seen.add(key)
                    sim = description_match_score(
                        description,
                        entry.description,
                        unit=unit,
                        catalog_unit=entry.unit,
                    )
                    if is_hard_mismatch(description, entry.description):
                        continue
                    hits.append((sim * 0.95, entry))

    try:
        index = get_composition_index()
        for item, faiss_score in index.search(description, unit=search_unit or None, top_k=limit):
            family = "SINAPI"
            key = f"{family}:{item.code}"
            if key in seen:
                continue
            seen.add(key)
            cat = CatalogEntry(
                base=family,
                source=item.source or "sinapi",
                reference="",
                code=item.code,
                description=item.description,
                unit=item.unit,
                price=float(item.price or 0),
                default_uf=uf,
            )
            hits.append((float(faiss_score) * 0.35 + description_match_score(
                description, item.description, unit=unit, catalog_unit=item.unit
            ) * 0.65, cat))
            if is_hard_mismatch(description, cat.description):
                hits.pop()
    except Exception as exc:
        logger.debug("FAISS boost indisponível: %s", exc)

    hits.sort(key=lambda x: (-x[0], order.index(x[1].base) if x[1].base in order else 99))
    return hits[: max(limit * 3, 25)]


def _engineering_score(description: str, entry: CatalogEntry, text_sim: float, *, unit: str = "") -> float:
    """Combina score semântico com cobertura de tokens — nunca reduz abaixo do text_sim."""
    semantic = description_match_score(
        description,
        entry.description,
        unit=unit,
        catalog_unit=entry.unit,
    )
    blended = semantic * 0.72 + text_sim * 0.28
    return min(1.0, max(text_sim, semantic, blended))


def _finalize_match(
    description: str,
    unit: str,
    *,
    chosen: CatalogEntry | None,
    best_score: float,
    candidates: list[CatalogEntry],
    cand_dicts: list[dict[str, Any]],
    level: str,
    model_used: str | None,
) -> MatchResult:
    unit_ok = not unit or (chosen is not None and units_compatible(unit, chosen.unit))
    hard = (
        chosen is not None
        and is_hard_mismatch(description, chosen.description)
    )
    if chosen and not hard and best_score >= MIN_SUGGEST_MATCH_SCORE:
        return MatchResult(
            entry=chosen,
            score=best_score if unit_ok else best_score * 0.92,
            level=level if best_score >= MIN_AUTO_MATCH_SCORE and unit_ok else "suggested",
            candidates=cand_dicts,
            model_used=model_used,
            unit_compatible=unit_ok,
            import_description=description,
        )
    return MatchResult(
        entry=None,
        score=best_score,
        level="below_threshold" if best_score < MIN_SUGGEST_MATCH_SCORE else level,
        candidates=cand_dicts,
        model_used=model_used,
        unit_compatible=unit_ok,
        hard_reject=hard,
        import_description=description,
    )


def _llm_pick(
    description: str,
    candidates: list[CatalogEntry],
    *,
    unit: str = "",
    quantity: float = 0,
) -> tuple[CatalogEntry | None, float, str | None]:
    if not candidates:
        return None, 0.0, None
    if len(candidates) < 2:
        return candidates[0], 0.85, None

    try:
        from config import settings
        from models.ollama_client import OllamaClient

        options = "\n".join(
            f"- id={i + 1} | {c.base} {c.code} | {c.description[:120]} | {c.unit}"
            for i, c in enumerate(candidates[:10])
        )
        prompt = (
            "Você é um orçamentista especializado em obras civis.\n"
            "Analise a descrição abaixo e selecione a composição mais compatível dentre as opções.\n"
            "Priorize mesma unidade de medida e maior similaridade semântica.\n"
            "Retorne APENAS o número id da composição mais adequada (ex: 3).\n\n"
            f"Descrição do orçamento:\n{description}\n"
            f"Unidade esperada: {unit or '—'}\n"
            f"Quantidade: {quantity or '—'}\n\nOpções:\n{options}\n"
        )
        client = OllamaClient(timeout=settings.ollama_budget_timeout)
        model = settings.ollama_budget_model
        raw, used_model = client.generate(prompt, model=model, options={"temperature": 0.1})
        raw = raw.strip()
        m = re.search(r"\b(\d{1,2})\b", raw)
        if m:
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(candidates):
                picked = candidates[idx]
                pick_score = description_match_score(
                    description,
                    picked.description,
                    unit=unit,
                    catalog_unit=picked.unit,
                )
                if pick_score >= MIN_SUGGEST_MATCH_SCORE and not is_hard_mismatch(description, picked.description):
                    return picked, min(0.96, 0.78 + pick_score * 0.18), used_model
    except Exception as exc:
        logger.debug("LLM re-rank indisponível: %s", exc)
    return candidates[0], 0.82, None


class PriceMatchingService:
    def __init__(
        self,
        *,
        uf: str = "AM",
        use_llm: bool = True,
        price_bases: list[dict[str, Any]] | None = None,
    ) -> None:
        self.uf = uf.upper()
        self.use_llm = use_llm
        self.price_bases = list(price_bases or [])

    def match_row(
        self,
        description: str,
        unit: str,
        quantity: float,
        *,
        existing_code: str | None = None,
        existing_base: str | None = None,
        aggressive: bool = False,
        imported_code: str | None = None,
    ) -> MatchResult:
        code_from_sheet = (imported_code or existing_code or "").strip() or None

        if code_from_sheet:
            entry = _lookup_by_code(
                code_from_sheet,
                existing_base,
                uf=self.uf,
                unit="" if aggressive else unit,
                price_bases=self.price_bases or None,
            )
            if entry:
                validated, score, unit_ok = _validated_code_match(description, entry, unit=unit)
                if validated:
                    return MatchResult(
                        entry=validated,
                        score=score,
                        level="imported_code",
                        candidates=[entry.to_dict() | {"score": score}],
                        unit_compatible=unit_ok,
                        import_description=description,
                    )

        base_hint, code = extract_code_from_description(description)

        if code:
            entry = _lookup_by_code(
                code,
                base_hint,
                uf=self.uf,
                unit="" if aggressive else unit,
                price_bases=self.price_bases or None,
            )
            if entry:
                validated, score, unit_ok = _validated_code_match(description, entry, unit=unit)
                if validated:
                    return MatchResult(
                        entry=validated,
                        score=score,
                        level="code",
                        candidates=[entry.to_dict() | {"score": score}],
                        unit_compatible=unit_ok,
                    )

        text_hits = _text_candidates(
            description,
            uf=self.uf,
            unit=unit,
            limit=20,
            price_bases=self.price_bases or None,
            require_unit=not aggressive,
            min_score=0.38,
        )
        if not aggressive:
            relaxed_hits = _text_candidates(
                description,
                uf=self.uf,
                unit=unit,
                limit=20,
                price_bases=self.price_bases or None,
                require_unit=False,
                min_score=0.35,
            )
            merged: dict[str, tuple[float, CatalogEntry]] = {}
            for sim, entry in text_hits + relaxed_hits:
                key = f"{entry.base}:{entry.code}"
                prev = merged.get(key)
                if prev is None or sim > prev[0]:
                    merged[key] = (sim, entry)
            text_hits = sorted(merged.values(), key=lambda x: -x[0])[:15]
        if not text_hits:
            return MatchResult(
                entry=None,
                score=0.0,
                level="none",
                candidates=[],
                unit_compatible=True,
                import_description=description,
            )

        order = _base_order(self.price_bases or None)
        scored: list[tuple[float, CatalogEntry]] = []
        for sim, entry in text_hits:
            final = _engineering_score(description, entry, sim, unit=unit)
            if is_hard_mismatch(description, entry.description):
                continue
            if final < MIN_SUGGEST_MATCH_SCORE:
                continue
            scored.append((final, entry))
        if not scored:
            fallback = [
                (sim, entry)
                for sim, entry in text_hits
                if not is_hard_mismatch(description, entry.description)
            ]
            return MatchResult(
                entry=None,
                score=fallback[0][0] if fallback else 0.0,
                level="below_threshold",
                candidates=[
                    e.to_dict() | {"score": s}
                    for s, e in sorted(fallback, key=lambda x: -x[0])[:10]
                ],
                unit_compatible=True,
                import_description=description,
            )
        scored.sort(
            key=lambda x: (
                -(1 if (not unit or units_compatible(unit, x[1].unit)) else 0),
                -(1 if float(x[1].price or 0) > 0 else 0),
                -x[0],
                order.index(x[1].base) if x[1].base in order else 99,
            )
        )

        candidates = [e for _, e in scored[:10]]
        cand_dicts = [e.to_dict() | {"score": s} for s, e in scored[:10]]
        best_score, best_entry = scored[0]
        unit_ok = not unit or units_compatible(unit, best_entry.unit)

        chosen = best_entry
        model_used: str | None = None
        if self.use_llm and best_score < 0.95 and len(candidates) >= 1:
            llm_pick, llm_score, model_used = _llm_pick(
                description,
                candidates,
                unit=unit,
                quantity=quantity,
            )
            if llm_pick:
                llm_desc = description_match_score(
                    description,
                    llm_pick.description,
                    unit=unit,
                    catalog_unit=llm_pick.unit,
                )
                if llm_desc >= MIN_SUGGEST_MATCH_SCORE and not is_hard_mismatch(description, llm_pick.description):
                    chosen = llm_pick
                    best_score = max(best_score, min(0.96, llm_desc))
                    unit_ok = not unit or units_compatible(unit, chosen.unit)

        if not unit_ok and not aggressive and scored:
            for alt_score, alt_entry in scored:
                if units_compatible(unit, alt_entry.unit):
                    chosen = alt_entry
                    best_score = alt_score
                    unit_ok = True
                    break

        return _finalize_match(
            description,
            unit,
            chosen=chosen,
            best_score=best_score,
            candidates=candidates,
            cand_dicts=cand_dicts,
            level="text" if best_score < 1.0 else "exact",
            model_used=model_used,
        )

    def apply_pricing(
        self,
        match: MatchResult,
        quantity: float,
        *,
        increase_index: float = 1.0,
    ) -> dict[str, Any]:
        payload = match.to_payload()
        if not payload.get("codigo_base") or not match.entry:
            payload["valor_unitario"] = None
            payload["valor_total"] = None
            payload["valor_unitario_base"] = None
            return payload
        unit_base = float(match.entry.price or 0)
        unit_adj = unit_base * float(increase_index or 1.0)
        payload["valor_unitario"] = round(unit_adj, 4)
        payload["valor_total"] = round(unit_adj * float(quantity or 0), 2)
        payload["valor_unitario_base"] = round(unit_base, 4)
        if not match.unit_compatible:
            payload["status"] = "review"
        return payload
