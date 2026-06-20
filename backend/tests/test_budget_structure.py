"""Testes unit parsing e sub-etapas."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pricing.budget.budget_structure import (
    add_etapa,
    add_subetapa,
    add_service_to_group,
    apply_quantity_to_group,
    delete_item,
    group_services_to_prompt,
    parse_term_hints,
    parse_term_with_unit,
    renumber_wbs,
    service_to_prompt_term,
    split_composition_prompt,
)
from pricing.budget.ppd_template import create_empty_ppd_metadata
from pricing.models.price_item import PriceItem


def test_parse_unit_at_start():
    q, u = parse_term_with_unit("(mês) engenheiro civil")
    assert q == "engenheiro civil"
    assert u == "MES"


def test_parse_unit_at_end():
    q, u = parse_term_with_unit("transporte brita (m³/km)")
    assert "transporte" in q
    assert u == "M3XKM"


def test_parse_unit_hours():
    q, u = parse_term_with_unit("(h) lixamento mecânico")
    assert u == "H"


def test_subetapa_and_service_codes():
    meta = create_empty_ppd_metadata()
    roots = []
    etapa = add_etapa(roots, "ADMINISTRAÇÃO", meta)
    sub = add_subetapa(roots, etapa.code, "Equipe técnica", meta)
    assert sub.code == "1.1"
    assert sub.row_type == "SUB-ETAPA"
    assert sub.name == "EQUIPE TÉCNICA"
    price = PriceItem(code="93567", description="Engenheiro", unit="MES", price=100, source="sinapi")
    svc = add_service_to_group(sub, price, meta)
    assert svc.code == "1.1.1"
    assert svc.parent_code == "1.1"


def test_group_name_uppercase():
    meta = create_empty_ppd_metadata()
    roots = []
    etapa = add_etapa(roots, "administração da obra", meta)
    assert etapa.name == "ADMINISTRAÇÃO DA OBRA"


def test_compose_prompt_split_with_units():
    parts = split_composition_prompt("(mês) engenheiro, (h) vigia")
    assert len(parts) == 2
    q1, u1 = parse_term_with_unit(parts[0])
    assert u1 == "MES"
    q2, u2 = parse_term_with_unit(parts[1])
    assert u2 == "H"


def test_parse_quantity_bracket():
    q, u, qty = parse_term_hints("[12] engenheiro civil")
    assert q == "engenheiro civil"
    assert u is None
    assert qty == 12.0


def test_parse_quantity_paren_numeric():
    q, u, qty = parse_term_hints("(6) (mês) engenheiro")
    assert qty == 6.0
    assert u == "MES"
    assert "engenheiro" in q


def test_parse_quantity_x_suffix():
    q, u, qty = parse_term_hints("(h) vigia x 720")
    assert u == "H"
    assert qty == 720.0
    assert "vigia" in q


def test_parse_quantity_colon():
    q, _, qty = parse_term_hints("encarregado: 3,5")
    assert qty == 3.5
    assert q == "encarregado"


def test_unit_not_confused_with_quantity():
    q, u, qty = parse_term_hints("(mês) engenheiro civil")
    assert u == "MES"
    assert qty is None
    assert q == "engenheiro civil"


def test_parse_qty_unit_combined_m():
    q, u, qty = parse_term_hints("(6 m) tubo galvanizado")
    assert qty == 6.0
    assert u == "M"
    assert "tubo" in q


def test_parse_qty_unit_separate_paren():
    q, u, qty = parse_term_hints("(6) (m) tubo galvanizado")
    assert qty == 6.0
    assert u == "M"
    assert "tubo" in q


def test_parse_qty_unit_reversed_paren():
    q, u, qty = parse_term_hints("(m) (6) tubo galvanizado")
    assert qty == 6.0
    assert u == "M"
    assert "tubo" in q


def test_parse_qty_unit_at_end_m():
    q, u, qty = parse_term_hints("tubo galvanizado (6 m)")
    assert qty == 6.0
    assert u == "M"
    assert "tubo" in q


def test_parse_qty_unit_combined_paren():
    q, u, qty = parse_term_hints("(6 mes) engenheiro civil")
    assert qty == 6.0
    assert u == "MES"
    assert q == "engenheiro civil"


def test_parse_qty_unit_combined_m2():
    q, u, qty = parse_term_hints("(4 m²) pintura acrílica")
    assert qty == 4.0
    assert u == "M2"
    assert "pintura" in q


def test_parse_qty_unit_combined_hours():
    q, u, qty = parse_term_hints("(720 h) vigia")
    assert qty == 720.0
    assert u == "H"
    assert q == "vigia"


def test_parse_qty_unit_at_end():
    q, u, qty = parse_term_hints("escavação manual (12 m³)")
    assert qty == 12.0
    assert u == "M3"
    assert "escavação" in q


def test_parse_term_with_unit_qty_combo():
    q, u = parse_term_with_unit("(6 mês) encarregado")
    assert u == "MES"
    assert q == "encarregado"


def test_apply_quantity_to_group():
    meta = create_empty_ppd_metadata()
    roots = []
    etapa = add_etapa(roots, "ADMINISTRAÇÃO", meta)
    price = PriceItem(code="93567", description="Engenheiro", unit="MES", price=100, source="sinapi")
    svc1 = add_service_to_group(etapa, price, meta, quantity=1.0)
    svc2 = add_service_to_group(etapa, price, meta, quantity=2.0)
    count = apply_quantity_to_group(etapa, 12.0, meta)
    assert count == 2
    assert svc1.quantity == 12.0
    assert svc2.quantity == 12.0
    assert svc1.effective_total() > 0
    assert etapa.total_price > 0


def test_service_to_prompt_term_with_qty_unit():
    meta = create_empty_ppd_metadata()
    roots = []
    etapa = add_etapa(roots, "ADMIN", meta)
    price = PriceItem(code="1", description="Engenheiro civil", unit="MES", price=100, source="sinapi")
    svc = add_service_to_group(etapa, price, meta, quantity=6.0)
    term = service_to_prompt_term(svc)
    assert term == "(6 mes) Engenheiro civil"


def test_group_services_to_prompt_multiline():
    meta = create_empty_ppd_metadata()
    roots = []
    etapa = add_etapa(roots, "ADMIN", meta)
    p1 = PriceItem(code="1", description="Engenheiro", unit="MES", price=100, source="sinapi")
    p2 = PriceItem(code="2", description="Vigia", unit="H", price=10, source="sinapi")
    add_service_to_group(etapa, p1, meta, quantity=6.0)
    add_service_to_group(etapa, p2, meta, quantity=720.0)
    prompt = group_services_to_prompt(etapa)
    lines = prompt.split("\n")
    assert len(lines) == 2
    assert "(6 mes)" in lines[0]
    assert "(720 h)" in lines[1]


def test_renumber_wbs_closes_etapa_gaps():
    meta = create_empty_ppd_metadata()
    roots = []
    e1 = add_etapa(roots, "A", meta)
    e2 = add_etapa(roots, "B", meta)
    e3 = add_etapa(roots, "C", meta)
    e3.code = "5"
    delete_item(roots, e2.row_id)
    mapping = renumber_wbs(roots)
    assert e1.code == "1"
    assert e3.code == "2"
    assert mapping == {"5": "2"}


def test_renumber_wbs_closes_service_gaps_and_memory():
    meta = create_empty_ppd_metadata()
    roots = []
    etapa = add_etapa(roots, "ADMIN", meta)
    price = PriceItem(code="93567", description="Engenheiro", unit="MES", price=100, source="sinapi")
    svc1 = add_service_to_group(etapa, price, meta, quantity=1.0)
    svc2 = add_service_to_group(etapa, price, meta, quantity=2.0)
    svc3 = add_service_to_group(etapa, price, meta, quantity=3.0)
    svc2.code = "1.5"
    svc2.children[0].code = "1.5.m1"
    delete_item(roots, svc2.row_id)
    mapping = renumber_wbs(roots)
    assert svc1.code == "1.1"
    assert svc3.code == "1.2"
    assert svc1.children[0].code == "1.1.m1"
    assert svc3.children[0].code == "1.2.m1"
    assert "1.5" in mapping or "1.3" in mapping
