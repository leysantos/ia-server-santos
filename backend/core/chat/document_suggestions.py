"""Sugestões dinâmicas de documentos a partir do texto da resposta do chat."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

ExportKind = Literal[
    "memoria",
    "trd",
    "memorial",
    "parecer",
    "especificacao",
    "checklist",
    "nota_orcamento",
    "resposta",
]
ActionKind = Literal["croqui"]
SuggestKind = ExportKind | ActionKind

_ENGINEERING_DISC = frozenset(
    {
        "ESTRUTURAL",
        "HIDRAULICA",
        "HIDRÁULICA",
        "ELETRICA",
        "ELÉTRICA",
        "GEOTECNIA",
        "ORCAMENTO",
        "ORÇAMENTO",
        "ARQUITETURA",
        "PCI",
        "INSTALACOES",
        "INSTALAÇÕES",
        "SANEAMENTO",
        "DRENAGEM",
        "TRANSPORTES",
        "INFRAESTRUTURA",
        "MEIO_AMBIENTE",
        "TOPOGRAFIA",
    }
)


@dataclass(frozen=True)
class DocSuggestion:
    kind: SuggestKind
    label: str
    formats: tuple[str, ...]
    priority: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["formats"] = list(self.formats)
        return d


def _norm(text: str) -> str:
    return (text or "").casefold()


def _score(patterns: tuple[str, ...], blob: str) -> int:
    return sum(1 for p in patterns if re.search(p, blob, re.I))


_CALC = (
    r"armadur",
    r"estribo",
    r"momento",
    r"fck",
    r"nbr\s*6118",
    r"\bkN\b",
    r"mem[oó]ria\s+de\s+c[aá]lculo",
    r"dimension",
    r"\bviga\b",
    r"\blaje\b",
    r"\bpilar\b",
    r"\bM_?Sd\b",
    r"\bAs\b",
    r"φ\s*\d",
    r"\bmi\b",
    r"esfor[cç]o",
)
_CROQUI = (
    r"\bviga\b",
    r"armadur",
    r"estribo",
    r"seção|seccao",
    r"elevação|elevacao",
    r"croqui",
    r"detalhamento",
    r"\d+\s*[x×]\s*\d+\s*cm",
)
_TRD = (
    r"termo\s+de\s+refer",
    r"\bTRD\b",
    r"\bTDR\b",
    r"escopo\s+t[eé]cnico",
    r"entreg[aá]veis",
    r"objeto\s+do\s+servi",
)
_MEMORIAL = (
    r"memorial\s+descritivo",
    r"descri[cç][aã]o\s+dos\s+materiais",
    r"especificações\s+de\s+acabamento",
    r"sistema\s+construtivo",
    r"acabamento",
    r"revestimento",
)
_PARECER = (
    r"parecer\s+t[eé]cnico",
    r"n[aã]o\s+conformidade",
    r"\bNC\b",
    r"conformidade",
    r"recomenda[cç][aã]o\s+normativa",
    r"an[aá]lise\s+cr[ií]tica",
    r"diagn[oó]stico",
    r"laudo",
)
_ESPEC = (
    r"especifica[cç][aã]o\s+t[eé]cnica",
    r"crit[eé]rios\s+de\s+aceita",
    r"m[eé]todo\s+executivo",
    r"materiais\s+e\s+servi[cç]os",
    r"ET\b",
)
_CHECKLIST = (
    r"checklist",
    r"\bPCI\b",
    r"\bPPCI\b",
    r"\bIT[-\s]?\d",
    r"CBMAM",
    r"corpo\s+de\s+bombeiros",
    r"item\s+de\s+verifica",
)
_ORC = (
    r"\bSINAPI\b",
    r"\bSICRO\b",
    r"\bBDI\b",
    r"composi[cç][aã]o",
    r"or[cç]amento",
    r"pre[cç]o\s+unit[aá]rio",
    r"curva\s+ABC",
    r"insumo",
)


def should_offer_document_actions(
    text: str,
    *,
    discipline: str | None = None,
    route_mode: str | None = None,
) -> bool:
    body = (text or "").strip()
    if len(body) < 280:
        return False
    disc = (discipline or "").upper().strip()
    if disc and disc in _ENGINEERING_DISC:
        return True
    mode = (route_mode or "").lower()
    if mode in ("engenharia", "mixed"):
        return True
    blob = _norm(body)
    return any(
        _score(pats, blob) >= 1
        for pats in (_CALC, _TRD, _MEMORIAL, _PARECER, _ESPEC, _CHECKLIST, _ORC)
    )


def suggest_chat_documents(
    text: str,
    *,
    discipline: str | None = None,
    source_question: str | None = None,
    route_mode: str | None = None,
    max_items: int = 5,
) -> list[DocSuggestion]:
    """
    Retorna sugestões ordenadas por relevância (priority desc).
    Sempre inclui ao menos um documento textual quando a resposta for elegível.
    """
    if not should_offer_document_actions(text, discipline=discipline, route_mode=route_mode):
        return []

    blob = _norm(f"{source_question or ''}\n{text or ''}")
    disc = (discipline or "").upper()

    scores: dict[SuggestKind, tuple[int, str]] = {}

    calc_n = _score(_CALC, blob)
    if calc_n:
        scores["memoria"] = (40 + calc_n * 8, "Resposta com dimensionamento / esforços")
    croqui_n = _score(_CROQUI, blob)
    if croqui_n >= 2 or (disc == "ESTRUTURAL" and calc_n >= 2):
        scores["croqui"] = (38 + croqui_n * 5, "Há geometria/armadura para croqui")
    trd_n = _score(_TRD, blob)
    if trd_n or calc_n >= 2:
        scores["trd"] = (
            28 + trd_n * 10 + (4 if calc_n else 0),
            "Útil para formalizar escopo/entregáveis",
        )
    mem_n = _score(_MEMORIAL, blob)
    if mem_n or disc == "ARQUITETURA":
        scores["memorial"] = (
            26 + mem_n * 10 + (8 if disc == "ARQUITETURA" else 0),
            "Tom descritivo / memorial",
        )
    par_n = _score(_PARECER, blob)
    if par_n:
        scores["parecer"] = (32 + par_n * 9, "Análise / conformidade / diagnóstico")
    esp_n = _score(_ESPEC, blob)
    if esp_n:
        scores["especificacao"] = (30 + esp_n * 9, "Critérios técnicos de execução")
    chk_n = _score(_CHECKLIST, blob)
    if chk_n or disc == "PCI":
        scores["checklist"] = (
            34 + chk_n * 9 + (10 if disc == "PCI" else 0),
            "Verificação / PCI / checklist",
        )
    orc_n = _score(_ORC, blob)
    if orc_n or disc in ("ORCAMENTO", "ORÇAMENTO"):
        scores["nota_orcamento"] = (
            30 + orc_n * 8 + (10 if "ORC" in disc else 0),
            "Conteúdo de preços / bases / BDI",
        )

    # Fallback: resposta técnica genérica se nada específico pontuou forte
    if not scores or max(s for s, _ in scores.values()) < 30:
        scores.setdefault(
            "resposta",
            (22, "Documento técnico a partir da resposta"),
        )
    elif "resposta" not in scores and len(scores) < 2:
        scores["resposta"] = (18, "Versão bruta da resposta")

    # Evita croqui em respostas claramente de orçamento/PCI sem estrutura
    if "croqui" in scores and orc_n >= 3 and calc_n == 0 and croqui_n < 2:
        del scores["croqui"]

    ordered = sorted(scores.items(), key=lambda kv: kv[1][0], reverse=True)

    catalog: dict[SuggestKind, tuple[str, tuple[str, ...]]] = {
        "memoria": ("Memória de cálculo", ("pdf", "docx")),
        "trd": ("Termo de referência (TRD)", ("pdf", "docx")),
        "memorial": ("Memorial descritivo", ("pdf", "docx")),
        "parecer": ("Parecer técnico", ("pdf", "docx")),
        "especificacao": ("Especificação técnica", ("pdf", "docx")),
        "checklist": ("Checklist / verificação", ("pdf", "docx")),
        "nota_orcamento": ("Nota de orçamento", ("pdf", "docx")),
        "resposta": ("Resposta técnica", ("pdf", "docx")),
        "croqui": ("Croqui estrutural", ("image",)),
    }

    out: list[DocSuggestion] = []
    for kind, (prio, reason) in ordered:
        label, formats = catalog[kind]
        out.append(
            DocSuggestion(
                kind=kind,
                label=label,
                formats=formats,
                priority=prio,
                reason=reason,
            )
        )
        if len(out) >= max_items:
            break
    return out
