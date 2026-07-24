"""Catálogo unificado de composições fechadas (SINAPI, SICRO, SEMINF, ORSE)."""

from __future__ import annotations

import logging
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from pricing.budget.price_bank_index import PriceBankIndex, PriceBankReferenceEntry
from pricing.budget.price_bank_store import PriceBankStore

logger = logging.getLogger(__name__)

BASE_PRIORITY: list[tuple[str, tuple[str, ...]]] = [
    ("SEMINF", ("seminf", "ppd_seminf", "dp_seminf")),
    ("SINAPI", ("sinapi",)),
    ("SICRO", ("sicro", "cicro")),
    ("ORSE", ("orse",)),
]

SOURCE_TO_FAMILY: dict[str, str] = {
    "sinapi": "SINAPI",
    "seminf": "SEMINF",
    "ppd_seminf": "SEMINF",
    "dp_seminf": "SEMINF",
    "sicro": "SICRO",
    "cicro": "SICRO",
    "orse": "ORSE",
}

_cache_lock = threading.Lock()
_catalog_cache: dict[str, Any] = {"loaded_at": 0.0, "entries": [], "by_code": {}}
_CACHE_TTL = 300.0

_CODE_LIKE = re.compile(
    r"^[\d./]|\.seminf|/orse|/sinapi|/sicro",
    re.IGNORECASE,
)

_STOP_WORDS = frozenset(
    {
        "a",
        "ao",
        "aos",
        "as",
        "com",
        "da",
        "das",
        "de",
        "do",
        "dos",
        "e",
        "em",
        "na",
        "no",
        "nos",
        "o",
        "os",
        "ou",
        "para",
        "por",
        "sem",
        "um",
        "uma",
    }
)

_SENIORITY_TOKENS = (
    "senior",
    "sênior",
    "pleno",
    "junior",
    "júnior",
    "master",
    "especialista",
    "coordenador",
    "auxiliar",
)

# Grupos de ação — mismatch entre import e base penaliza forte (ex.: remoção vs revestimento).
_ACTION_GROUPS: dict[str, frozenset[str]] = {
    "remocao": frozenset(
        {"remocao", "remover", "demolicao", "demolir", "retirada", "retirar", "destaque", "destacar"}
    ),
    "revestimento": frozenset(
        {
            "revestimento",
            "revestir",
            "aplicacao",
            "aplicar",
            "execucao",
            "executar",
            "projecao",
            "projetar",
            "chapisco",
            "reboco",
            "emassamento",
            "monocamada",
        }
    ),
    "fornecimento": frozenset(
        {
            "fornecimento",
            "fornecer",
            "instalacao",
            "instalar",
            "montagem",
            "montar",
            "colocacao",
            "colocar",
            "assentamento",
            "assentar",
        }
    ),
    "transporte": frozenset(
        {"transporte", "transportar", "carga", "descarga", "icamento", "guindaste", "horizontal"}
    ),
    "limpeza": frozenset({"limpeza", "limpar", "lavagem", "lavar", "higienizacao"}),
}

_INCOMPATIBLE_ACTION_PAIRS: frozenset[tuple[str, str]] = frozenset(
    {
        ("remocao", "revestimento"),
        ("remocao", "limpeza"),
        ("remocao", "fornecimento"),
        ("limpeza", "revestimento"),
        ("transporte", "revestimento"),
        ("transporte", "fornecimento"),
    }
)

# Substantivos técnicos — se presentes no import, devem aparecer na base.
_DOMAIN_NOUNS = frozenset(
    {
        "tapume",
        "tapumes",
        "placa",
        "placas",
        "portico",
        "porticos",
        "granito",
        "lona",
        "vinil",
        "plastico",
        "plasticos",
        "acm",
        "bancada",
        "rasgo",
        "alvenaria",
        "luva",
        "esgoto",
        "fachada",
        "telhado",
        "trama",
        "terca",
        "tercas",
        "fibrocimento",
        "canteiro",
        "obras",
        "obra",
        "predial",
        "prumada",
        "tubo",
        "pvc",
        "degraus",
        "escada",
    }
)

