"""Testes de exportação de documentos e croqui estrutural do chat."""

from __future__ import annotations

from core.chat.document_export import build_chat_document, build_chat_docx, build_chat_pdf
from core.chat.structural_croqui import parse_beam_spec, try_build_structural_croqui


SAMPLE = """
### Solução Recomendada

Para a viga bi-apoiada de **15 x 60 cm** com vão de **7,0 m**, carga **800 kgf/m**:

* Concreto: fck = 30 MPa
* Armadura Longitudinal Inferior: 2 φ 16,0 mm
* Porta-estribo superior: 2 φ 8,0 mm
* Estribos: φ 6,3 mm c/ 15 cm

| Pos. | Função | Diâmetro |
| N1 | Longitudinal Inferior | 16,0 mm |

#### Análise Técnica
M_Sd = 87,89 kN·m conforme NBR 6118.
"""


def test_build_memoria_pdf_and_docx():
    pdf, mt, name = build_chat_document(
        kind="memoria",
        fmt="pdf",
        text=SAMPLE,
        discipline="ESTRUTURAL",
        source_question="calcule uma viga bi-apoiada",
    )
    assert mt == "application/pdf"
    assert name.endswith(".pdf")
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 2000

    docx, mt2, name2 = build_chat_document(
        kind="memoria",
        fmt="docx",
        text=SAMPLE,
        discipline="ESTRUTURAL",
    )
    assert "wordprocessingml" in mt2
    assert name2.endswith(".docx")
    assert docx[:2] == b"PK"
    # Cabeçalho institucional (partes Word)
    assert b"word/" in docx or b"word\\" in docx or docx[:2] == b"PK"


def test_build_trd_pdf():
    data = build_chat_pdf(kind="trd", text=SAMPLE, title="TRD Viga")
    assert data[:4] == b"%PDF"
    assert len(data) > 1500


def test_build_docx_helpers():
    data = build_chat_docx(kind="resposta", text=SAMPLE * 2)
    assert data[:2] == b"PK"


def test_parse_beam_and_croqui_png():
    q = "calcule uma viga bi-apoiada dim 15x60 cm vão 7m, carga 800kgf/m, fck 30mpa"
    spec = parse_beam_spec(SAMPLE, q)
    assert spec is not None
    assert spec.width_cm == 15
    assert spec.height_cm == 60
    assert abs(spec.span_m - 7.0) < 0.01
    assert spec.bottom_phi == 16.0
    assert abs(spec.stirrup_spacing_cm - 15.0) < 0.01

    out = try_build_structural_croqui(SAMPLE, q)
    assert out is not None
    png, mime = out
    assert mime == "image/png"
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 5000


def test_build_parecer_and_checklist():
    parecer = build_chat_pdf(kind="parecer", text=SAMPLE * 2, title="Parecer")
    assert parecer[:4] == b"%PDF"
    chk = build_chat_docx(kind="checklist", text=SAMPLE * 2)
    assert chk[:2] == b"PK"


def test_suggest_structural_prefers_memoria_and_croqui():
    from core.chat.document_suggestions import suggest_chat_documents

    items = suggest_chat_documents(
        SAMPLE * 3,
        discipline="ESTRUTURAL",
        source_question="calcule uma viga bi-apoiada 15x60",
    )
    kinds = [i.kind for i in items]
    assert "memoria" in kinds
    assert "croqui" in kinds
    assert kinds[0] in ("memoria", "croqui", "trd")


def test_suggest_orcamento_and_pci():
    from core.chat.document_suggestions import suggest_chat_documents

    orc = (
        "Orçamento estimativo com base SINAPI e BDI de 25%. "
        "Composições de serviço e preço unitário dos insumos. " * 8
    )
    items = suggest_chat_documents(orc, discipline="ORÇAMENTO")
    kinds = [i.kind for i in items]
    assert "nota_orcamento" in kinds
    assert "croqui" not in kinds

    pci = (
        "Checklist PCI conforme IT-11 CBMAM e PPCI. "
        "Itens de verificação de conformidade do projeto. " * 8
    )
    pci_items = suggest_chat_documents(pci, discipline="PCI")
    assert any(i.kind == "checklist" for i in pci_items)


def test_suggest_parecer():
    from core.chat.document_suggestions import suggest_chat_documents

    text = (
        "Parecer técnico sobre não conformidade estrutural. "
        "Análise crítica e diagnóstico com recomendação normativa. " * 10
    )
    items = suggest_chat_documents(text, discipline="ESTRUTURAL")
    assert any(i.kind == "parecer" for i in items)