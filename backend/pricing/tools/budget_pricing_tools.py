"""Ferramentas determinísticas de consulta ao banco de preços (price_bank)."""

from __future__ import annotations

import re
from typing import Any

from pricing.budget.price_bank_index import PriceBankIndex

_SINAPI_CODE_RE = re.compile(r"\b(\d{4,6})\b")
_REF_RE = re.compile(r"\b(?:BR[-/])?(\d{4})[-/](\d{1,2})\b", re.I)
_REF_SLASH_RE = re.compile(r"\b(\d{1,2})\s*/\s*(20\d{2})\b")

_UF_BY_NAME: dict[str, str] = {
    "acre": "AC",
    "alagoas": "AL",
    "amapá": "AP",
    "amapa": "AP",
    "amazonas": "AM",
    "bahia": "BA",
    "ceará": "CE",
    "ceara": "CE",
    "distrito federal": "DF",
    "espírito santo": "ES",
    "espirito santo": "ES",
    "goiás": "GO",
    "goias": "GO",
    "maranhão": "MA",
    "maranhao": "MA",
    "mato grosso": "MT",
    "mato grosso do sul": "MS",
    "minas gerais": "MG",
    "pará": "PA",
    "para": "PA",
    "paraíba": "PB",
    "paraiba": "PB",
    "paraná": "PR",
    "parana": "PR",
    "pernambuco": "PE",
    "piauí": "PI",
    "piaui": "PI",
    "rio de janeiro": "RJ",
    "rio grande do norte": "RN",
    "rio grande do sul": "RS",
    "rondônia": "RO",
    "rondonia": "RO",
    "roraima": "RR",
    "santa catarina": "SC",
    "são paulo": "SP",
    "sao paulo": "SP",
    "sergipe": "SE",
    "tocantins": "TO",
}

_BRAZIL_UFS = frozenset(
    "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO".split()
)

_PRICING_QUERY_KEYWORDS = (
    "sinapi",
    "tcpo",
    "composição",
    "composicao",
    "composic",
    "cpu",
    "insumo",
    "preço",
    "preco",
    "custo unitário",
    "custo unitario",
    "orçamento",
    "orcamento",
    "desoneração",
    "desoneracao",
    "comd",
    "semd",
    "ccd",
    "csd",
    "analítica",
    "analitica",
    "aberta",
    "fechada",
)