MIN_AUTO_MATCH_SCORE = 0.80
MIN_SUGGEST_MATCH_SCORE = 0.52
MIN_IMPORTED_CODE_DESC_SCORE = 0.75

# Tokens relacionados (sinônimos técnicos) para cobertura semântica.
_TOKEN_RELATED: dict[str, frozenset[str]] = {
    "perfuracao": frozenset({"furo", "perfuratriz", "perfurado", "perfuracoes"}),
    "furo": frozenset({"perfuracao", "perfuratriz", "furos"}),
    "perfuratriz": frozenset({"furo", "perfuracao"}),
    "limpeza": frozenset({"furo", "limpeza", "soprar", "aspiracao"}),
    "espera": frozenset({"barra", "barras", "armadura", "armacao", "ligacao", "transferencia"}),
    "barra": frozenset({"barras", "armadura", "espera", "ligacao", "transferencia", "aco"}),
    "barras": frozenset({"barra", "armadura", "espera", "ligacao", "transferencia"}),
    "adesivo": frozenset({"adesivo", "epoxi", "resina", "injecao", "colagem"}),
    "epoxi": frozenset({"adesivo", "resina", "epoxi", "estrutural"}),
    "pilar": frozenset({"pilares", "estaca", "coluna", "colunas"}),
    "viga": frozenset({"vigas", "baldrame"}),
    "concreto": frozenset({"concretagem", "cimento", "estrutura"}),
    "armado": frozenset({"armadura", "armacao", "aco"}),
    "armacao": frozenset({"armadura", "armado", "aco", "ferragem"}),
}

# Consultas alternativas para ampliar recall no catálogo.
_SEARCH_SYNONYMS: dict[str, tuple[str, ...]] = {
    "perfuracao": ("furo mecanizado concreto", "furo concreto perfuratriz"),
    "furo": ("furo mecanizado concreto",),
    "limpeza": ("furo mecanizado concreto",),
    "epoxi": ("adesivo estrutural resina", "injecao epoxi"),
    "adesivo": ("adesivo estrutural epoxi",),
    "espera": ("armadura pilar concreto armado", "barra aco pilar"),
    "pilar": ("pilar concreto armado", "estrutura concreto armado"),
}


def normalize_match_text(text: str) -> str:
    """Remove acentos e normaliza espaços para comparação."""
    raw = unicodedata.normalize("NFKD", text or "")
    ascii_text = raw.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^\w\s]", " ", ascii_text.lower())
    return " ".join(cleaned.split())


def tokenize_match_description(text: str) -> list[str]:
    norm = normalize_match_text(text)
    return [t for t in norm.split() if len(t) >= 3 and t not in _STOP_WORDS]


def _token_matches(token: str, cat_token_set: set[str]) -> bool:
    if token in cat_token_set:
        return True
    related = _TOKEN_RELATED.get(token)
    if related and (related & cat_token_set):
        return True
    return False


def distill_search_queries(description: str) -> list[str]:
    """Gera consultas alternativas para ampliar recall (sinônimos + tokens-chave)."""
    raw = (description or "").strip()
    if not raw:
        return []
    seen: set[str] = set()
    queries: list[str] = []

    def add(q: str) -> None:
        q = q.strip()
        if not q or q in seen:
            return
        seen.add(q)
        queries.append(q)

    add(raw)
    tokens = tokenize_match_description(raw)
    if len(tokens) >= 2:
        add(" ".join(tokens[:4]))
    if len(tokens) >= 3:
        add(" ".join(tokens[:6]))
    for token in tokens[:6]:
        for key, syns in _SEARCH_SYNONYMS.items():
            if token == key or key in token:
                for syn in syns:
                    add(syn)
    return queries[:10]


