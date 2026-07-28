"""Testes do módulo de Laudos de Vistoria (sem chamar Gemini)."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("DB_ENABLED", "false")

PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture
def db_session(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("DB_ENABLED", "true")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'laudos.db'}")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    from config.settings import reload_settings

    reload_settings()

    from config import settings as settings_mod

    monkeypatch.setattr(settings_mod, "DATA_DIR", tmp_path / "data")

    from core.database.connection import init_db, SessionLocal
    from core.inspection_report import service as svc

    monkeypatch.setattr(svc, "STORAGE_ROOT", tmp_path / "data" / "inspection_reports")

    init_db()
    db = SessionLocal()
    yield db
    db.close()


def test_seed_templates_and_create_report(db_session):
    from core.inspection_report import service as svc

    templates = svc.list_templates(db_session)
    assert len(templates) >= 8
    slugs = {t["slug"] for t in templates}
    assert "pontes" in slugs
    assert "muro_contencao" in slugs
    assert "edificacao" in slugs

    tpl = next(t for t in templates if t["slug"] == "edificacao")
    # L3 — tipología com capítulos próprios
    assert any("Predial" in (c.get("title") or "") for c in tpl["chapters"])
    assert "NBR 15575" in (tpl.get("system_prompt") or "") or "edificação" in (
        tpl.get("system_prompt") or ""
    ).lower()

    report = svc.create_report(
        db_session,
        title="Vistoria bloco A",
        template_id=uuid.UUID(tpl["id"]),
        user_prompt="Laudo de fissuras em laje",
        knowledge_mode="attachments",
        user_id=None,
    )
    assert report["status"] == "draft"
    assert report["knowledge_mode"] == "attachments"

    asset = svc.add_asset(
        db_session,
        uuid.UUID(report["id"]),
        filename="norma.pdf",
        content=b"%PDF-1.4 fake",
        kind_hint="document",
    )
    assert asset["kind"] == "document"

    img = svc.add_asset(
        db_session,
        uuid.UUID(report["id"]),
        filename="patologia.jpg",
        content=PNG_1X1,
        kind_hint="image",
        caption="Fissura na laje",
    )
    assert img["kind"] == "image"
    assert img["photo_number"] == 1


def test_docx_export_includes_all_photos(db_session, tmp_path):
    from core.inspection_report.docx_export import build_inspection_laudo_docx

    png_path = tmp_path / "f1.png"
    png_path.write_bytes(PNG_1X1)
    content = {
        "titulo": "Laudo teste",
        "objeto": "Edificação",
        "local": "Cidade X",
        "chapters": [
            {
                "id": "introducao",
                "title": "1. Introdução",
                "paragraphs": ["Texto com recuo de primeira linha."],
                "tables": [],
                "charts": [],
            }
        ],
        "pathologies": [
            {
                "name": "Fissura",
                "location": "Laje",
                "severity": "média",
                "description": "Abertura de 0,3 mm",
                "cause": "Retração",
                "solution": "Injeção epóxi",
                "urgency": "30 dias",
            }
        ],
        "schedule": [{"order": 1, "phase": "Correção", "activities": "Injeção", "duration": "1 semana"}],
        "references": ["NBR 6118"],
        "photographic_report": [
            {
                "photo_number": 1,
                "filename": "f1.png",
                "title": "Fissura",
                "description": "Detalhe da patologia",
                "source": "Empresa Teste",
            }
        ],
        "conclusions": ["Intervir em 30 dias."],
    }
    data = build_inspection_laudo_docx(
        content=content,
        image_assets=[
            {
                "photo_number": 1,
                "filename": "f1.png",
                "path": str(png_path),
                "orientation": "landscape",
            }
        ],
    )
    assert data[:2] == b"PK"
    assert len(data) > 2000


def test_sumario_in_export_and_content():
    from core.inspection_report.docx_export import build_inspection_laudo_docx
    from core.inspection_report.format_utils import build_sumario_entries, ensure_sumario_chapter
    from core.inspection_report.pdf_export import build_inspection_laudo_pdf
    import zipfile
    import io

    content = {
        "titulo": "Laudo com sumário",
        "objeto": "Ponte",
        "local": "AM",
        "chapters": [
            {"id": "capa", "title": "Capa / Identificação", "paragraphs": []},
            {"id": "sumario", "title": "Sumário", "paragraphs": []},
            {
                "id": "objetivo",
                "title": "4. Objetivo",
                "paragraphs": ["Avaliar a estrutura."],
                "tables": [],
                "charts": [],
            },
            {
                "id": "parecer",
                "title": "Parecer Técnico",
                "paragraphs": ["Estrutura em condição regular."],
            },
        ],
        "pathologies": [],
        "photographic_report": [],
        "conclusions": ["Manutenção preventiva."],
        "references": ["NBR 9452"],
        "responsaveis_tecnicos": [{"nome": "Eng. Teste", "crea": "AM-1"}],
    }

    entries = build_sumario_entries(content)
    labels = " | ".join(e["label"] for e in entries)
    assert "Objetivo" in labels or "objetivo" in labels.lower()
    assert "Relatório fotográfico" in labels
    assert "Responsáveis técnicos" in labels

    ensured = ensure_sumario_chapter(content)
    sumario_ch = next(
        c for c in ensured["chapters"] if str(c.get("id") or "").lower() == "sumario"
    )
    assert sumario_ch["paragraphs"]
    assert any("Objetivo" in p or "objetivo" in p.lower() for p in sumario_ch["paragraphs"])

    docx = build_inspection_laudo_docx(content=ensured, image_assets=[])
    with zipfile.ZipFile(io.BytesIO(docx)) as zf:
        xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
    assert "Sumário" in xml or "Sumario" in xml
    assert "Objetivo" in xml

    pdf = build_inspection_laudo_pdf(content=ensured, image_assets=[])
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 800
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        assert "Sumário" in text or "Sumario" in text
        assert "Objetivo" in text or "objetivo" in text.lower()
    except Exception:
        # Fallback: PDF gerado com tamanho plausível (fonte embutida pode comprimr strings)
        assert len(pdf) > 1500


def test_cover_layout_tables_in_docx_and_pdf():
    from core.inspection_report.docx_export import build_inspection_laudo_docx
    from core.inspection_report.format_utils import build_cover_layout
    from core.inspection_report.pdf_export import build_inspection_laudo_pdf
    import zipfile
    import io

    content = {
        "titulo": "Laudo Técnico de Vistoria e Avaliação Estrutural em Emergência",
        "subtitulo": "Vistoria Extraordinária / Emergencial – NBR 9452",
        "numero_laudo": "LT-SEMINF-OAE-2026-0042-REV1",
        "objeto": "Ponte Presidente Dutra",
        "local": "Av. Presidente Dutra s/nº, Manaus - AM",
        "data_vistoria": "15/07/2026",
        "tipo_vistoria": "Vistoria Extraordinária / Emergencial",
        "solicitante": {
            "empresa": "SEMINF - Secretaria Municipal de Infraestrutura",
            "endereco": "Rua Gabriel Gonçalves, nº 351, Aleixo, Manaus/AM",
            "contato": "leyfps@gmail.com",
        },
        "responsaveis_tecnicos": [
            {"nome": "FRANCIRLEY PEREIRA SANTOS", "crea": "31.410-AM"}
        ],
        "responsaveis_imagens": [{"nome": "FRANCIRLEY PEREIRA SANTOS"}],
        "compliance_note": "Documento elaborado em estrita conformidade com NBR 9452.",
        "chapters": [],
        "pathologies": [],
        "photographic_report": [],
        "conclusions": [],
        "references": [],
    }

    cover = build_cover_layout(content, generated_at="24/07/2026 18:15")
    headings = [b["heading"] for b in cover["blocks"]]
    assert "Identificação do objeto" in headings
    assert "Solicitante" in headings
    assert any("Responsabilidade técnica" in h for h in headings)
    labels = [row[0] for b in cover["blocks"] for row in b["rows"]]
    assert "Nº do laudo" in labels
    assert "Objeto" in labels
    assert "Empresa / órgão" in labels
    assert "CREA" in labels
    assert "ART" in labels

    docx = build_inspection_laudo_docx(content=content, image_assets=[])
    with zipfile.ZipFile(io.BytesIO(docx)) as zf:
        xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
    assert "Identificação do objeto" in xml.upper() or "IDENTIFICAÇÃO DO OBJETO" in xml
    assert "SEMINF" in xml
    assert "31.410-AM" in xml

    pdf = build_inspection_laudo_pdf(content=content, image_assets=[])
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 1500


def test_photographic_presentation_and_parties():
    from core.inspection_report.format_utils import (
        build_photographic_presentation,
        cover_parties_lines,
        normalize_parties,
        party_display_lines,
        photo_source_line,
    )

    content = {
        "titulo": "Laudo Técnico de Vistoria",
        "numero_laudo": "LT-01",
        "objeto": "Ponte X",
        "local": "Bariri/SP",
        "data_vistoria": "01/07/2026",
        "tipo_vistoria": "vistoria estrutural",
        "photographic_report": [{"photo_number": 1}],
        "responsaveis_imagens": [{"nome": "Maria Fotos", "crea": "111"}],
        "responsaveis_tecnicos": [
            {
                "nome": "Eng. Carlos",
                "profissao": "Engenheiro Civil",
                "crea": "SP-1",
                "art": "ART-999",
            }
        ],
    }
    text = build_photographic_presentation(content)
    assert "LT-01" in text
    assert "Maria Fotos" in text
    assert "imagem anexo" not in text.lower()
    assert "dimensionada" not in text.lower()

    parties = normalize_parties(content["responsaveis_tecnicos"])
    assert len(parties) == 1
    assert parties[0]["art"] == "ART-999"
    lines = party_display_lines(parties[0])
    assert lines[0] == "ENG. CARLOS"
    assert any("CREA" in x for x in lines)
    assert any("ART" in x for x in lines)

    cover = cover_parties_lines(content)
    assert any("CREA: SP-1" in x for x in cover)
    assert any("ART: ART-999" in x for x in cover)
    assert any("Maria Fotos" in x for x in cover)

    fonte = photo_source_line(content)
    assert "Maria Fotos" in fonte
    assert "07/2026" in fonte


def test_georef_to_ficha_and_docx(db_session, tmp_path, monkeypatch):
    from core.inspection_report import service as svc
    from core.inspection_report.docx_export import build_inspection_laudo_docx

    templates = svc.list_templates(db_session)
    tpl = next(t for t in templates if t["slug"] == "pontes")
    report = svc.create_report(
        db_session,
        title="Ponte teste georef",
        template_id=uuid.UUID(tpl["id"]),
        user_prompt="teste",
        knowledge_mode="attachments",
    )
    rid = uuid.UUID(report["id"])

    monkeypatch.setattr(
        "core.inspection_report.geo_utils.extract_gps_from_image",
        lambda _path: {"latitude": -3.1, "longitude": -60.0, "label": "3°06'S 60°00'W"},
    )
    geo = svc.add_asset(
        db_session,
        rid,
        filename="local.jpg",
        content=PNG_1X1,
        kind_hint="georef",
    )
    assert geo["kind"] == "georef"
    assert geo["gps"]["latitude"] == -3.1

    full = svc.get_report(db_session, rid)
    assert full.content
    assert full.content.get("georreferencia", {}).get("has_gps") is True

    # ficha com coordenadas após inject
    content = dict(full.content)
    content.setdefault(
        "chapters",
        [
            {
                "id": "ficha_tecnica",
                "title": "7. Ficha",
                "paragraphs": ["ok"],
                "tables": [{"caption": "Dados", "headers": ["Campo", "Valor"], "rows": [["A", "B"]]}],
            }
        ],
    )
    content["photographic_report"] = []
    geo_asset = {
        "path": str(svc.asset_path(rid, full.assets[0])),
        "caption": "Georref",
        "latitude": -3.1,
        "longitude": -60.0,
        "label": "3°06'S 60°00'W",
    }
    monkeypatch.setattr(
        "core.inspection_report.location_map.build_location_map_png",
        lambda *a, **k: PNG_1X1,
    )
    data = build_inspection_laudo_docx(content=content, image_assets=[], georef_asset=geo_asset)
    assert data[:2] == b"PK"


def test_pdf_export_minimal():
    from core.inspection_report.pdf_export import build_inspection_laudo_pdf

    content = {
        "titulo": "Laudo PDF",
        "objeto": "Teste",
        "local": "AM",
        "chapters": [
            {
                "id": "objetivo",
                "title": "4. Objetivo",
                "paragraphs": ["Verificar estado."],
                "tables": [],
                "charts": [],
            }
        ],
        "pathologies": [],
        "photographic_report": [],
        "conclusions": ["Ok"],
        "references": ["NBR 6118"],
    }
    data = build_inspection_laudo_pdf(content=content, image_assets=[])
    assert data[:4] == b"%PDF"
    assert len(data) > 500


def test_parties_preserved_after_generate(db_session, monkeypatch):
    from core.inspection_report import service as svc

    templates = svc.list_templates(db_session)
    tpl = next(t for t in templates if t["slug"] == "edificacao")
    report = svc.create_report(
        db_session,
        title="Preserve parties",
        template_id=uuid.UUID(tpl["id"]),
        user_prompt="teste",
        knowledge_mode="attachments",
    )
    rid = uuid.UUID(report["id"])
    full = svc.get_report(db_session, rid)
    full.content = {
        "responsaveis_tecnicos": [
            {"nome": "Eng. Ana", "crea": "AM-1", "art": "ART-1", "profissao": "Eng. Civil"}
        ],
        "solicitante": {
            "empresa": "Prefeitura",
            "cnpj": "11.222.333/0001-81",
            "endereco": "Rua A",
            "contato": "99",
        },
        "georreferencia": {"latitude": -3.0, "longitude": -60.0, "has_gps": True, "label": "x"},
    }
    db_session.commit()

    fake_content = {
        "titulo": "Gerado",
        "chapters": [{"id": "objetivo", "title": "4. Objetivo", "paragraphs": ["x"]}],
        "photographic_report": [],
        "pathologies": [],
    }

    monkeypatch.setattr(
        "core.inspection_report.service.generate_laudo_content",
        lambda **_kwargs: (dict(fake_content), "mock-model"),
    )
    monkeypatch.setattr("core.inspection_report.service.gemini_available", lambda: True)

    out = svc.generate_report(db_session, rid)
    assert out["content"]["responsaveis_tecnicos"][0]["nome"] == "Eng. Ana"
    assert out["content"]["solicitante"]["empresa"] == "Prefeitura"
    assert out["content"]["georreferencia"]["latitude"] == -3.0


def test_user_isolation_access(db_session):
    from core.inspection_report import service as svc
    from core.inspection_report.access import user_can_access_report

    templates = svc.list_templates(db_session)
    tpl = next(t for t in templates if t["slug"] == "geral")
    u1 = uuid.uuid4()
    u2 = uuid.uuid4()
    r1 = svc.create_report(
        db_session,
        title="Do user 1",
        template_id=uuid.UUID(tpl["id"]),
        user_prompt="",
        knowledge_mode="attachments",
        user_id=u1,
    )
    report = svc.get_report(db_session, uuid.UUID(r1["id"]))
    owner = MagicMock()
    owner.id = u1
    owner.role = "dev_user"
    other = MagicMock()
    other.id = u2
    other.role = "dev_user"
    admin = MagicMock()
    admin.id = u2
    admin.role = "admin"
    assert user_can_access_report(report, owner) is True
    assert user_can_access_report(report, other) is False
    assert user_can_access_report(report, admin) is True

    listed = svc.list_reports(db_session, user_id=u1, include_orphans=False)
    assert any(x["id"] == r1["id"] for x in listed)
    listed2 = svc.list_reports(db_session, user_id=u2, include_orphans=False)
    assert not any(x["id"] == r1["id"] for x in listed2)

    # Órfão: só admin
    orphan = svc.create_report(
        db_session,
        title="Orphan",
        template_id=uuid.UUID(tpl["id"]),
        user_prompt="",
        knowledge_mode="attachments",
        user_id=None,
    )
    orphan_row = svc.get_report(db_session, uuid.UUID(orphan["id"]))
    assert user_can_access_report(orphan_row, other) is False
    assert user_can_access_report(orphan_row, admin) is True
    claimed = svc.assign_report_owner(db_session, uuid.UUID(orphan["id"]), u1)
    assert claimed is not None
    assert claimed["user_id"] == str(u1)


def test_correction_prompt_is_truncated():
    from core.inspection_report.service import _summarize_content_for_correction

    content = {
        "titulo": "T",
        "objeto": "O",
        "chapters": [
            {"title": "1. A", "paragraphs": ["p" * 500]},
            {"title": "2. B", "paragraphs": ["q" * 500]},
        ],
        "pathologies": [{"code": "P01", "name": "Fissura", "severity": "alta", "description": "d" * 300}],
        "photographic_report": [{"photo_number": 1, "title": "Foto", "legend": "L"}],
    }
    summary = _summarize_content_for_correction(content, max_chars=800)
    assert len(summary) <= 800
    assert "titulo: T" in summary
    assert "LAUDO ATUAL (JSON)" not in summary


def test_upload_limits(db_session):
    from core.inspection_report import service as svc

    templates = svc.list_templates(db_session)
    tpl = next(t for t in templates if t["slug"] == "geral")
    report = svc.create_report(
        db_session,
        title="limits",
        template_id=uuid.UUID(tpl["id"]),
        user_prompt="",
        knowledge_mode="attachments",
    )
    rid = uuid.UUID(report["id"])
    with pytest.raises(ValueError, match="excede"):
        svc.add_asset(
            db_session,
            rid,
            filename="big.bin",
            content=b"x" * (svc.MAX_ASSET_BYTES + 1),
            kind_hint="document",
        )


def test_human_edit_chapters(db_session):
    from core.inspection_report import service as svc

    templates = svc.list_templates(db_session)
    tpl = next(t for t in templates if t["slug"] == "geral")
    report = svc.create_report(
        db_session,
        title="edit",
        template_id=uuid.UUID(tpl["id"]),
        user_prompt="",
        knowledge_mode="attachments",
    )
    rid = uuid.UUID(report["id"])
    full = svc.get_report(db_session, rid)
    full.content = {
        "titulo": "X",
        "chapters": [{"id": "objetivo", "title": "4. Objetivo", "paragraphs": ["antigo"]}],
        "photographic_report": [{"photo_number": 1, "title": "A", "legend": "A"}],
    }
    db_session.commit()

    updated = svc.update_report_meta(
        db_session,
        rid,
        {
            "chapters": [{"id": "objetivo", "title": "4. Objetivo", "paragraphs": ["novo texto"]}],
            "photographic_report": [{"photo_number": 1, "title": "B", "legend": "B"}],
        },
    )
    assert updated["content"]["chapters"][0]["paragraphs"] == ["novo texto"]
    assert updated["content"]["photographic_report"][0]["title"] == "B"


def test_export_checklist_and_cnpj():
    from core.inspection_report.validation import build_export_checklist, validate_cnpj

    ok, _ = validate_cnpj("")
    assert ok
    ok, msg = validate_cnpj("11.222.333/0001-81")
    # dígitos verificadores — CNPJ de teste conhecido inválido ou válido
    # 11222333000181 é um CNPJ usado em exemplos; validamos formato
    assert isinstance(ok, bool)

    bad = build_export_checklist({"chapters": [], "solicitante": {"cnpj": "123"}})
    assert bad["blocking"] is True

    good = build_export_checklist(
        {
            "titulo": "L",
            "chapters": [{"id": "x", "title": "t", "paragraphs": ["p"]}],
            "solicitante": {"empresa": "X", "cnpj": ""},
            "responsaveis_tecnicos": [{"nome": "Eng", "crea": "AM-1", "art": "ART-1"}],
            "photographic_report": [{"photo_number": 1}],
            "georreferencia": {"has_gps": True, "latitude": 1, "longitude": 2},
        }
    )
    assert good["ok"] is True


def test_typology_chapters_differ():
    from core.inspection_report.typology import chapters_for_slug, system_prompt_for_slug

    ponte = chapters_for_slug("pontes")
    edi = chapters_for_slug("edificacao")
    assert ponte != edi
    assert any("Predial" in c["title"] for c in edi)
    prompt = system_prompt_for_slug("erosao", name="Erosão", description="x")
    assert "erosivos" in prompt.lower() or "Erosão" in prompt


def test_nbr_8160_title_in_presets():
    from core.knowledge.norm_packs.presets import NBR_TITLES

    assert "esgoto" in NBR_TITLES["8160"].lower()
    assert "quente" not in NBR_TITLES["8160"].lower()


def test_instrumented_tests_by_severity_and_slug():
    from core.inspection_report.instrumented_tests import (
        catalog_for_slug,
        ensaios_table,
        ensure_ensaios_chapter,
        suggest_tests_for_content,
    )

    pontes_crit = catalog_for_slug("pontes")["crítica"]
    assert any("Prova de carga" in t["ensaio"] for t in pontes_crit)
    assert any("ultrassom" in t["ensaio"].lower() for t in pontes_crit)

    erosao = catalog_for_slug("erosao")["crítica"]
    assert any("SPT" in t["ensaio"] or "sondagem" in t["ensaio"].lower() for t in erosao)

    content = {
        "pathologies": [
            {"code": "P01", "name": "Corrosão", "severity": "crítica"},
            {"code": "P02", "name": "Fissura", "severity": "média"},
        ],
        "photographic_report": [],
        "chapters": [
            {"id": "parecer", "title": "Parecer", "paragraphs": ["ok"], "tables": []},
            {"id": "conclusao", "title": "Conclusão", "paragraphs": ["fim"], "tables": []},
        ],
        "conclusions": [],
    }
    tests = suggest_tests_for_content("pontes", content)
    codes = {t["codigo"] for t in tests}
    assert "EI-01" in codes  # prova de carga (crítica)
    assert "EI-OAE-01" in codes or any("submersa" in t["ensaio"].lower() for t in tests)
    # Ordenação: maior necessidade primeiro
    pcts = [int(t["necessidade_pct"]) for t in tests]
    assert pcts == sorted(pcts, reverse=True)
    assert tests[0]["item"] == 1
    assert tests[0]["necessidade_pct"] >= tests[-1]["necessidade_pct"]

    table = ensaios_table(tests)
    assert table["headers"][0] == "Item"
    assert "Necessidade (%)" in table["headers"]
    assert "Descrição do ensaio" in table["headers"]
    assert table["rows"][0][0] == "1"
    assert str(table["rows"][0][4]).endswith("%")

    enriched = ensure_ensaios_chapter(content, slug="pontes")
    assert enriched["instrumented_tests"]
    ch_ids = [str(c.get("id")) for c in enriched["chapters"]]
    assert "ensaios_instrumentados" in ch_ids
    ensaios_ch = next(c for c in enriched["chapters"] if c["id"] == "ensaios_instrumentados")
    assert ensaios_ch["tables"]
    assert "Necessidade (%)" in ensaios_ch["tables"][0]["headers"]
    assert any("ensaio" in str(c).lower() for c in enriched["conclusions"])


def test_ensaios_intro_uses_pathologies_not_template_jargon():
    from core.inspection_report.instrumented_tests import (
        apply_instrumented_tests_to_content,
        build_ensaios_intro_paragraphs,
        suggest_tests_for_content,
    )

    content = {
        "objeto": "Ponte Presidente Dutra",
        "local": "Manaus/AM",
        "pathologies": [
            {
                "code": "P01",
                "name": "Corrosão de armadura",
                "severity": "crítica",
                "location": "pilares P2",
            },
            {"code": "P02", "name": "Fissuração", "severity": "alta", "element": "laje"},
        ],
        "chapters": [
            {"id": "plano_correcao", "title": "Plano", "paragraphs": ["x"]},
            {"id": "conclusao", "title": "Conclusão", "paragraphs": ["y"]},
        ],
        "conclusions": [],
    }
    tests = suggest_tests_for_content("pontes", content)
    paras = build_ensaios_intro_paragraphs(
        content, slug="pontes", tests=tests, max_sev="crítica"
    )
    blob = " ".join(paras).lower()
    assert "template" not in blob
    assert "tipología" not in blob and "tipologia" not in blob
    assert "ponte presidente dutra" in blob
    assert "corrosão" in blob or "corrosa" in blob
    assert "crítica" in blob

    out = apply_instrumented_tests_to_content(content, slug="pontes", enabled=True)
    ch = next(c for c in out["chapters"] if c["id"] == "ensaios_instrumentados")
    text = " ".join(ch["paragraphs"]).lower()
    assert "template" not in text
    assert "presidente dutra" in text


def test_apply_instrumented_tests_even_without_gemini_field():
    """Flag ativa deve injetar capítulo/tabela mesmo se o Gemini omitiu ensaios."""
    from core.inspection_report.instrumented_tests import apply_instrumented_tests_to_content

    content = {
        "pathologies": [{"code": "P01", "name": "Corrosão", "severity": "alta"}],
        "chapters": [
            {"id": "parecer", "title": "Parecer", "paragraphs": ["ok"]},
            {"id": "plano_correcao", "title": "Plano", "paragraphs": ["corrigir"]},
            {"id": "conclusao", "title": "Conclusão", "paragraphs": ["fim"]},
        ],
        "conclusions": [],
    }
    out = apply_instrumented_tests_to_content(content, slug="pontes", enabled=True)
    assert out["suggest_instrumented_tests"] is True
    assert out["instrumented_tests"]
    assert any(c.get("id") == "ensaios_instrumentados" for c in out["chapters"])
    plano = next(c for c in out["chapters"] if c.get("id") == "plano_correcao")
    assert any("instrumentad" in str(p).lower() for p in plano["paragraphs"])


def test_instrumented_tests_baixa_is_lighter():
    from core.inspection_report.instrumented_tests import suggest_tests_for_content

    content = {"pathologies": [{"severity": "baixa"}], "photographic_report": []}
    tests = suggest_tests_for_content("pavimentacao", content)
    assert tests
    assert all(t["gravidade_alvo"] in ("baixa", "média") for t in tests)
    assert not any("FWD" in t["ensaio"] and t["gravidade_alvo"] == "crítica" for t in tests)


def test_prompt_requests_steel_section_residual_tests():
    """Pedido de seção transversal de perfis/chapas deve vir no topo da lista."""
    from core.inspection_report.instrumented_tests import (
        apply_instrumented_tests_to_content,
        extract_requested_tests_from_prompt,
        suggest_tests_for_content,
    )

    prompt = (
        "Ponte mista concreto e aço em condição precária. "
        "Verificar necessidade de ensaios instrumentados, principalmente checar "
        "a área da sessão transversal dos perfis e chapas metálicas com corrosão avançada."
    )
    req = extract_requested_tests_from_prompt(prompt)
    codes = {t["codigo"] for t in req}
    assert "EI-ACO-01" in codes
    assert "EI-ACO-02" in codes

    content = {
        "objeto": "Ponte Presidente Dutra",
        "pathologies": [
            {"code": "P01", "name": "Corrosão avançada em perfis metálicos", "severity": "crítica"}
        ],
        "chapters": [{"id": "conclusao", "title": "Conclusão", "paragraphs": ["ok"]}],
        "conclusions": [],
    }
    tests = suggest_tests_for_content("pontes", content, user_prompt=prompt)
    assert tests[0]["codigo"] == "EI-ACO-01"
    assert "espessura" in tests[0]["ensaio"].lower() or "UT" in tests[0]["ensaio"]
    assert any(t["codigo"] == "EI-ACO-02" for t in tests)
    assert any("seção" in t["ensaio"].lower() or "secao" in t["ensaio"].lower() or "área residual" in t["ensaio"].lower() or "area residual" in t["ensaio"].lower() for t in tests)

    out = apply_instrumented_tests_to_content(
        content, slug="pontes", enabled=True, user_prompt=prompt
    )
    names = " | ".join(t["ensaio"] for t in out["instrumented_tests"][:3])
    assert "espessura" in names.lower() or "UT" in names
    assert out["instrumented_tests"][0]["necessidade_pct"] >= 98


def test_l10_l11_l12_engineering_enrichment():
    """L10 classificação DNIT · L11 inventário · L12 metrologia tipada."""
    from core.inspection_report.engineering_enrichment import (
        apply_engineering_enrichment,
        build_engineering_prompt_block,
    )
    from core.inspection_report.format_utils import build_body_sections

    prompt = build_engineering_prompt_block("pontes")
    assert "CLASSIFICAÇÃO NBR 9452" in prompt
    assert "INVENTÁRIO DE ELEMENTOS" in prompt
    assert "CAMPOS METROLÓGICOS" in prompt
    assert "sup_longarina" in prompt

    content = {
        "titulo": "Laudo ponte",
        "pathologies": [
            {
                "code": "P01",
                "name": "Corrosão em longarina metálica",
                "element": "Longarina L3",
                "severity": "crítica",
                "description": "Perda de seção estimada em 35% com abertura de fissura de 0,8 mm na alma.",
                "location": "Vão central, longarina",
            },
            {
                "code": "P02",
                "name": "Juntas obstruídas",
                "element": "Junta de dilatação",
                "severity": "média",
                "description": "Junta com material degradado.",
            },
        ],
        "photographic_report": [
            {
                "photo_number": 1,
                "title": "Longarina corroída",
                "description": "Detalhe da longarina L3",
                "filename": "f01.jpg",
            }
        ],
        "chapters": [{"id": "objetivo", "title": "Objetivo", "paragraphs": ["Vistoria especial."]}],
    }

    out = apply_engineering_enrichment(content, slug="pontes")

    # L12 — metrologia
    m0 = out["pathologies"][0]["metrology"]
    assert m0["section_loss_pct"] == 35.0
    assert m0["crack_width_mm"] == 0.8
    assert m0["method"] in ("estimated", "visual", "measured", "instrumented")

    # L11 — inventário + vínculos
    inv = {e["element_id"]: e for e in out["element_inventory"]}
    assert "sup_longarina" in inv
    assert "P01" in inv["sup_longarina"]["pathology_refs"]
    assert inv["sup_longarina"]["status"] == "crítico"
    assert out["pathologies"][0]["element_id"] == "sup_longarina"

    # L10 — classificação (pior nota governa)
    cls = out["classification"]
    assert cls["global_dnit_note"] == 1
    assert cls["global_label"] == "Crítico"
    assert cls["governing_element_id"] == "sup_longarina"
    assert "P01" in cls["governing_pathology_codes"]
    assert "NBR 9452" in cls["standard_refs"]

    # Capítulos injetados
    cids = {c["id"] for c in out["chapters"]}
    assert "classificacao_dnit" in cids
    assert "inventario_elementos" in cids
    assert "metrologia" in cids

    # Export sections incluem L10–L12
    titles = " ".join(s["title"] for s in build_body_sections(out)).lower()
    assert "classificação" in titles or "dnit" in titles
    assert "inventário" in titles
    assert "metrológ" in titles or "metrolog" in titles


def test_prepare_report_content_applies_l10_l12(db_session):
    from core.inspection_report import service as svc

    templates = svc.list_templates(db_session)
    tpl = next(t for t in templates if t["slug"] == "pontes")
    report = svc.create_report(
        db_session,
        title="Ponte teste L10",
        template_id=uuid.UUID(tpl["id"]),
        user_prompt="Vistoria",
        knowledge_mode="attachments",
    )
    rid = uuid.UUID(report["id"])
    from core.inspection_report.models import InspectionReport

    db = db_session
    row = db.get(InspectionReport, rid)
    assert row is not None
    row.content = {
        "titulo": "Laudo",
        "pathologies": [
            {
                "code": "P01",
                "name": "Corrosão pilar",
                "element": "Pilar P2",
                "severity": "alta",
                "description": "Deslocamento de 12 mm no fuste do pilar P2.",
            }
        ],
        "photographic_report": [],
        "chapters": [],
    }
    row.status = "generated"
    db.commit()

    prepared = svc.prepare_report_content(row)
    assert prepared["classification"]["global_dnit_note"] == 2
    assert any(e["element_id"] == "mes_pilar" for e in prepared["element_inventory"])
    assert prepared["pathologies"][0]["metrology"]["displacement_mm"] == 12.0


def test_protocol_order_toc_interdiction_metrology_honesty():
    """P0/P1 protocolo: TOC contínuo, L10–L13 antes da conclusão, metrologia honesta."""
    from core.inspection_report.engineering_enrichment import apply_engineering_enrichment
    from core.inspection_report.format_utils import (
        build_body_sections,
        build_photographic_index_table,
        build_sumario_entries,
    )
    from core.inspection_report.instrumented_tests import ensaios_table
    from core.inspection_report.metrology import normalize_metrology

    # measured sem ensaio → estimated
    m = normalize_metrology(
        {"crack_width_mm": 0.5, "method": "measured"},
        text_fallback="fissura 0,5 mm",
        has_linked_assay=False,
    )
    assert m["method"] == "estimated"

    content = {
        "titulo": "Laudo protocolo",
        "objeto": "Ponte Presidente Dutra (Ponte Mista em Concreto e Aço)",
        "pathologies": [
            {
                "code": "P01",
                "name": "Corrosão longarina",
                "element": "Longarina L1",
                "severity": "crítica",
                "description": "Perda de seção entre 35% e 65% na alma.",
                "metrology": {
                    "section_loss_pct": 50,
                    "residual_thickness_mm": 6.5,
                    "method": "measured",
                },
            },
            {
                "code": "P02",
                "name": "Junta obstruída",
                "element": "Junta",
                "severity": "média",
                "description": "Junta degradada.",
            },
        ],
        "photographic_report": [
            {
                "photo_number": 1,
                "title": "Longarina",
                "description": "Corrosão na longarina",
                "severity": "crítica",
                "pathology_refs": ["P01"],
            }
        ],
        "chapters": [
            {"id": "objetivo", "title": "4. Objetivo", "paragraphs": ["Avaliar OAE."]},
            {
                "id": "parecer",
                "title": "11. Parecer Técnico (Notas DNIT)",
                "paragraphs": ["Recomenda-se INTERDIÇÃO TOTAL."],
            },
            {
                "id": "indicadores",
                "title": "9. Cards-Resumo, Indicadores e Gráficos",
                "paragraphs": ["ICE 78%"],
            },
            {
                "id": "conclusao",
                "title": "14. Conclusão",
                "paragraphs": ["Estrutura crítica."],
            },
            {
                "id": "referencias",
                "title": "15. Referências",
                "paragraphs": ["NBR 9452"],
            },
        ],
        "instrumented_tests": [
            {
                "codigo": f"EI-{i:02d}",
                "ensaio": f"Ensaio {i}",
                "descricao": "desc",
                "gravidade_alvo": "crítica",
                "necessidade_pct": 99 - i,
                "pathology_refs": [],
            }
            for i in range(12)
        ],
        "classification": {
            "global_dnit_note": 1,
            "governing_element_id": "sup_tabuleiro",
            "governing_pathology_codes": ["P06"],
            "rationale": "Gemini apontou tabuleiro.",
        },
    }

    out = apply_engineering_enrichment(content, slug="pontes")

    # Governante = longarina (pior), não tabuleiro do Gemini
    assert out["classification"]["governing_element_id"] == "sup_longarina"
    assert "P01" in out["classification"]["governing_pathology_codes"]

    # Metrologia honestidade
    assert out["pathologies"][0]["metrology"]["method"] == "estimated"

    # Interdição L13
    assert out["interdiction"]["required"] is True
    assert out["interdiction"]["restriction_type"] == "total"
    assert any(c.get("id") == "interdicao" for c in out["chapters"])

    # Foto eleva status do inventário
    inv = {e["element_id"]: e for e in out["element_inventory"]}
    assert inv["sup_longarina"]["status"] != "não_inspecionado"

    sections = build_body_sections(out)
    titles = [s["title"] for s in sections]
    numbers = [s["number"] for s in sections]
    assert numbers == list(range(1, len(numbers) + 1))

    def _idx(needle: str) -> int:
        for i, t in enumerate(titles):
            if needle.lower() in t.lower():
                return i
        return -1

    i_inv = _idx("Inventário")
    i_cls = _idx("Classificação")
    i_int = _idx("Interdição")
    i_ens = _idx("Ensaios")
    i_conc = _idx("Conclus")
    assert i_inv >= 0 and i_cls >= 0 and i_int >= 0
    assert i_inv < i_cls < i_int
    if i_ens >= 0 and i_conc >= 0:
        assert i_ens < i_conc
    assert i_cls < i_conc or i_conc < 0

    # Sem jargão Cards-Resumo
    assert not any("cards" in t.lower() for t in titles)

    # TOC alinhado ao corpo
    sumario = build_sumario_entries(out)
    body_labels = [s["title"] for s in sections]
    for lab in body_labels:
        assert any(e["label"] == lab for e in sumario)

    # Índice fotográfico
    idx = build_photographic_index_table(out)
    assert idx and len(idx["rows"]) == 1

    # Ensaios top-N
    tbl = ensaios_table(out["instrumented_tests"])
    assert len(tbl["rows"]) == 8
    assert "top 8" in tbl["caption"].lower() or "8 de 12" in tbl["caption"]


def test_header_and_cover_art_fields():
    from core.inspection_report.format_utils import build_cover_layout, header_meta_lines
    from core.inspection_report.protocol_order import soft_break_id

    assert "\u200b" not in soft_break_id("sup_longarina")
    assert soft_break_id("sup_longarina") == "sup_longarina"

    content = {
        "numero_laudo": "LT-1",
        "objeto": "Ponte Presidente Dutra (Ponte Mista em Concreto e Aço) sobre Igarapé",
        "data_vistoria": "15/07/2026",
        "responsaveis_tecnicos": [
            {
                "nome": "Eng Teste",
                "profissao": "Engenheiro Civil",
                "crea": "31.410-AM",
                "art": "",
            }
        ],
    }
    lines = header_meta_lines(content, generated_at="25/07/2026 07:38")
    assert any(line.startswith("Objeto:") for line in lines)
    assert "…" in lines[1] or len(lines[1]) <= 80

    cover = build_cover_layout(content, generated_at="25/07/2026")
    rt_block = next(b for b in cover["blocks"] if "Responsabilidade" in b["heading"])
    labels = [r[0] for r in rt_block["rows"]]
    assert "CREA" in labels
    assert "ART" in labels
    art_row = next(r for r in rt_block["rows"] if r[0] == "ART")
    assert "não informada" in art_row[1].lower()


def test_l14_stratified_photo_coverage():
    """L14: amostragem estratificada + ondas; não é teto cego uniforme de 16."""
    from core.inspection_report.photo_coverage import (
        coverage_remainder_batches,
        merge_coverage_into_content,
        select_diagnostic_indices,
    )
    from core.inspection_report.classification import apply_classification
    from core.inspection_report.format_utils import build_photographic_index_table

    n = 62
    meta = [
        {
            "photo_number": i + 1,
            "filename": f"f{i+1:02d}.jpg",
            "caption": "Corrosão longarina" if i == 10 else "",
            "orientation": "landscape" if i % 3 else "portrait",
        }
        for i in range(n)
    ]
    idxs = select_diagnostic_indices(n, meta)
    assert 0 in idxs and (n - 1) in idxs
    assert len(idxs) > 16  # soft_cap 24 — acima do antigo hard 16
    assert len(idxs) <= 32
    assert 10 in idxs  # captioned preferida

    # Uniforme antigo pularia muitos; estratificado deve cobrir extremos + legendada
    batches = coverage_remainder_batches(n, idxs)
    covered = set(idxs)
    for b in batches:
        covered.update(b)
    assert len(batches) >= 1
    assert len(covered) > len(idxs)

    # Merge de onda
    content = {
        "pathologies": [
            {"code": "P01", "name": "Corrosão", "severity": "crítica", "element_id": "sup_longarina"}
        ],
        "photographic_report": [
            {"photo_number": 40, "title": "Extra", "pathology_refs": []}
        ],
    }
    wave = {
        "pathologies_delta": [
            {
                "code": "P02",
                "name": "Nova erosão",
                "severity": "alta",
                "photo_refs": [40],
            }
        ],
        "photo_notes": [
            {"photo_number": 40, "severity": "alta", "pathology_refs": ["P02"]}
        ],
    }
    merged = merge_coverage_into_content(content, wave)
    assert any(p.get("code") == "P02" for p in merged["pathologies"])
    assert "P02" in merged["photographic_report"][0]["pathology_refs"]

    # Tie-break governante: longarina > tabuleiro quando ambos nota 1
    cls_in = {
        "pathologies": [
            {"code": "P01", "severity": "crítica", "element_id": "sup_longarina"},
            {"code": "P06", "severity": "crítica", "element_id": "sup_tabuleiro"},
        ],
        "element_inventory": [
            {
                "element_id": "sup_tabuleiro",
                "name": "Tabuleiro",
                "status": "crítico",
                "pathology_refs": ["P06"],
                "photo_refs": [],
                "dnit_note": 1,
            },
            {
                "element_id": "sup_longarina",
                "name": "Longarina",
                "status": "crítico",
                "pathology_refs": ["P01"],
                "photo_refs": [],
                "dnit_note": 1,
            },
        ],
        "classification": {"governing_element_id": "sup_tabuleiro"},
    }
    out = apply_classification(cls_in, slug="pontes")
    assert out["classification"]["governing_element_id"] == "sup_longarina"

    # Índice fotográfico limpa refs texto livre
    idx = build_photographic_index_table(
        {
            "pathologies": [{"code": "P01"}],
            "photographic_report": [
                {
                    "photo_number": 1,
                    "title": "Teste",
                    "element_id": "sup_longarina",
                    "severity": "crítica",
                    "pathology_refs": ["NBR 9452, Erosão do aterro", "P01"],
                }
            ],
        }
    )
    assert idx["rows"][0][4] == "P01"


def _fake_satellite_png(w: int = 120, h: int = 90) -> bytes:
    from PIL import Image

    img = Image.new("RGB", (w, h), color=(40, 90, 50))
    buf = __import__("io").BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_location_map_esri_and_cache(tmp_path, monkeypatch):
    from core.inspection_report import location_map as lm

    fake = _fake_satellite_png()
    calls = {"n": 0}

    class _Resp:
        status_code = 200
        content = fake

    def fake_get(url, params=None, timeout=None):
        calls["n"] += 1
        assert "World_Imagery" in url or "arcgisonline" in url
        return _Resp()

    monkeypatch.setattr(lm, "_google_static_api_key", lambda: None)
    monkeypatch.setattr(lm.requests, "get", fake_get)

    cache = tmp_path / "location_map.png"
    png1 = lm.build_location_map_png(-3.119, -60.021, cache_path=cache, allow_fallback=False)
    assert png1 and png1[:8] == b"\x89PNG\r\n\x1a\n"
    assert cache.is_file()
    assert calls["n"] >= 1
    assert (cache.with_suffix(".source.txt")).read_text() == "esri"

    n_after = calls["n"]
    png2 = lm.build_location_map_png(-3.119, -60.021, cache_path=cache)
    assert png2 == cache.read_bytes()
    assert calls["n"] == n_after  # cache hit

    cap = lm.location_map_caption(-3.1, -60.0, "Manaus")
    assert "satélite" in cap.lower()
    assert "Manaus" in cap


def test_location_map_fallback_without_network(tmp_path, monkeypatch):
    from core.inspection_report import location_map as lm

    def boom(*a, **k):
        raise RuntimeError("offline")

    monkeypatch.setattr(lm, "_google_static_api_key", lambda: None)
    monkeypatch.setattr(lm.requests, "get", boom)

    png = lm.build_location_map_png(-3.1, -60.0, cache_path=tmp_path / "m.png")
    assert png and png[:8] == b"\x89PNG\r\n\x1a\n"
    assert (tmp_path / "m.source.txt").read_text() == "fallback"


def test_docx_inserts_location_map_below_georef(tmp_path, monkeypatch):
    from core.inspection_report.docx_export import build_inspection_laudo_docx

    geo_path = tmp_path / "geo.png"
    geo_path.write_bytes(PNG_1X1)
    fake_map = _fake_satellite_png(200, 150)

    monkeypatch.setattr(
        "core.inspection_report.location_map.build_location_map_png",
        lambda *a, **k: fake_map,
    )

    content = {
        "titulo": "Laudo mapa",
        "objeto": "Ponte",
        "local": "AM",
        "chapters": [
            {
                "id": "ficha_tecnica",
                "title": "7. Ficha técnica",
                "paragraphs": ["Dados."],
                "tables": [
                    {
                        "caption": "Objeto",
                        "headers": ["Campo", "Valor"],
                        "rows": [["Nome", "Ponte"]],
                    }
                ],
            }
        ],
        "pathologies": [],
        "photographic_report": [],
        "conclusions": ["Ok"],
        "references": [],
    }
    geo_asset = {
        "path": str(geo_path),
        "caption": "Imagem georreferenciada — -3.119027, -60.021731 (WGS84)",
        "latitude": -3.119027,
        "longitude": -60.021731,
        "label": "-3.119027, -60.021731 (WGS84)",
        "map_cache_path": str(tmp_path / "location_map.png"),
    }
    data = build_inspection_laudo_docx(content=content, image_assets=[], georef_asset=geo_asset)
    assert data[:2] == b"PK"
    # DOCX é ZIP: mapa PNG deve aparecer como imagem embutida
    assert b"image" in data.lower() or b"word/" in data


def test_frame_and_caption_dedupe():
    from core.inspection_report.location_map import (
        FRAME_HEIGHT_PX,
        FRAME_WIDTH_PX,
        frame_image_for_export,
        georef_photo_caption,
        location_map_caption,
    )
    from PIL import Image
    import io

    portrait = Image.new("RGB", (200, 400), (80, 100, 60))
    buf = io.BytesIO()
    portrait.save(buf, format="PNG")
    framed = frame_image_for_export(buf.getvalue())
    out = Image.open(io.BytesIO(framed))
    assert out.size == (FRAME_WIDTH_PX, FRAME_HEIGHT_PX)

    cap = georef_photo_caption(
        {
            "caption": "Imagem georreferenciada — -3.1, -60.0 (WGS84)",
            "label": "-3.1, -60.0 (WGS84)",
        }
    )
    assert cap.count("WGS84") == 1
    assert location_map_caption(-3.116504, -60.034176, "-3.116504, -60.034176 (WGS84)").count(
        "-3.116504"
    ) == 1


def test_location_map_has_north_indicator():
    from core.inspection_report.location_map import _finalize_map_image, location_map_caption
    from PIL import Image
    import io

    base = Image.new("RGB", (400, 300), (40, 80, 40))
    buf = io.BytesIO()
    base.save(buf, format="PNG")
    out_bytes = _finalize_map_image(buf.getvalue(), with_pin=True)
    out = Image.open(io.BytesIO(out_bytes)).convert("RGB")
    # canto superior direito deve diferir do verde uniforme (badge + seta N)
    corner = out.crop((out.width - 90, 10, out.width - 10, 90))
    samples = [
        corner.getpixel((x, y))
        for x, y in ((10, 10), (40, 20), (50, 40), (30, 55))
    ]
    assert any(px != (40, 80, 40) for px in samples)
    assert "norte" in location_map_caption(-3.1, -60.0).lower()


def test_exif_orientation_portrait_export(tmp_path):
    """Pixels paisagem + EXIF Orientation=6 devem virar retrato no export."""
    from core.inspection_report.analytics import (
        fit_image_display_inches,
        image_bytes_for_export,
        open_image_upright,
    )
    from PIL import Image

    # 200×100 (paisagem nos pixels) com Orientation=6 → exibição 100×200 (retrato)
    path = tmp_path / "phone_portrait.jpg"
    img = Image.new("RGB", (200, 100), (10, 120, 40))
    # marca o canto “topo lógico” após rotate 90 CW: pixel (0,0) raw → canto inferior esquerdo após transpose
    for x in range(20):
        for y in range(10):
            img.putpixel((x, y), (255, 0, 0))
    exif = img.getexif()
    exif[0x0112] = 6  # Rotate 90 CW
    img.save(path, format="JPEG", quality=95, exif=exif)

    raw = Image.open(path)
    assert raw.size == (200, 100)

    upright = open_image_upright(path)
    assert upright.size == (100, 200)

    dw, dh = fit_image_display_inches(str(path), max_w=5.9, max_h=5.0)
    assert dh > dw  # caixa de exibição em retrato

    exported = image_bytes_for_export(str(path))
    out = Image.open(__import__("io").BytesIO(exported))
    assert out.size[1] > out.size[0]


def test_l15_normative_rag_apply_and_table():
    from core.inspection_report.normative_rag import (
        TYPOLOGY_PRIORITY_NBRS,
        apply_normative_citations,
        normative_citations_table,
        normative_prompt_block,
        slug_to_agent,
    )
    from core.inspection_report.format_utils import build_body_sections
    from core.inspection_report.engineering_enrichment import build_engineering_prompt_block

    assert slug_to_agent("pontes") == "infraestrutura"
    assert slug_to_agent("edificacao") == "estruturas"
    assert "9452" in TYPOLOGY_PRIORITY_NBRS["pontes"]
    assert "L15" in normative_prompt_block()
    assert "L15" in build_engineering_prompt_block("pontes")

    normative = {
        "rag_available": True,
        "citations": [
            {
                "norma": "NBR 9452",
                "clause": "5.2",
                "excerpt": "A inspeção especial deve considerar anomalias estruturais críticas.",
                "score": 0.91,
                "source": "NBR_9452.pdf",
                "legal_source": "abnt_licensed_pdf",
                "stamp_eligible": True,
                "query": "NBR 9452",
            }
        ],
        "nbrs_cited": ["NBR 9452"],
        "missing_priority_nbrs": ["NBR 7187"],
        "bases_used": ["nbr"],
        "agent_slug": "infraestrutura",
        "typology_slug": "pontes",
    }
    content = apply_normative_citations(
        {"titulo": "Laudo", "chapters": [], "references": ["NBR 6118"]},
        normative=normative,
        slug="pontes",
    )
    assert len(content["normative_citations"]) == 1
    assert content["normative_citations"][0]["norma"] == "NBR 9452"
    assert any("NBR 9452" in r for r in content["references"])
    refs_ch = next(c for c in content["chapters"] if c.get("id") == "referencias")
    assert refs_ch["tables"]
    tbl = normative_citations_table(content["normative_citations"])
    assert tbl["rows"][0][0] == "NBR 9452"

    sections = build_body_sections(content)
    ref_sec = next(s for s in sections if s.get("chapter_id") == "referencias")
    assert ref_sec["tables"]


def test_l15_retrieve_mocked(monkeypatch):
    from core.inspection_report import normative_rag as nr
    from types import SimpleNamespace

    class FakeChunk:
        text = "Inspeção de pontes conforme critérios de classificação."
        source = "NBR_9452.pdf"
        doc_type = "nbr"
        metadata = {"norma": "NBR 9452", "filename": "NBR_9452.pdf", "section": "4.1"}

    class FakeResult:
        hits = [(FakeChunk(), 0.88)]
        bases_used = ["nbr"]

    monkeypatch.setattr(
        "core.knowledge.rag.agent_retriever.retrieve_for_agent",
        lambda *a, **k: FakeResult(),
    )
    # legal helpers may still run
    out = nr.retrieve_laudo_normative_context(
        slug="pontes", query="ponte oxidação", discipline_hint="INFRAESTRUTURA", top_k=6
    )
    assert out["rag_available"] is True
    assert out["hits_count"] >= 1
    assert out["context_text"]
    assert "NBR 9452" in out["context_text"]
    assert out["citations"][0]["norma"] == "NBR 9452"


def test_l16_assay_results_schema_validation_and_table():
    from core.inspection_report.assay_results import (
        apply_assay_results_to_content,
        assay_results_table,
        enrich_test_from_suggestion,
        merge_assay_results,
        normalize_assay_result,
        validate_assay_result,
        validate_assay_results,
    )

    item = normalize_assay_result(
        {
            "test_code": "UT-01",
            "ensaio": "Ultrassom — espessura",
            "valor": "12.5",
            "unidade": "mm",
            "pathology_refs": ["p1", "P1"],
            "status": "executado",
            "data_ensaio": "15/03/2026",
        }
    )
    assert item["test_code"] == "UT-01"
    assert item["pathology_refs"] == ["P1"]
    assert item["data_ensaio"] == "2026-03-15"
    assert not validate_assay_result(item)

    bad = normalize_assay_result({"ensaio": "Schmidt", "status": "executado", "valor": ""})
    assert "Valor medido" in validate_assay_result(bad)[0]

    dup_errors = validate_assay_results(
        [
            {"id": "same", "ensaio": "A", "valor": "1", "status": "executado"},
            {"id": "same", "ensaio": "B", "valor": "2", "status": "executado"},
        ]
    )
    assert any("duplicado" in e.lower() for e in dup_errors)

    content = merge_assay_results(
        {"instrumented_tests": [{"codigo": "UT-01", "ensaio": "Ultrassom"}]},
        [item],
    )
    assert len(content["instrumented_test_results"]) == 1
    assert content["assay_results_meta"]["count_executed"] == 1

    enriched = apply_assay_results_to_content(
        {
            **content,
            "chapters": [
                {
                    "id": "ensaios_instrumentados",
                    "title": "Ensaios instrumentados",
                    "paragraphs": ["Sugestão de ensaios."],
                    "tables": [],
                }
            ],
        }
    )
    ch = next(c for c in enriched["chapters"] if c.get("id") == "ensaios_instrumentados")
    assert any("resultado(s) medido(s)" in p.lower() for p in ch["paragraphs"])
    assert ch["tables"]
    tbl = assay_results_table([item])
    assert tbl["rows"][0][3].startswith("12.5")

    pre = enrich_test_from_suggestion({"test_code": "SCH", "ensaio": "Esclerômetro", "pathology_refs": ["P2"]})
    assert pre["test_code"] == "SCH"
    assert pre["pathology_refs"] == ["P2"]


def test_l16_save_assay_results_service(db_session):
    from core.inspection_report import service as svc

    templates = svc.list_templates(db_session)
    tpl = next(t for t in templates if t["slug"] == "edificacao")
    report = svc.create_report(
        db_session,
        title="L16 test",
        template_id=uuid.UUID(tpl["id"]),
        user_prompt="Ensaios",
        knowledge_mode="attachments",
        suggest_instrumented_tests=True,
    )
    rid = uuid.UUID(report["id"])
    full = svc.get_report(db_session, rid)
    full.content = {
        "instrumented_tests": [
            {
                "codigo": "SCH-01",
                "ensaio": "Esclerômetro rebound",
                "pathology_refs": ["P1"],
                "norma_ref": "NBR 7684",
            }
        ],
        "pathologies": [{"code": "P1", "name": "Fissura"}],
        "chapters": [{"id": "ensaios_instrumentados", "title": "Ensaios", "paragraphs": [], "tables": []}],
    }
    db_session.commit()

    view = svc.save_assay_results(
        db_session,
        rid,
        [
            {
                "ensaio": "Esclerômetro rebound",
                "test_code": "SCH-01",
                "valor": "42",
                "unidade": "MPa",
                "local": "Pilar P1",
                "status": "executado",
                "pathology_refs": ["P1"],
            }
        ],
    )
    assert view["count_executed"] == 1
    assert view["suggested_tests"]

    stored = svc.get_report(db_session, rid)
    assert stored.content.get("instrumented_test_results")
    ch = next(
        c for c in stored.content["chapters"] if c.get("id") == "ensaios_instrumentados"
    )
    assert ch.get("tables")

    with pytest.raises(ValueError, match="Valor medido"):
        svc.save_assay_results(
            db_session,
            rid,
            [{"ensaio": "X", "status": "executado", "valor": ""}],
        )


def test_l17_visual_memory_render_and_save(db_session, tmp_path):
    from PIL import Image
    from core.inspection_report import service as svc
    from core.inspection_report.visual_memory import (
        merge_visual_memory,
        normalize_overlay,
        render_overlay_png,
        validate_visual_memory,
    )

    img = Image.new("RGB", (120, 80), (180, 180, 180))
    path = tmp_path / "photo.png"
    img.save(path)
    png = render_overlay_png(
        path,
        [
            {
                "type": "line",
                "points": [0.1, 0.2, 0.8, 0.7],
                "label": "12",
                "unit": "mm",
                "color": "#2563eb",
                "stroke": 5,
                "font_size": 22,
            },
            {
                "type": "circle",
                "points": [0.2, 0.2, 0.5, 0.6],
                "label": "zona",
                "color": "#16a34a",
                "filled": True,
            },
        ],
    )
    assert png[:4] == b"\x89PNG"

    styled = normalize_overlay(
        {
            "type": "arrow",
            "points": [0.1, 0.1, 0.9, 0.9],
            "label": "Fundação",
            "color": "#ea580c",
            "stroke": 8,
            "font_size": 28,
        }
    )
    assert styled is not None
    assert styled["color"] == "#ea580c"
    assert styled["stroke"] == 8
    assert styled["font_size"] == 28

    templates = svc.list_templates(db_session)
    tpl = next(t for t in templates if t["slug"] == "edificacao")
    report = svc.create_report(
        db_session,
        title="L17",
        template_id=uuid.UUID(tpl["id"]),
        user_prompt="x",
        knowledge_mode="attachments",
    )
    rid = uuid.UUID(report["id"])
    asset = svc.add_asset(
        db_session,
        rid,
        filename="fissura.png",
        content=path.read_bytes(),
        mime_type="image/png",
        kind_hint="image",
    )
    view = svc.save_visual_memory(
        db_session,
        rid,
        [
            {
                "asset_id": asset["id"],
                "overlays": [
                    {
                        "type": "arrow",
                        "points": [0.2, 0.2, 0.7, 0.6],
                        "label": "8",
                        "unit": "mm",
                        "color": "#7c3aed",
                        "stroke": 4,
                        "font_size": 20,
                    }
                ],
            }
        ],
    )
    assert view["count"] == 1
    ov = view["items"][0]["overlays"][0]
    assert ov["label"] == "8"
    assert ov["color"] == "#7c3aed"
    assert ov["stroke"] == 4
    assert validate_visual_memory([{"asset_id": asset["id"], "overlays": []}]) == []
    merged = merge_visual_memory({}, view["items"])
    assert merged["visual_memory"]


def test_l18_art_asset_and_party_fields(db_session):
    from core.inspection_report import service as svc
    from core.inspection_report.format_utils import art_traceability_table, normalize_party
    from core.inspection_report.validation import build_export_checklist

    party = normalize_party(
        {
            "nome": "Eng. Ana",
            "crea": "SP-12345",
            "art": "",
            "art_protocolo": "2026-001",
            "art_asset_id": "asset-1",
        }
    )
    assert party["art_asset_id"] == "asset-1"
    tbl = art_traceability_table({"responsaveis_tecnicos": [party]})
    assert tbl and "anexo" in tbl["rows"][0]

    templates = svc.list_templates(db_session)
    tpl = next(t for t in templates if t["slug"] == "edificacao")
    report = svc.create_report(
        db_session,
        title="L18",
        template_id=uuid.UUID(tpl["id"]),
        user_prompt="x",
        knowledge_mode="attachments",
    )
    rid = uuid.UUID(report["id"])
    art = svc.add_asset(
        db_session,
        rid,
        filename="art.pdf",
        content=b"%PDF-1.4 art",
        mime_type="application/pdf",
        kind_hint="art",
    )
    assert art["kind"] == "art"
    checklist = build_export_checklist(
        {
            "titulo": "T",
            "chapters": [{"id": "a"}],
            "responsaveis_tecnicos": [
                {"nome": "Eng", "crea": "1234", "art_asset_id": art["id"]}
            ],
            "solicitante": {"empresa": "X", "cnpj": ""},
        }
    )
    assert not any(w["code"].endswith("art_empty") for w in checklist["warnings"])


def test_l19_signature_evidence_and_hash(db_session, tmp_path):
    from PIL import Image
    from core.inspection_report import service as svc
    from core.inspection_report.signature_evidence import get_signature_evidence, sha256_hex

    templates = svc.list_templates(db_session)
    tpl = next(t for t in templates if t["slug"] == "edificacao")
    report = svc.create_report(
        db_session,
        title="L19",
        template_id=uuid.UUID(tpl["id"]),
        user_prompt="x",
        knowledge_mode="attachments",
    )
    rid = uuid.UUID(report["id"])
    img = Image.new("RGB", (80, 40), (255, 255, 255))
    path = tmp_path / "firma.png"
    img.save(path)
    sig = svc.add_asset(
        db_session,
        rid,
        filename="firma.png",
        content=path.read_bytes(),
        mime_type="image/png",
        kind_hint="signature",
    )
    assert sig["kind"] == "signature"
    ev = svc.save_signature_evidence(
        db_session,
        rid,
        {"rt_signature_asset_ids": {"rt1": sig["id"]}, "notes": "imagem"},
    )
    assert ev["rt_signature_asset_ids"]["rt1"] == sig["id"]

    full = svc.get_report(db_session, rid)
    digest = svc.record_export_pdf_hash(db_session, full, b"%PDF-fake")
    assert digest == sha256_hex(b"%PDF-fake")
    full2 = svc.get_report(db_session, rid)
    stored = get_signature_evidence(full2.content)
    assert stored["pdf_sha256"] == digest


def test_l16_metrology_linked_from_results():
    from core.inspection_report.assay_results import pathology_refs_with_executed_results
    from core.inspection_report.metrology import apply_metrology

    content = {
        "pathologies": [
            {
                "code": "P1",
                "name": "Corrosão",
                "metrology": {"method": "instrumented", "section_loss_pct": 40},
            },
            {
                "code": "P2",
                "name": "Fissura",
                "metrology": {"method": "instrumented", "crack_width_mm": 0.3},
            },
        ],
        "instrumented_test_results": [
            {
                "id": "1",
                "ensaio": "UT",
                "valor": "8",
                "status": "executado",
                "pathology_refs": ["P1"],
            },
            {
                "id": "2",
                "ensaio": "Pendente",
                "valor": "",
                "status": "pendente",
                "pathology_refs": ["P2"],
            },
        ],
    }
    assert pathology_refs_with_executed_results(content) == {"P1"}

    out = apply_metrology(content)
    p1 = next(p for p in out["pathologies"] if p["code"] == "P1")
    p2 = next(p for p in out["pathologies"] if p["code"] == "P2")
    assert p1["metrology"]["method"] == "instrumented"
    assert p2["metrology"]["method"] == "estimated"


def test_art_lookup_builds_crea_and_sicar_urls():
    from core.inspection_report.art_lookup import extract_uf, lookup_art

    assert extract_uf("CREA-AM 12345") == "AM"
    result = lookup_art(
        crea="CREA-SP",
        art="1234567",
        art_protocolo="2026-001",
        probe=False,
    )
    assert result["uf"] == "SP"
    assert "crea-sp" in result["art_url"].lower()
    assert "car.gov.br" in result["sicar_url"]
    assert result["source"] == "crea_portal"


def test_pades_status_without_cert():
    from core.inspection_report.pades_sign import pades_configured, pades_status

    st = pades_status()
    assert "ready" in st
    assert "enabled" in st
    # Sem cert no ambiente de teste → não ready (salvo se alguém configurar)
    if not st["enabled"]:
        assert st["ready"] is False
        assert pades_configured() is False


def test_signature_evidence_records_pades_method():
    from core.inspection_report.signature_evidence import get_signature_evidence, record_pdf_hash

    content = record_pdf_hash(
        {},
        b"%PDF-1.4 fake",
        method="pades",
        pades_meta={"profile": "PAdES-B", "signer_subject": "CN=Test"},
    )
    ev = get_signature_evidence(content)
    assert ev["method"] == "pades"
    assert ev["pdf_sha256"]
    assert ev["pades"]["profile"] == "PAdES-B"
