"""Classificação insumo / mão de obra / equipamento para relatórios e analíticas."""

from __future__ import annotations

import re
from typing import Any, Literal

ResourceCategory = Literal["equipamento", "insumo", "mao_obra"]

_LABOR_UNITS = frozenset({"H", "MES", "MÊS", "MÊS.", "MES."})

_LABOR_DESC_MARKERS = (
    "mensalista",
    "horista",
    "mão de obra",
    "mao de obra",
    " pedreiro",
    " servente",
    " encarregado",
    " engenheiro",
    " almoxarife",
    " eletricista",
    " carpinteiro",
    " armador",
    "profissional",
    "operário",
    "operario",
    " mestre de obras",
    " ajudante",
    " guincheiro",
)

# Encargos / complementos de MO — não entram no histograma de mão de obra direta
_INDIRECT_MO_PREFIXES = (
    "epi ",
    "epi-",
    "ferramentas ",
    "ferramentas-",
    "seguro ",
    "seguro-",
    "exames ",
    "exames-",
    "alimentacao ",
    "alimentacao-",
    "transporte ",
    "transporte-",
    "locacao ",
    "locacao-",
    "uniforme",
    "cesta basica",
    "vale transporte",
    "vale alimentacao",
    "plano de saude",
    "medicina ocupacional",
    "gratificacao",
    "bonus ",
)

_INDIRECT_MO_SUBSTRINGS = (
    "locacao de container",
    "locacao container",
    "aluguel de container",
)

# Funções / profissionais — histograma MO direta (planilha Caixa)
_DIRECT_LABOR_ROLE_MARKERS = (
    "pedreiro",
    "servente",
    "encarregado",
    "engenheiro",
    "almoxarife",
    "eletricista",
    "vigia",
    "mecanico",
    "carpinteiro",
    "armador",
    "soldador",
    "montador",
    "operador",
    "guindaste",
    "guincheiro",
    "mestre de obra",
    "mestre obra",
    "tecnico de seguranca",
    "técnico de segurança",
    "oficial de producao",
    "oficial de produção",
    "topografo",
    "topógrafo",
    "sondador",
    "pre-marcador",
    "pre marcador",
    "premarcador",
    "gesseiro",
    "pintor",
    "serralheiro",
    "encanador",
    "profissional",
    "operario",
    "operário",
    "borracheiro",
    "rigger",
    "ajudante",
    "auxiliar de eletricista",
    "auxiliar de mecanico",
    "auxiliar de montagem",
    "auxiliar de sondagem",
    "auxiliar topografico",
    "auxiliar topográfico",
)


def normalize_resource_text(value: str) -> str:
    text = (value or "").lower()
    text = text.replace("á", "a").replace("à", "a").replace("ã", "a")
    text = text.replace("é", "e").replace("ê", "e")
    text = text.replace("í", "i")
    text = text.replace("ó", "o").replace("ô", "o").replace("õ", "o")
    text = text.replace("ú", "u").replace("ç", "c")
    return re.sub(r"\s+", " ", text).strip()


def _is_hour_unit(unit: str) -> bool:
    u = (unit or "").strip().upper()
    return u in ("H", "HH", "CH", "H/H") or "HORA" in u


def is_indirect_mo_charge(description: str) -> bool:
    """Encargos complementares, EPI, transporte etc. — não são mão de obra direta."""
    norm = normalize_resource_text(description)
    if not norm:
        return False

    for prefix in _INDIRECT_MO_PREFIXES:
        if norm.startswith(prefix):
            return True

    for sub in _INDIRECT_MO_SUBSTRINGS:
        if sub in norm:
            return True

    # Ex.: "SEGURO - MENSALISTA (COLETADO CAIXA - ENCARGOS COMPLEMENTARES)"
    if "coletado caixa" in norm and "encargos complementares" in norm:
        if not is_direct_labor_role(description):
            return True

    return False


def is_direct_labor_role(description: str) -> bool:
    """Profissional / função de obra — entra no histograma de MO direta."""
    norm = normalize_resource_text(description)
    if not norm:
        return False
    return any(marker in norm for marker in _DIRECT_LABOR_ROLE_MARKERS)


def is_histogram_direct_labor(item: dict[str, Any]) -> bool:
    """
    Item elegível para histograma de mão de obra direta.

    Mantém profissionais (pedreiro, engenheiro, servente, vigia…).
    Exclui EPI, ferramentas, seguro, transporte, locação etc.
    """
    if resolve_resource_category(item) != "mao_obra":
        return False

    desc = str(item.get("description") or "")
    if is_indirect_mo_charge(desc):
        return False

    unit = str(item.get("unit") or "")
    if _is_hour_unit(unit):
        return True

    return is_direct_labor_role(desc)


def is_labor_descriptor(description: str, unit: str) -> bool:
    unit_key = (unit or "").strip().upper().replace(".", "")
    if unit_key in _LABOR_UNITS:
        return True
    blob = (description or "").lower()
    if "(mensalista)" in blob or "(horista)" in blob:
        return True
    return any(marker in blob for marker in _LABOR_DESC_MARKERS)


def _classificacao_to_category(classificacao: str) -> ResourceCategory | None:
    key = (classificacao or "").strip().lower()
    if not key:
        return None
    if "mao" in key and "obra" in key:
        return "mao_obra"
    if key in ("material", "materiais"):
        return "insumo"
    if "equip" in key:
        return "equipamento"
    if "servi" in key:
        return None
    return None


def resolve_resource_category(item: dict[str, Any]) -> ResourceCategory | None:
    """
    Resolve categoria econômica de um item de CPU.

    Prioridade: classificação SINAPI (ISD) → heurística MO (unidade/descrição) → item_type.
    """
    item_type = str(item.get("item_type") or "").strip().lower().replace(" ", "_")
    desc = str(item.get("description") or "")
    unit = str(item.get("unit") or "")

    if item_type == "composicao":
        return None

    from_class = _classificacao_to_category(str(item.get("classificacao") or ""))
    if from_class == "mao_obra":
        return "mao_obra"
    if from_class == "equipamento":
        return "equipamento"
    if from_class == "insumo":
        if is_labor_descriptor(desc, unit):
            return "mao_obra"
        return "insumo"

    if is_labor_descriptor(desc, unit):
        return "mao_obra"

    if item_type == "equipamento":
        return "equipamento"
    if item_type in ("mao_obra", "maodeobra"):
        return "mao_obra"
    if item_type in ("insumo", "material"):
        return "insumo"

    return None