def seniority_mismatch_penalty(import_desc: str, catalog_desc: str) -> float:
    """Penaliza apenas quando o import especifica senioridade diferente da base."""
    imp = normalize_match_text(import_desc)
    cat = normalize_match_text(catalog_desc)
    imp_levels = [s for s in _SENIORITY_TOKENS if s in imp]
    cat_levels = [s for s in _SENIORITY_TOKENS if s in cat]
    if not imp_levels or not cat_levels:
        return 0.0
    if imp_levels[0] == cat_levels[0]:
        return 0.0
    return -0.1


def _detect_action_group(text: str) -> str | None:
    tokens = set(tokenize_match_description(text))
    for name, words in _ACTION_GROUPS.items():
        if tokens & words:
            return name
    return None


def action_mismatch_penalty(import_desc: str, catalog_desc: str) -> float:
    imp_g = _detect_action_group(import_desc)
    cat_g = _detect_action_group(catalog_desc)
    if imp_g and cat_g and imp_g != cat_g:
        return -0.35
    return 0.0


def domain_noun_mismatch_penalty(import_desc: str, catalog_desc: str) -> float:
    imp_tokens = set(tokenize_match_description(import_desc))
    imp_nouns = imp_tokens & _DOMAIN_NOUNS
    if not imp_nouns:
        return 0.0
    cat_nouns = set(tokenize_match_description(catalog_desc)) & _DOMAIN_NOUNS
    overlap = imp_nouns & cat_nouns
    if not overlap:
        return -0.30
    if len(overlap) < max(1, len(imp_nouns) // 2):
        return -0.15
    return 0.0


def weighted_token_coverage(imp_tokens: list[str], cat_token_set: set[str]) -> float:
    if not imp_tokens:
        return 0.0
    total = 0.0
    matched = 0.0
    for i, token in enumerate(imp_tokens):
        weight = 2.0 if i < 2 else (1.5 if i < 4 else 1.0)
        total += weight
        if _token_matches(token, cat_token_set):
            matched += weight
    return matched / total if total else 0.0


def is_hard_mismatch(import_desc: str, catalog_desc: str) -> bool:
    """
    Rejeição forte — pares claramente incompatíveis (ex.: tapume vs luva, remoção vs revestimento).
    Não bloqueia matches parciais legítimos (ex.: limpeza de furo ≈ furo mecanizado).
    """
    imp_tokens = tokenize_match_description(import_desc)
    if not imp_tokens:
        return False
    cat_token_set = set(tokenize_match_description(catalog_desc))

    imp_g = _detect_action_group(import_desc)
    cat_g = _detect_action_group(catalog_desc)
    if imp_g and cat_g:
        if imp_g != cat_g and (
            (imp_g, cat_g) in _INCOMPATIBLE_ACTION_PAIRS
            or (cat_g, imp_g) in _INCOMPATIBLE_ACTION_PAIRS
        ):
            return True
        if imp_g != cat_g:
            coverage = weighted_token_coverage(imp_tokens, cat_token_set)
            if coverage < 0.45:
                return True

    imp_domain = set(imp_tokens) & _DOMAIN_NOUNS
    if imp_domain:
        cat_domain = cat_token_set & _DOMAIN_NOUNS
        if not (imp_domain & cat_domain):
            return True

    return False


def espera_context_adjustment(import_desc: str, catalog_desc: str) -> float:
    """Ajuste para barras de espera ≈ barras de transferência/ligação na base SINAPI."""
    imp = set(tokenize_match_description(import_desc))
    cat = set(tokenize_match_description(catalog_desc))
    if "espera" not in imp:
        return 0.0
    if cat & {"transferencia", "ligacao"}:
        return 0.18
    if cat & {"armadura", "armacao", "paredes"} and not (cat & {"transferencia", "ligacao"}):
        return -0.16
    return 0.0


def description_match_score(
    import_desc: str,
    catalog_desc: str,
    *,
    unit: str = "",
    catalog_unit: str = "",
) -> float:
    """Score 0–1: cobertura ponderada de tokens + ação/unidade + similaridade global."""
    imp_norm = normalize_match_text(import_desc)
    cat_norm = normalize_match_text(catalog_desc)
    if not imp_norm or not cat_norm:
        return 0.0
    if imp_norm == cat_norm:
        score = 1.0
    elif imp_norm in cat_norm:
        # Evita inflar score quando só um fragmento curto aparece em descrição longa.
        if len(imp_norm) >= 14 or len(imp_norm) / max(len(cat_norm), 1) >= 0.35:
            score = 0.92
        else:
            score = 0.52
    else:
        imp_tokens = tokenize_match_description(import_desc)
        cat_token_set = set(tokenize_match_description(catalog_desc))
        coverage = weighted_token_coverage(imp_tokens, cat_token_set)
        ratio = SequenceMatcher(None, imp_norm, cat_norm).ratio()

        if coverage >= 0.88:
            score = 0.88 + min(0.10, (coverage - 0.88) * 0.8)
        elif coverage >= 0.70:
            score = 0.80 + (coverage - 0.70) * 0.55
        elif coverage >= 0.50:
            score = 0.62 + (coverage - 0.50) * 0.90
        elif coverage >= 0.35:
            score = 0.48 + (coverage - 0.35) * 0.93
        else:
            score = max(ratio * 0.42, coverage * 0.58)

        if imp_tokens and coverage < 0.40:
            score = min(score, 0.65)
        if len(imp_tokens) >= 2 and not any(_token_matches(t, cat_token_set) for t in imp_tokens[:2]):
            score = min(score, 0.58)

    score += seniority_mismatch_penalty(import_desc, catalog_desc)
    score += action_mismatch_penalty(import_desc, catalog_desc)
    score += domain_noun_mismatch_penalty(import_desc, catalog_desc)
    score += espera_context_adjustment(import_desc, catalog_desc)
    if unit and catalog_unit:
        if units_compatible(unit, catalog_unit):
            score += 0.03
        else:
            score -= 0.22
    return min(1.0, max(0.0, round(score, 4)))


def _looks_like_code(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if _CODE_LIKE.search(t):
        return True
    digits = t.replace(".", "").replace("/", "").replace("-", "")
    return digits.isdigit() and len(digits) >= 4


@dataclass
class CatalogEntry:
    base: str
    source: str
    reference: str
    code: str
    description: str
    unit: str
    price: float
    default_uf: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "base": self.base,
            "source": self.source,
            "reference": self.reference,
            "code": self.code,
            "description": self.description,
            "unit": self.unit,
            "price": self.price,
            "default_uf": self.default_uf,
        }


def _source_family(source: str) -> str | None:
    sl = source.lower()
    if sl in SOURCE_TO_FAMILY:
        return SOURCE_TO_FAMILY[sl]
    for label, aliases in BASE_PRIORITY:
        if sl in aliases:
            return label
    return None


def family_from_source(source: str) -> str | None:
    return _source_family(source)


def effective_base_order(price_bases: list[dict[str, Any]] | None = None) -> list[str]:
    if not price_bases:
        return [label for label, _ in BASE_PRIORITY]
    order: list[str] = []
    for sel in price_bases:
        if not sel.get("enabled", True):
            continue
        family = family_from_source(str(sel.get("source") or ""))
        if family and family not in order:
            order.append(family)
    return order or [label for label, _ in BASE_PRIORITY]


def _selection_fingerprint(price_bases: list[dict[str, Any]] | None) -> str:
    if not price_bases:
        return "latest"
    parts: list[str] = []
    for sel in sorted(price_bases, key=lambda s: str(s.get("source") or "")):
        if not sel.get("enabled", True):
            continue
        parts.append(
            "|".join(
                [
                    str(sel.get("source") or "sinapi").lower(),
                    str(sel.get("uf") or "SP").upper(),
                    str(sel.get("reference") or "").replace("/", "-"),
                ]
            )
        )
    return "::".join(parts) or "latest"


def _pick_latest_refs(index: PriceBankIndex) -> dict[str, PriceBankReferenceEntry]:
    best: dict[str, PriceBankReferenceEntry] = {}
    for entry in index.references:
        family = _source_family(entry.source)
        if not family:
            continue
        prev = best.get(family)
        if prev is None or entry.reference > prev.reference:
            best[family] = entry
    return best


def _refs_from_selections(
    price_bases: list[dict[str, Any]] | None,
    index: PriceBankIndex,
    *,
    default_uf: str = "AM",
) -> dict[str, tuple[PriceBankReferenceEntry, str]]:
    """Mapeia família de base → (referência importada, UF de preço)."""
    if not price_bases:
        latest = _pick_latest_refs(index)
        return {family: (entry, default_uf.upper()) for family, entry in latest.items()}

    index_by_ref = {e.reference.replace("/", "-"): e for e in index.references}
    out: dict[str, tuple[PriceBankReferenceEntry, str]] = {}
    for sel in price_bases:
        if not sel.get("enabled", True):
            continue
        source = str(sel.get("source") or "").lower()
        family = family_from_source(source)
        if not family:
            continue
        ref_key = str(sel.get("reference") or "").replace("/", "-")
        if not ref_key:
            continue
        entry = index_by_ref.get(ref_key)
        if not entry:
            for candidate in index.references:
                if candidate.reference.replace("/", "-") == ref_key and _source_family(candidate.source) == family:
                    entry = candidate
                    break
        if entry:
            uf = str(sel.get("uf") or entry.default_uf or default_uf).upper()
            out[family] = (entry, uf)
    return out


def _price_for_row(row: dict[str, Any], uf: str) -> float:
    reg = (row.get("regional") or {}).get(uf.upper())
    if reg:
        return float(reg.get("comd") or reg.get("com") or 0)
    return float(row.get("price") or 0)


def load_catalog(
    *,
    uf: str = "AM",
    price_bases: list[dict[str, Any]] | None = None,
    force: bool = False,
) -> tuple[list[CatalogEntry], dict[str, list[CatalogEntry]]]:
    fingerprint = _selection_fingerprint(price_bases)
    cache_key = f"{uf.upper()}::{fingerprint}"
    now = time.time()
    with _cache_lock:
        if (
            not force
            and _catalog_cache["entries"]
            and now - float(_catalog_cache["loaded_at"]) < _CACHE_TTL
            and _catalog_cache.get("cache_key") == cache_key
        ):
            return _catalog_cache["entries"], _catalog_cache["by_code"]

    index = PriceBankIndex.load()
    ref_map = _refs_from_selections(price_bases, index, default_uf=uf)
    base_order = effective_base_order(price_bases)
    entries: list[CatalogEntry] = []
    by_code: dict[str, list[CatalogEntry]] = {}

    for family in base_order:
        picked = ref_map.get(family)
        if not picked:
            continue
        entry, sel_uf = picked
        store = PriceBankStore.for_reference(entry.reference)
        for row in store.load_closed():
            code = str(row.get("code") or "").strip()
            desc = str(row.get("description") or "").strip()
            if not code or not desc:
                continue
            unit = str(row.get("unit") or "un").strip()
            price = _price_for_row(row, sel_uf or uf)
            cat = CatalogEntry(
                base=family,
                source=entry.source,
                reference=entry.reference,
                code=code,
                description=desc,
                unit=unit,
                price=price,
                default_uf=sel_uf or entry.default_uf or uf.upper(),
            )
            entries.append(cat)
            key = _normalize_code_key(code, family)
            by_code.setdefault(key, []).append(cat)
            bare = code.split("/")[0].strip()
            if bare and bare != key:
                by_code.setdefault(bare, []).append(cat)

    with _cache_lock:
        _catalog_cache["loaded_at"] = now
        _catalog_cache["entries"] = entries
        _catalog_cache["by_code"] = by_code
        _catalog_cache["cache_key"] = cache_key

    logger.info(
        "Price matching catalog: %s composições (%s bases, fingerprint=%s)",
        len(entries),
        len(ref_map),
        fingerprint,
    )
    return entries, by_code


def _normalize_code_key(code: str, base: str) -> str:
    c = code.strip().upper()
    if "/" in c:
        return c
    if base == "ORSE" and c.isdigit():
        return f"{c.zfill(5)}/ORSE"
    return c


def normalize_unit(unit: str) -> str:
    u = (unit or "").strip().lower()
    u = u.replace("²", "2").replace("³", "3").replace(".", "")
    aliases = {
        "m2": "m2",
        "m²": "m2",
        "m3": "m3",
        "m³": "m3",
        "und": "un",
        "unid": "un",
        "unidade": "un",
        "kg": "kg",
        "k g": "kg",
        "h": "h",
        "hora": "h",
        "mes": "mes",
        "mês": "mes",
        "vb": "vb",
        "cj": "cj",
        "gl": "gl",
        "t": "t",
    }
    return aliases.get(u, u)


def units_compatible(expected: str, actual: str) -> bool:
    e = normalize_unit(expected)
    a = normalize_unit(actual)
    if not e or not a:
        return True
    if e == a:
        return True
    if e in ("m2",) and a in ("m2",):
        return True
    if e in ("m3",) and a in ("m3",):
        return True
    return False


def _search_by_code(
    code_q: str,
    *,
    base: str | None,
    unit: str | None,
    allowed: set[str] | None,
    by_code: dict[str, list[CatalogEntry]],
    limit: int,
) -> list[CatalogEntry]:
    keys = [code_q.upper(), code_q, code_q.split("/")[0], code_q.split(".")[0]]
    hits: list[CatalogEntry] = []
    seen: set[str] = set()
    for key in keys:
        for entry in by_code.get(key, []):
            sig = f"{entry.base}:{entry.code}:{entry.reference}"
            if sig in seen:
                continue
            seen.add(sig)
            hits.append(entry)
    if not hits:
        needle = code_q.lower()
        for entries in by_code.values():
            for entry in entries:
                if needle in entry.code.lower():
                    sig = f"{entry.base}:{entry.code}:{entry.reference}"
                    if sig not in seen:
                        seen.add(sig)
                        hits.append(entry)
    if base:
        hits = [h for h in hits if h.base.upper() == base.upper()]
    if allowed:
        hits = [h for h in hits if h.base in allowed]
    if unit:
        hits = [h for h in hits if units_compatible(unit, h.unit)]
    return hits[:limit]


def search_catalog(
    query: str,
    *,
    unit: str | None = None,
    base: str | None = None,
    code: str | None = None,
    limit: int = 20,
    uf: str = "AM",
    price_bases: list[dict[str, Any]] | None = None,
    min_score: float = 0.38,
) -> list[CatalogEntry]:
    _entries, by_code = load_catalog(uf=uf, price_bases=price_bases)
    allowed = set(effective_base_order(price_bases)) if price_bases else None
    ql_raw = (query or "").strip()
    ql = ql_raw.lower()
    code_q = (code or "").strip()

    if not code_q and ql_raw and _looks_like_code(ql_raw):
        code_q = ql_raw
        ql = ""

    hits: list[CatalogEntry] = []
    if code_q:
        hits = _search_by_code(
            code_q,
            base=base,
            unit=unit,
            allowed=allowed,
            by_code=by_code,
            limit=limit,
        )

    if ql:
        entries, _ = load_catalog(uf=uf, price_bases=price_bases)
        scored: list[tuple[float, CatalogEntry]] = []
        for entry in entries:
            if base and entry.base.upper() != base.upper():
                continue
            if allowed and entry.base not in allowed:
                continue
            if unit and not units_compatible(unit, entry.unit):
                continue
            score = description_match_score(
                query,
                entry.description,
                unit=unit or "",
                catalog_unit=entry.unit,
            )
            if score >= min_score:
                scored.append((score, entry))

        scored.sort(key=lambda x: (-x[0], x[1].base, x[1].code))
        text_hits = [e for _, e in scored[:limit]]
        if hits:
            if ql:
                filtered = [h for h in hits if ql in h.description.lower() or ql in h.code.lower()]
                hits = filtered or hits
        else:
            hits = text_hits
    elif not hits:
        return []

    return hits[:limit]
