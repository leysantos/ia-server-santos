"""Testes do template PPD vazio e importação de bases nomeadas."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pricing.budget.ppd_template import create_empty_ppd_metadata, create_empty_ppd_tree
from pricing.budget.price_base_store import PriceBaseStore


def test_empty_ppd_template_structure():
    meta = create_empty_ppd_metadata(projeto="Teste", obra_type="RF")
    roots = create_empty_ppd_tree(meta)
    assert roots == []


def test_price_base_store_csv(tmp_path):
    csv_path = tmp_path / "base.csv"
    csv_path.write_text(
        "codigo,descricao,unidade,preco\n1001,Tijolo,un,1.50\n1002,Cimento,kg,0.80\n",
        encoding="utf-8",
    )
    store = PriceBaseStore(root=tmp_path / "custom")
    entry, rows = store.import_file("Minha Base", csv_path)
    assert entry.name == "Minha Base"
    assert entry.item_count == 2
    assert len(rows) == 2
    active, active_rows = store.get_active_rows()
    assert active is not None
    assert len(active_rows) == 2


def test_price_base_store_delete(tmp_path):
    csv_path = tmp_path / "base.csv"
    csv_path.write_text(
        "codigo,descricao,unidade,preco\n1001,Tijolo,un,1.50\n",
        encoding="utf-8",
    )
    store = PriceBaseStore(root=tmp_path / "custom")
    entry, _ = store.import_file("Base A", csv_path)
    store.delete(entry.id)
    assert store.list_bases() == []
    assert store.get_active_rows() == (None, [])
