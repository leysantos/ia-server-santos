"""Motor de templates com placeholders corporativos."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def render_template(template_text: str, context: dict[str, Any]) -> str:
    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = context.get(key, "")
        return "" if value is None else str(value)

    return _PLACEHOLDER_RE.sub(_replace, template_text)


def build_sheet_context(
    *,
    empresa: str = "",
    autor: str = "",
    crea: str = "",
    escala: str = "1:100",
    titulo: str = "",
    codigo: str = "",
    revisao: str = "REV00",
    data: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    ctx = {
        "empresa": empresa,
        "autor": autor,
        "crea": crea,
        "escala": escala,
        "titulo": titulo,
        "codigo": codigo,
        "revisao": revisao,
        "data": data or datetime.now(timezone.utc).strftime("%d/%m/%Y"),
    }
    ctx.update(extra)
    return ctx


DEFAULT_SHEET_TEMPLATE = """\
PRANCHA — {{titulo}}
Empresa: {{empresa}}
Autor: {{autor}} | CREA: {{crea}}
Código: {{codigo}} | Revisão: {{revisao}} | Escala: {{escala}}
Data: {{data}}
"""


def render_default_sheet(context: dict[str, Any]) -> str:
    return render_template(DEFAULT_SHEET_TEMPLATE, context)
