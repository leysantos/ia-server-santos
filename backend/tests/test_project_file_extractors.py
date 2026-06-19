"""Testes de extração multi-formato para RAG de projetos."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.project_rag.project_file_extractors import (
    PROJECT_INDEXABLE_SUFFIXES,
    extract_project_file_segments,
    is_indexable_project_file,
)


def test_plain_text_extraction():
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as f:
        f.write("Memorial descritivo\nViga V1 — 30cm")
        path = Path(f.name)
    try:
        segments, fmt = extract_project_file_segments(path)
        assert fmt == "txt"
        assert any("Viga V1" in s.text for s in segments)
    finally:
        path.unlink(missing_ok=True)


def test_csv_extraction():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", encoding="utf-8") as f:
        f.write("item,carga\nViga,V1\n")
        path = Path(f.name)
    try:
        segments, fmt = extract_project_file_segments(path)
        assert fmt == "csv"
        assert any("Viga" in s.text for s in segments)
    finally:
        path.unlink(missing_ok=True)


def test_json_extraction():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8") as f:
        json.dump({"projeto": "Edificio A", "carga": 200}, f)
        path = Path(f.name)
    try:
        segments, fmt = extract_project_file_segments(path)
        assert fmt == "json"
        assert "Edificio A" in segments[0].text
    finally:
        path.unlink(missing_ok=True)


def test_indexable_suffixes():
    assert ".pdf" in PROJECT_INDEXABLE_SUFFIXES
    assert ".ifc" in PROJECT_INDEXABLE_SUFFIXES
    assert is_indexable_project_file("planta.dwg")
    assert not is_indexable_project_file("video.mp4")


if __name__ == "__main__":
    test_plain_text_extraction()
    test_csv_extraction()
    test_json_extraction()
    test_indexable_suffixes()
    print("OK: testes project_file_extractors passaram")
