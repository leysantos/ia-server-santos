"""Helpers de tipología — capítulos e prompts por slug (L3)."""

from __future__ import annotations

from core.inspection_report.constants import (
    CHAPTERS_BY_SLUG,
    DEFAULT_CHAPTERS,
    PROMPT_EXTRAS_BY_SLUG,
    SYSTEM_PROMPT_BASE,
    TEMPLATE_DEFS,
)


def chapters_for_slug(slug: str | None) -> list[dict]:
    if not slug:
        return list(DEFAULT_CHAPTERS)
    return list(CHAPTERS_BY_SLUG.get(slug, DEFAULT_CHAPTERS))


def system_prompt_for_slug(slug: str | None, *, name: str = "", description: str = "") -> str:
    extras = PROMPT_EXTRAS_BY_SLUG.get(slug or "", "")
    header = f"\n\nTIPO DE LAUDO: {name}. {description}".strip() if name else ""
    extra_block = f"\n\nORIENTAÇÕES ESPECÍFICAS DA TIPOLOGIA:\n{extras}" if extras else ""
    return SYSTEM_PROMPT_BASE + header + extra_block


def template_seed_payload(item: dict) -> tuple[list[dict], str]:
    slug = item["slug"]
    chapters = chapters_for_slug(slug)
    prompt = system_prompt_for_slug(
        slug,
        name=item.get("name") or slug,
        description=item.get("description") or "",
    )
    return chapters, prompt


def all_template_slugs() -> list[str]:
    return [t["slug"] for t in TEMPLATE_DEFS]
