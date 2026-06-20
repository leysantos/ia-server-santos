"""Detecção e navegação de paginação em listagens (ex.: CBMAM legislacaos)."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse, urlunparse

_PAGE_COUNT_RE = re.compile(r"Página\s+\d+\s+de\s+(\d+)", re.I)
_PAGE_LINK_RE = re.compile(r"""href=["']([^"']*\?page=\d+[^"']*)["']""", re.I)


def listing_page_urls(html: str, page_url: str) -> list[str]:
    """
    Retorna URLs de todas as páginas de uma listagem paginada.

    CBMAM ex.: «Página 1 de 6, exibindo 20 registro(s) de 103» → 6 URLs.
    """
    parsed = urlparse(page_url)
    base_path = parsed.path.rstrip("/") or parsed.path
    base = urlunparse((parsed.scheme, parsed.netloc, base_path, "", "", ""))

    total_pages = 1
    match = _PAGE_COUNT_RE.search(html)
    if match:
        total_pages = max(1, int(match.group(1)))
    else:
        page_nums = set()
        for href in _PAGE_LINK_RE.findall(html):
            page_match = re.search(r"[?&]page=(\d+)", href, re.I)
            if page_match:
                page_nums.add(int(page_match.group(1)))
        if page_nums:
            total_pages = max(page_nums)

    urls: list[str] = []
    for page_num in range(1, total_pages + 1):
        if page_num == 1:
            urls.append(base)
        else:
            urls.append(f"{base}?page={page_num}")
    return urls


def merge_unique_links(
    link_lists: list[list[dict]],
    *,
    max_links: int,
) -> list[dict]:
    """Mescla listas de links deduplicando por URL absoluta."""
    seen: set[str] = set()
    merged: list[dict] = []
    for links in link_lists:
        for item in links:
            url = str(item.get("url") or "")
            if not url or url in seen:
                continue
            seen.add(url)
            merged.append(item)
            if len(merged) >= max_links:
                return merged
    return merged