class BudgetPricingTools:
    """Consultas ao price_bank — usadas pelo agente de orçamento e pelo BudgetOrchestrator."""

    @staticmethod
    def list_references() -> list[dict[str, Any]]:
        return PriceBankIndex.load().list_references()

    @staticmethod
    def resolve_defaults(
        *,
        uf: str | None = None,
        reference: str | None = None,
    ) -> dict[str, str]:
        idx = PriceBankIndex.load()
        ref = PriceBankIndex.resolve_reference(reference)
        entry = next((r for r in idx.references if r.reference == ref), None)
        use_uf = (uf or (entry.default_uf if entry else "") or "SP").upper()
        return {"uf": use_uf, "reference": ref}

    @staticmethod
    def search_compositions(
        query: str,
        *,
        unit: str | None = None,
        uf: str | None = None,
        reference: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        from pricing.core.base_service_resolver import BaseServiceResolver

        defaults = BudgetPricingTools.resolve_defaults(uf=uf, reference=reference)
        BudgetPricingTools._ensure_provider_loaded(defaults["reference"], defaults["uf"])

        resolver = BaseServiceResolver()
        detail = resolver.resolve_with_details(
            query.strip(),
            unit=unit,
            use_llm=False,
        )
        out: list[dict[str, Any]] = []
        if detail.item:
            out.append(
                {
                    "code": detail.item.code,
                    "description": detail.item.description,
                    "unit": detail.item.unit,
                    "price_comd": detail.item.price,
                    "method": detail.method,
                    "score": detail.score,
                }
            )
        for cand in (detail.candidates or [])[: max(0, limit - len(out))]:
            if any(c["code"] == cand.get("code") for c in out):
                continue
            out.append(cand)
        return out[:limit]

    @staticmethod
    def get_open_composition(
        code: str,
        *,
        uf: str | None = None,
        reference: str | None = None,
    ) -> dict[str, Any]:
        from pricing.budget.price_bank_store import PriceBankStore

        defaults = BudgetPricingTools.resolve_defaults(uf=uf, reference=reference)
        comp = PriceBankStore.for_reference(defaults["reference"]).get_open_composition(
            str(code).strip(),
            uf=defaults["uf"],
        )
        if not comp:
            raise ValueError(
                f"Composição aberta '{code}' não encontrada em {defaults['reference']}"
            )
        comp["reference"] = defaults["reference"]
        comp["price_uf"] = comp.get("price_uf") or defaults["uf"]
        from pricing.budget.price_bank_period_variation import compute_period_variation_warnings

        comp["period_variation"] = compute_period_variation_warnings(
            comp, uf=defaults["uf"], reference=defaults["reference"]
        )
        return comp

    @staticmethod
    def format_open_composition_markdown(comp: dict[str, Any], *, max_items: int = 50) -> str:
        ref = comp.get("reference", "")
        uf = comp.get("price_uf", "SP")
        ref_label = ref.replace("BR-", "").replace("-", "/") if ref.startswith("BR-") else ref
        lines = [
            "=== DADOS OFICIAIS DO BANCO DE PREÇOS (price_bank) — NÃO INVENTE VALORES ===",
            f"Código: {comp.get('code', '')}",
            f"Descrição: {comp.get('description', '')}",
            f"Unidade: {comp.get('unit', '')}",
            f"UF: {uf} | Período: {ref_label}",
            "",
            "**Totais sintéticos (aba fechada)**",
            f"- Com desoneração (ComD/CCD): R$ {float(comp.get('total_price') or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            f"- Sem desoneração (SemD/CSD): R$ {float(comp.get('total_price_sem') or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            "",
            "**Totais analíticos (soma dos parciais da CPU)**",
            f"- ComD: R$ {float(comp.get('analytical_total_com') or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            f"- SemD: R$ {float(comp.get('analytical_total_sem') or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            "",
        ]
        variation = comp.get("period_variation") or {}
        var_warnings = variation.get("warnings") or []
        if var_warnings:
            prev_lbl = variation.get("previous_label") or "mês anterior"
            lines.append(f"**Alertas de variação vs {prev_lbl} (>±{variation.get('threshold_pct', 30)}%)**")
            for w in var_warnings[:8]:
                lines.append(f"- {w.get('message', '')}")
            lines.append("")
        lines.extend([
            "| Tipo | Código | Descrição | Und | Coef. | Preço un. ComD | Parcial ComD | Preço un. SemD | Parcial SemD |",
            "|------|--------|-----------|-----|-------|----------------|--------------|----------------|--------------|",
        ])
        items = comp.get("items") or []
        for item in items[:max_items]:
            desc = str(item.get("description") or "")[:80].replace("|", "/")
            lines.append(
                "| {tipo} | {code} | {desc} | {unit} | {coef} | {ucom} | {pcom} | {usem} | {psem} |".format(
                    tipo=item.get("item_type", ""),
                    code=item.get("code", ""),
                    desc=desc,
                    unit=item.get("unit", ""),
                    coef=item.get("coefficient", ""),
                    ucom=_brl(item.get("unit_price")),
                    pcom=_brl(item.get("partial_cost")),
                    usem=_brl(item.get("unit_price_sem")),
                    psem=_brl(item.get("partial_cost_sem")),
                )
            )
        if len(items) > max_items:
            lines.append(f"\n_(+ {len(items) - max_items} itens omitidos)_")
        lines.append("=== FIM DOS DADOS OFICIAIS ===")
        return "\n".join(lines)

    @staticmethod
    def _ensure_provider_loaded(reference: str, uf: str) -> None:
        """Carrega composições fechadas da referência/UF no provider (busca semântica)."""
        try:
            from pricing.budget.price_base_session import apply_price_bases_selection

            apply_price_bases_selection(
                [
                    {
                        "enabled": True,
                        "source": "sinapi",
                        "uf": uf.upper(),
                        "reference": reference,
                    }
                ]
            )
        except Exception:
            pass


def _brl(value: Any) -> str:
    try:
        n = float(value or 0)
    except (TypeError, ValueError):
        return "—"
    if n == 0:
        return "—"
    return f"R$ {n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def extract_sinapi_codes(text: str) -> list[str]:
    seen: set[str] = set()
    codes: list[str] = []
    for match in _SINAPI_CODE_RE.finditer(text):
        code = match.group(1)
        if code in seen:
            continue
        seen.add(code)
        codes.append(code)
    return codes


def extract_uf_from_text(text: str) -> str | None:
    lower = text.lower()
    m = re.search(r"\buf\s+([a-z]{2})\b", lower)
    if m:
        cand = m.group(1).upper()
        if cand in _BRAZIL_UFS:
            return cand
    for token in re.findall(r"\b[a-záàâãéêíóôõúç]{2,}\b", lower):
        if token in _UF_BY_NAME:
            return _UF_BY_NAME[token]
    return None


def extract_reference_from_text(text: str) -> str | None:
    m = _REF_RE.search(text)
    if m:
        return f"BR-{m.group(1)}-{int(m.group(2)):02d}"
    m2 = _REF_SLASH_RE.search(text)
    if m2:
        return f"BR-{m2.group(2)}-{int(m2.group(1)):02d}"
    return None


def is_pricing_query(text: str) -> bool:
    lower = text.lower()
    if any(k in lower for k in _PRICING_QUERY_KEYWORDS):
        return True
    return bool(extract_sinapi_codes(text))


def wants_open_composition(text: str) -> bool:
    lower = text.lower()
    if any(
        k in lower
        for k in (
            "composição aberta",
            "composicao aberta",
            "cpu",
            "analítica",
            "analitica",
            "estrutura da composição",
            "estrutura da composicao",
            "esboç",
            "esboc",
            "detalh",
            "insumos da composição",
            "insumos da composicao",
        )
    ):
        return True
    codes = extract_sinapi_codes(text)
    return bool(codes) and ("compos" in lower or "sinapi" in lower or "código" in lower or "codigo" in lower)


def fetch_pricing_context_for_agent(text: str) -> tuple[str, list[dict[str, Any]]]:
    """
    Executa ferramentas de preço conforme o texto do usuário.
    Retorna (bloco markdown para o prompt, metadados das chamadas).
    """
    if not is_pricing_query(text):
        return "", []

    uf = extract_uf_from_text(text)
    reference = extract_reference_from_text(text)
    tools = BudgetPricingTools()
    calls: list[dict[str, Any]] = []
    blocks: list[str] = []

    refs = tools.list_references()
    if refs and not reference:
        reference = refs[0].get("reference")

    if wants_open_composition(text):
        for code in extract_sinapi_codes(text)[:2]:
            try:
                comp = tools.get_open_composition(code, uf=uf, reference=reference)
                blocks.append(tools.format_open_composition_markdown(comp))
                calls.append(
                    {
                        "tool": "get_open_composition",
                        "code": code,
                        "uf": comp.get("price_uf"),
                        "reference": comp.get("reference"),
                    }
                )
            except ValueError as exc:
                blocks.append(f"⚠️ Composição {code}: {exc}")
                calls.append({"tool": "get_open_composition", "code": code, "error": str(exc)})
    elif extract_sinapi_codes(text):
        for code in extract_sinapi_codes(text)[:1]:
            try:
                comp = tools.get_open_composition(code, uf=uf, reference=reference)
                blocks.append(tools.format_open_composition_markdown(comp))
                calls.append(
                    {
                        "tool": "get_open_composition",
                        "code": code,
                        "uf": comp.get("price_uf"),
                        "reference": comp.get("reference"),
                    }
                )
            except ValueError:
                pass

    if not blocks and is_pricing_query(text) and len(text.split()) >= 3:
        query = text.strip()
        try:
            hits = tools.search_compositions(query, uf=uf, reference=reference, limit=8)
            if hits:
                lines = ["=== BUSCA NA BASE DE PREÇOS ==="]
                for h in hits:
                    lines.append(
                        f"- {h.get('code')} | {h.get('description', '')[:100]} | "
                        f"{h.get('unit', '')} | ComD R$ {float(h.get('price') or h.get('price_comd') or 0):.2f}"
                    )
                lines.append("=== FIM DA BUSCA ===")
                blocks.append("\n".join(lines))
                calls.append({"tool": "search_compositions", "hits": len(hits)})
        except Exception as exc:
            blocks.append(f"⚠️ Busca na base: {exc}")

    if refs and not blocks:
        defaults = tools.resolve_defaults(uf=uf, reference=reference)
        blocks.append(
            "Bases de preço disponíveis: "
            + ", ".join(f"{r.get('label', r.get('reference'))} ({r.get('reference')})" for r in refs[:5])
            + f". Padrão consultado: UF {defaults['uf']}, período {defaults['reference']}."
        )
        calls.append({"tool": "list_references", "count": len(refs)})

    return "\n\n".join(blocks), calls
