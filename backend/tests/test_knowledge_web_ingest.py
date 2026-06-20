"""Testes — importação web de knowledge."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.knowledge.web_ingest.downloader import _filename_from_response
from core.knowledge.web_ingest.parser import extract_download_links
from core.knowledge.web_ingest.pagination import listing_page_urls, merge_unique_links
from core.knowledge.web_ingest.security import UnsafeURLError, validate_public_http_url


PSCIP_TABLE_HTML = """
<html><body><table>
<tr><th>Nome</th><th>Ação</th></tr>
<tr><td>ANEXO A - MEMORIAL DESCRITIVO PSCIP.docx</td>
<td><a href="/portal/download?id=1001">Baixar</a></td></tr>
<tr><td>ANEXO B - PLANTA DE RISCO.docx</td>
<td><a href="/portal/download?id=1002"> Baixar </a></td></tr>
<tr><td>ANEXO C - QUADRO RESUMO.docx</td>
<td><a href="/files/anexo-c.docx">Baixar</a></td></tr>
</table></body></html>
"""

CBMAM_POST_FORM_HTML = """
<html><body><table>
<tr><th>Nome do Anexo</th><th class="actions">Ação</th></tr>
<tr>
<td>ANEXO A - MEMORIAL DESCRITIVO PSCIP.docx</td>
<td class="actions">
<form method="post" action="/anexo-legislacaos/download/78">
<input type="hidden" name="_method" value="POST"/>
<input type="hidden" name="_csrfToken" value="token-a"/>
</form>
<a href="#" onclick="document.forms[0].submit();">Baixar</a>
</td></tr>
<tr>
<td>ANEXO B - MEMORIAL DESCRITIVO PSGLP.docx</td>
<td class="actions">
<form method="post" action="/anexo-legislacaos/download/79">
<input type="hidden" name="_method" value="POST"/>
<input type="hidden" name="_csrfToken" value="token-b"/>
</form>
<a href="#">Baixar</a>
</td></tr>
</table></body></html>
"""

CBMAM_VER_ANEXOS_WITH_NOISE_HTML = """
<html><body>
<table>
<tr><th>Nome do Anexo</th><th class="actions">Ação</th></tr>
<tr><td>ANEXO A - MEMORIAL DESCRITIVO PSCIP.docx</td><td><a href="/portal/download?id=1001">Baixar</a></td></tr>
<tr><td>ANEXO B - MEMORIAL DESCRITIVO PSGLP.docx</td><td><a href="/portal/download?id=1002">Baixar</a></td></tr>
</table>

