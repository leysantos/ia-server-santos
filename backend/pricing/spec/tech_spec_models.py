"""Modelos da Especificação Técnica derivada do orçamento."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def default_formatting() -> dict[str, Any]:
    return {
        "font_family": "Calibri",
        "font_size": 11,
        "line_spacing": 1.15,
        "margin_cm": 2.5,
        "page_numbers": False,
        "logo_text": None,
        "document_title": None,
    }


@dataclass
class TechSpecDocument:
    title: str = "Especificação Técnica"
    markdown: str = ""
    html_content: str = ""
    formatting: dict[str, Any] = field(default_factory=default_formatting)
    llm_model: str | None = None
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "markdown": self.markdown,
            "html_content": self.html_content or markdown_to_html(self.markdown),
            "formatting": dict(self.formatting or default_formatting()),
            "llm_model": self.llm_model,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> TechSpecDocument | None:
        if not data:
            return None
        doc = cls(
            title=str(data.get("title") or "Especificação Técnica"),
            markdown=str(data.get("markdown") or ""),
            html_content=str(data.get("html_content") or ""),
            formatting=dict(data.get("formatting") or default_formatting()),
            llm_model=data.get("llm_model"),
            updated_at=str(data.get("updated_at") or datetime.now(timezone.utc).isoformat()),
        )
        if doc.markdown and not doc.html_content:
            doc.html_content = markdown_to_html(doc.markdown)
        return doc

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()
        if self.markdown and not self.html_content:
            self.html_content = markdown_to_html(self.markdown)


def render_document_html(doc: TechSpecDocument) -> str:
    """Monta preview completo: logo + título + corpo + rodapé de páginas."""
    fmt = doc.formatting or default_formatting()
    body = doc.html_content or markdown_to_html(doc.markdown)
    parts: list[str] = []

    logo = fmt.get("logo_text")
    if logo:
        safe = html.escape(str(logo))
        parts.append(
            '<div class="tech-spec-logo" style="text-align:center;border:1px dashed #888;'
            'padding:14px;margin-bottom:18px;background:#fafafa;">'
            f"<strong>[LOGO: {safe}]</strong></div>"
        )

    doc_title = fmt.get("document_title")
    if doc_title:
        parts.append(
            f'<h1 style="text-align:center;margin-bottom:20px;">{html.escape(str(doc_title))}</h1>'
        )

    parts.append(f'<div class="tech-spec-body">{body}</div>')

    if fmt.get("page_numbers"):
        parts.append(
            '<div class="tech-spec-page-footer" style="margin-top:28px;padding-top:10px;'
            'border-top:1px solid #ccc;text-align:center;font-size:9pt;color:#555;">'
            "Página <span>1</span></div>"
        )

    return "\n".join(parts)


def extract_body_html(full_html: str) -> str:
    """Remove chrome de preview para persistir só o corpo editável."""
    if not full_html:
        return ""
    body_match = re.search(
        r'<div class="tech-spec-body"[^>]*>(.*)</div>\s*(?:<div class="tech-spec-page-footer"|$)',
        full_html,
        re.S | re.I,
    )
    if body_match:
        return body_match.group(1).strip()
    return full_html


def markdown_to_html(markdown_text: str) -> str:
    """Conversão leve Markdown → HTML para preview/editável."""
    if not markdown_text.strip():
        return "<p></p>"

    lines = markdown_text.replace("\r\n", "\n").split("\n")
    parts: list[str] = []
    in_ul = False

    def close_ul() -> None:
        nonlocal in_ul
        if in_ul:
            parts.append("</ul>")
            in_ul = False

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            close_ul()
            parts.append("<p><br></p>")
            continue

        heading = re.match(r"^(#{1,4})\s+(.+)$", line)
        if heading:
            close_ul()
            level = len(heading.group(1))
            text = _inline_md(heading.group(2))
            parts.append(f"<h{level}>{text}</h{level}>")
            continue

        bullet = re.match(r"^[-*]\s+(.+)$", line)
        if bullet:
            if not in_ul:
                parts.append("<ul>")
                in_ul = True
            parts.append(f"<li>{_inline_md(bullet.group(1))}</li>")
            continue

        close_ul()
        parts.append(f"<p>{_inline_md(line)}</p>")

    close_ul()
    return "\n".join(parts)


def _inline_md(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped)
    return escaped
