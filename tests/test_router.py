"""Testes do router — classificação por regras (sem LLM)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.router import route, route_by_rules, normalize_discipline


def test_estrutural_viga_concreto():
    text = "dimensionar viga de concreto armado"
    assert route_by_rules(text) == "ESTRUTURAL"
    result = route(text)
    assert result["discipline"] == "ESTRUTURAL"
    assert result["agent"] == "estruturas_agent"


def test_hidrossanitario():
    text = "projeto de tubulação de esgoto sanitário"
    assert route_by_rules(text) == "HIDROSSANITÁRIO"
    assert route(text)["discipline"] == "HIDROSSANITÁRIO"


def test_eletrica():
    text = "calcular carga elétrica do circuito de iluminação"
    assert route_by_rules(text) == "ELÉTRICA"


def test_geotecnia():
    text = "sondagem SPT para fundação"
    assert route_by_rules(text) == "GEOTECNIA"


def test_drenagem():
    text = "dimensionar drenagem de águas pluviais"
    assert route_by_rules(text) == "DRENAGEM"


def test_incendio():
    text = "projeto de sistema sprinkler e combate a incêndio"
    assert route_by_rules(text) == "INCÊNDIO"


def test_normalize_discipline():
    assert normalize_discipline("estrutural") == "ESTRUTURAL"
    assert normalize_discipline("hidrossanitario") == "HIDROSSANITÁRIO"
    assert normalize_discipline("resposta: ESTRUTURAL\n") == "ESTRUTURAL"


def test_rules_priority_over_generic():
    # Estrutural deve vencer termos genéricos
    text = "dimensionar viga de concreto armado"
    result = route(text)
    assert result["discipline"] != "GERAL"


if __name__ == "__main__":
    test_estrutural_viga_concreto()
    test_hidrossanitario()
    test_eletrica()
    test_geotecnia()
    test_drenagem()
    test_incendio()
    test_normalize_discipline()
    test_rules_priority_over_generic()
    print("OK: testes router passaram")
