"""L17 — Memória visual: croqui/overlay cotado sobre fotos do laudo."""

from __future__ import annotations

import io
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

OVERLAY_TYPES = frozenset({"line", "arrow", "rect", "label", "circle"})
MAX_CROQUIS = 8
MAX_OVERLAYS_PER_PHOTO = 30
DEFAULT_COLOR = "#dc2626"
DEFAULT_STROKE = 3
DEFAULT_FONT_SIZE = 18
_HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")
_HEX3_RE = re.compile(r"^#?[0-9a-fA-F]{3}$")


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _clamp01(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, x))


def normalize_color(raw: Any) -> str:
    s = str(raw or "").strip()
    if _HEX3_RE.match(s):
        h = s.lstrip("#")
        s = f"#{h[0] * 2}{h[1] * 2}{h[2] * 2}"
    if not s.startswith("#"):
        s = f"#{s}"
    if _HEX_RE.match(s):
        return s.lower()
    return DEFAULT_COLOR


def normalize_stroke(raw: Any) -> int:
    try:
        n = int(round(float(raw)))
    except (TypeError, ValueError):
        n = DEFAULT_STROKE
    return max(1, min(12, n))


def normalize_font_size(raw: Any) -> int:
    try:
        n = int(round(float(raw)))
    except (TypeError, ValueError):
        n = DEFAULT_FONT_SIZE
    return max(10, min(64, n))


def color_rgba(hex_color: str, alpha: int = 230) -> tuple[int, int, int, int]:
    c = normalize_color(hex_color).lstrip("#")
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    return (r, g, b, max(0, min(255, int(alpha))))