<!-- Tabela/trecho irrelevante que também tem "download" -->
<table>
<tr><td>70</td><td><a href="/legislacaos/download/70">Download</a></td></tr>
</table>
</body></html>
"""

SAMPLE_HTML = """
<html><body><table>
<tr><td>ANEXO A - MEMORIAL DESCRITIVO PSCIP.docx</td>
<td><a href="/files/anexo-a.docx">Baixar</a></td></tr>
<tr><td>ANEXO B - PLANTA.docx</td>
<td><a href="/files/anexo-b.docx">Baixar</a></td></tr>
<tr><td><a href="/externo/manual.pdf">Download PDF</a></td></tr>
</table></body></html>
"""


def test_extract_download_links():
    links = extract_download_links(SAMPLE_HTML, "https://example.com/anexos")
    assert len(links) >= 2
    urls = {l["url"] for l in links}
    assert "https://example.com/files/anexo-a.docx" in urls


def test_extract_pscip_table_without_extension_in_href():
    links = extract_download_links(PSCIP_TABLE_HTML, "https://cbmam.gov.br/anexos")
    assert len(links) == 3
    first = links[0]
    assert "ANEXO A" in first["hint_filename"]
    assert first["hint_suffix"] == ".docx"


def test_filename_from_content_type_and_hint():
    name = _filename_from_response(
        "https://site.gov/download?id=1",
        "",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        hint_filename="ANEXO A - MEMORIAL.docx",
    )
    assert name.endswith(".docx")


def test_extract_download_links_table_rows():
    links = extract_download_links(SAMPLE_HTML, "https://example.com/anexos")
    names = {l["name"] for l in links}
    assert any("ANEXO A" in n for n in names)


def test_extract_cbmam_post_form_table():
    links = extract_download_links(CBMAM_POST_FORM_HTML, "https://sisgat.cbm.am.gov.br/portal/ver-anexos/175")
    assert len(links) == 2
    assert links[0]["url"].endswith("/download/78")
    assert links[1]["url"].endswith("/download/79")
    assert "post_data" in links[0]
    assert links[0]["post_data"]["_csrfToken"] == "token-a"
    assert "ANEXO A" in links[0]["hint_filename"]

def test_extract_ver_anexos_ignores_numeric_noise_rows():
    links = extract_download_links(
        CBMAM_VER_ANEXOS_WITH_NOISE_HTML,
        "https://sisgat.cbm.am.gov.br/portal/ver-anexos/175",
    )
    names = {l["name"] for l in links}
    assert any("ANEXO A" in n for n in names)
    assert any("ANEXO B" in n for n in names)
    assert "70" not in names


CBMAM_IT_TABLE_HTML = """
<html><body><table>
<tr><td>Instrução Técnica</td><td>2</td><td>2019</td><td>SIM</td>
<td>Conceitos básicos de segurança contra incêndio.</td><td>---</td>
<td><a href="/legislacaos/download/70">Download</a></td></tr>
<tr><td>Instrução Técnica</td><td>15</td><td>2019</td><td>SIM</td>
<td>Controle de fumaça - parte 1</td><td>---</td>
<td><a href="/legislacaos/download/87">Download</a></td></tr>
</table></body></html>
"""


def test_extract_cbmam_legislation_table_uses_assunto():
    links = extract_download_links(CBMAM_IT_TABLE_HTML, "https://sisgat.cbm.am.gov.br/portal/legislacaos/4")
    assert len(links) == 2
    urls = [l["url"] for l in links]
    assert len(urls) == len(set(urls))
    assert "Conceitos básicos" in links[0]["name"]
    assert "Nº 2" in links[0]["name"]
    assert "Controle de fumaça" in links[1]["name"]
    assert links[0]["hint_suffix"] == ".pdf"
    assert links[0]["hint_filename"].endswith(".pdf")
    assert not any(l["name"].isdigit() for l in links)
    assert not any(l["name"].lower() == "download" for l in links)


def test_validate_public_http_url_blocks_localhost():
    try:
        validate_public_http_url("http://127.0.0.1/secret")
        assert False, "expected UnsafeURLError"
    except UnsafeURLError:
        pass


def test_validate_public_http_url_accepts_public_ip():
    url = validate_public_http_url("https://93.184.216.34/page")
    assert url.startswith("https://")


CBMAM_PAGINATION_HTML = """
<html><body>
<p>Página 1 de 3, exibindo 20 registro(s) de 45</p>
<ul class="pagination">
<li><a href="/portal/legislacaos/4?page=2">2</a></li>
<li class="last"><a href="/portal/legislacaos/4?page=3">Última</a></li>
</ul>
</body></html>
"""


def test_listing_page_urls_cbmam():
    urls = listing_page_urls(
        CBMAM_PAGINATION_HTML,
        "https://sisgat.cbm.am.gov.br/portal/legislacaos/4",
    )
    assert urls == [
        "https://sisgat.cbm.am.gov.br/portal/legislacaos/4",
        "https://sisgat.cbm.am.gov.br/portal/legislacaos/4?page=2",
        "https://sisgat.cbm.am.gov.br/portal/legislacaos/4?page=3",
    ]


def test_merge_unique_links_by_url():
    batch_a = [{"url": "https://x/a", "name": "Doc A"}]
    batch_b = [{"url": "https://x/a", "name": "Dup"}, {"url": "https://x/b", "name": "Doc B"}]
    merged = merge_unique_links([batch_a, batch_b], max_links=10)
    assert len(merged) == 2
    assert merged[0]["name"] == "Doc A"