def normalize_overlay(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    data = dict(raw or {})
    otype = str(data.get("type") or "label").strip().lower()
    if otype not in OVERLAY_TYPES:
        otype = "label"
    pts_raw = data.get("points") or []
    if not isinstance(pts_raw, list):
        pts_raw = []
    points = [_clamp01(p, 0.0) for p in pts_raw[:16]]
    if otype in ("line", "arrow") and len(points) < 4:
        return None
    if otype in ("rect", "circle") and len(points) < 4:
        return None
    if otype == "label" and len(points) < 2:
        return None
    return {
        "id": str(data.get("id") or uuid.uuid4()),
        "type": otype,
        "points": points,
        "label": str(data.get("label") or "").strip()[:120] or None,
        "unit": str(data.get("unit") or "").strip()[:20] or None,
        "color": normalize_color(data.get("color")),
        "stroke": normalize_stroke(data.get("stroke", DEFAULT_STROKE)),
        "font_size": normalize_font_size(data.get("font_size", DEFAULT_FONT_SIZE)),
        "filled": bool(data.get("filled", otype in ("rect", "circle"))),
    }


def normalize_visual_memory_item(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    data = dict(raw or {})
    asset_id = str(data.get("asset_id") or "").strip()
    if not asset_id:
        return None
    overlays_raw = data.get("overlays") or []
    if not isinstance(overlays_raw, list):
        overlays_raw = []
    overlays: list[dict[str, Any]] = []
    for o in overlays_raw[:MAX_OVERLAYS_PER_PHOTO]:
        if not isinstance(o, dict):
            continue
        n = normalize_overlay(o)
        if n:
            overlays.append(n)
    return {
        "id": str(data.get("id") or uuid.uuid4()),
        "asset_id": asset_id,
        "photo_number": data.get("photo_number"),
        "overlays": overlays,
        "updated_at": str(data.get("updated_at") or _now_iso()),
    }


def list_visual_memory(content: dict[str, Any] | None) -> list[dict[str, Any]]:
    raw = (content or {}).get("visual_memory")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw[:MAX_CROQUIS]:
        if not isinstance(item, dict):
            continue
        n = normalize_visual_memory_item(item)
        if n:
            out.append(n)
    return out


def validate_visual_memory(items: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if len(items) > MAX_CROQUIS:
        errors.append(f"Máximo de {MAX_CROQUIS} croquis por laudo")
    seen_assets: set[str] = set()
    for i, raw in enumerate(items):
        if not isinstance(raw, dict):
            errors.append(f"Item {i + 1}: formato inválido")
            continue
        item = normalize_visual_memory_item(raw)
        if not item:
            errors.append(f"Item {i + 1}: asset_id obrigatório")
            continue
        aid = item["asset_id"]
        if aid in seen_assets:
            errors.append(f"Croqui duplicado para asset {aid}")
        seen_assets.add(aid)
        if len(item["overlays"]) > MAX_OVERLAYS_PER_PHOTO:
            errors.append(f"Item {i + 1}: máximo {MAX_OVERLAYS_PER_PHOTO} overlays")
    return errors


def merge_visual_memory(content: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = []
    for x in items:
        if not isinstance(x, dict):
            continue
        n = normalize_visual_memory_item(x)
        if n:
            n["updated_at"] = _now_iso()
            normalized.append(n)
    out = dict(content or {})
    out["visual_memory"] = normalized[:MAX_CROQUIS]
    return out


def memory_for_asset(content: dict[str, Any] | None, asset_id: str | None) -> dict[str, Any] | None:
    if not asset_id:
        return None
    aid = str(asset_id).strip()
    for item in list_visual_memory(content):
        if item.get("asset_id") == aid:
            return item
    return None


def memory_for_photo_number(content: dict[str, Any] | None, photo_number: int | None) -> dict[str, Any] | None:
    if photo_number is None:
        return None
    for item in list_visual_memory(content):
        try:
            if int(item.get("photo_number") or -1) == int(photo_number):
                return item
        except (TypeError, ValueError):
            continue
    return None


def _font(size: int = 18) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    except Exception:
        try:
            return ImageFont.truetype(
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", size
            )
        except Exception:
            return ImageFont.load_default()


def _stroke_px(w: int, h: int, stroke: int) -> int:
    base = max(1, min(w, h) // 220)
    return max(1, int(round(base * max(1, stroke) / 2.0)))


def _draw_arrow_head(
    draw: ImageDraw.ImageDraw,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    color: tuple,
    *,
    size: float = 14,
) -> None:
    import math

    angle = math.atan2(y1 - y0, x1 - x0)
    p1 = (x1 - size * math.cos(angle - 0.45), y1 - size * math.sin(angle - 0.45))
    p2 = (x1 - size * math.cos(angle + 0.45), y1 - size * math.sin(angle + 0.45))
    draw.polygon([(x1, y1), p1, p2], fill=color)


def render_overlay_png(
    photo_path: str | Path,
    overlays: list[dict[str, Any]],
    *,
    max_edge_px: int = 0,
) -> bytes:
    """Desenha overlays cotados sobre a foto e retorna PNG.

    Se ``max_edge_px`` > 0, redimensiona a base antes de desenhar (export mais leve).
    """
    from core.inspection_report.analytics import open_image_upright

    img = open_image_upright(photo_path).convert("RGBA")
    w0, h0 = img.size
    edge = max(w0, h0)
    if max_edge_px > 0 and edge > max_edge_px:
        scale = max_edge_px / float(edge)
        img = img.resize(
            (max(1, int(w0 * scale)), max(1, int(h0 * scale))),
            Image.Resampling.LANCZOS,
        )
    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for o in overlays:
        if not isinstance(o, dict):
            continue
        n = normalize_overlay(o) or o
        otype = n.get("type")
        pts = n.get("points") or []
        label = n.get("label") or ""
        unit = n.get("unit") or ""
        text = f"{label} {unit}".strip() if unit else (label or "")
        color = color_rgba(n.get("color") or DEFAULT_COLOR, 230)
        color_fill = color_rgba(n.get("color") or DEFAULT_COLOR, 45)
        stroke = normalize_stroke(n.get("stroke", DEFAULT_STROKE))
        font_size = normalize_font_size(n.get("font_size", DEFAULT_FONT_SIZE))
        # Escala fonte relativa ao tamanho da imagem exportada
        scaled_font = max(10, int(round(font_size * (min(w, h) / 900.0))))
        font = _font(scaled_font)
        lw = _stroke_px(w, h, stroke)
        filled = bool(n.get("filled", True))

        if otype in ("line", "arrow") and len(pts) >= 4:
            x0, y0 = pts[0] * w, pts[1] * h
            x1, y1 = pts[2] * w, pts[3] * h
            draw.line([(x0, y0), (x1, y1)], fill=color, width=lw)
            if otype == "arrow":
                _draw_arrow_head(draw, x0, y0, x1, y1, color, size=max(10, lw * 4))
            if text:
                mx, my = (x0 + x1) / 2, (y0 + y1) / 2 - scaled_font
                bbox = draw.textbbox((mx, my), text, font=font)
                pad = 3
                draw.rectangle(
                    [bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad],
                    fill=(15, 23, 42, 200),
                )
                draw.text((mx, my), text, fill=color, font=font)
        elif otype == "rect" and len(pts) >= 4:
            x0, y0 = pts[0] * w, pts[1] * h
            x1, y1 = pts[2] * w, pts[3] * h
            box = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
            draw.rectangle(
                box,
                outline=color,
                width=lw,
                fill=color_fill if filled else None,
            )
            if text:
                draw.text((box[0] + 4, box[1] + 4), text, fill=color, font=font)
        elif otype == "circle" and len(pts) >= 4:
            x0, y0 = pts[0] * w, pts[1] * h
            x1, y1 = pts[2] * w, pts[3] * h
            box = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
            draw.ellipse(
                box,
                outline=color,
                width=lw,
                fill=color_fill if filled else None,
            )
            if text:
                cx = (box[0] + box[2]) / 2
                cy = (box[1] + box[3]) / 2
                bbox = draw.textbbox((cx, cy), text, font=font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                draw.text((cx - tw / 2, cy - th / 2), text, fill=color, font=font)
        elif otype == "label" and len(pts) >= 2:
            x, y = pts[0] * w, pts[1] * h
            if text:
                bbox = draw.textbbox((x, y), text, font=font)
                pad = 4
                draw.rectangle(
                    [bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad],
                    fill=(255, 255, 255, 210),
                    outline=color,
                    width=max(1, lw // 2),
                )
                draw.text((x, y), text, fill=color, font=font)
            else:
                r = max(5, lw + 2)
                draw.ellipse([x - r, y - r, x + r, y + r], fill=color)

    composed = Image.alpha_composite(img, overlay).convert("RGB")
    buf = io.BytesIO()
    composed.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# Limites padrão do export (Word/PDF) — evita PDFs de dezenas de MB e timeouts no proxy Next.
EXPORT_MAX_EDGE_PX = 1400
EXPORT_JPEG_QUALITY = 80


def image_bytes_with_visual_memory(
    photo_path: str | Path,
    content: dict[str, Any] | None,
    *,
    asset_id: str | None = None,
    photo_number: int | None = None,
    max_edge_px: int = EXPORT_MAX_EDGE_PX,
    quality: int = EXPORT_JPEG_QUALITY,
) -> bytes:
    """Bytes da foto com croqui, se houver; senão JPEG upright redimensionado."""
    from core.inspection_report.analytics import image_bytes_for_export

    mem = memory_for_asset(content, asset_id) or memory_for_photo_number(content, photo_number)
    if mem and mem.get("overlays"):
        try:
            png = render_overlay_png(
                photo_path,
                mem["overlays"],
                max_edge_px=max_edge_px if max_edge_px > 0 else 0,
            )
            img = Image.open(io.BytesIO(png)).convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            return buf.getvalue()
        except Exception:
            pass
    return image_bytes_for_export(
        str(photo_path),
        max_edge_px=max_edge_px,
        quality=quality,
    )


def build_visual_memory_view(report: Any) -> dict[str, Any]:
    content = report.content if hasattr(report, "content") else {}
    items = list_visual_memory(content)
    photos = []
    for a in getattr(report, "assets", None) or []:
        if getattr(a, "kind", None) != "image":
            continue
        photos.append(
            {
                "asset_id": str(a.id),
                "filename": a.filename,
                "photo_number": a.photo_number,
                "caption": a.caption,
            }
        )
    return {
        "items": items,
        "photos": photos,
        "count": len(items),
        "max_croquis": MAX_CROQUIS,
    }
