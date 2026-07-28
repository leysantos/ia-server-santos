"""Mapa de localização satélite a partir de coordenadas GPS (EXIF / georref).

Gera PNG com imagem de satélite e marcador no ponto do objeto, para inserção
na ficha técnica do laudo (abaixo da foto georreferenciada).

Provedores (nessa ordem):
1. Google Static Maps — se ``GOOGLE_MAPS_STATIC_API_KEY`` estiver definida
2. Esri World Imagery export — sem chave (uso operacional local)
"""

from __future__ import annotations

import io
import logging
import math
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

# Quadro único para foto georref + mapa (mesmas proporções no Word/PDF)
FRAME_WIDTH_IN = 5.9
FRAME_HEIGHT_IN = 3.7  # ~16:10
FRAME_WIDTH_PX = 1180
FRAME_HEIGHT_PX = 740
FRAME_BORDER_PX = 5
FRAME_BORDER_RGB = (148, 163, 184)  # cinza institucional #94A3B8
FRAME_PAD_RGB = (248, 250, 252)  # fundo do letterbox

DEFAULT_WIDTH = FRAME_WIDTH_PX
DEFAULT_HEIGHT = FRAME_HEIGHT_PX
DEFAULT_RADIUS_M = 280.0
_HTTP_TIMEOUT = 25


def _bbox_around(lat: float, lon: float, radius_m: float) -> tuple[float, float, float, float]:
    """Retorna (west, south, east, north) em WGS84."""
    dlat = radius_m / 111_320.0
    cos_lat = max(0.05, abs(math.cos(math.radians(lat))))
    dlon = radius_m / (111_320.0 * cos_lat)
    return lon - dlon, lat - dlat, lon + dlon, lat + dlat


def _draw_pin(img: Image.Image, x: int, y: int) -> None:
    """Marcador tipo alfinete vermelho no centro (x, y = ponta)."""
    draw = ImageDraw.Draw(img)
    # sombra suave
    draw.ellipse([x - 10, y - 4, x + 10, y + 6], fill=(0, 0, 0, 90))
    # corpo do pin
    r = 16
    cy = y - r - 4
    draw.ellipse([x - r, cy - r, x + r, cy + r], fill=(210, 35, 35), outline=(255, 255, 255), width=3)
    draw.polygon(
        [(x, y), (x - r + 2, cy + 4), (x + r - 2, cy + 4)],
        fill=(210, 35, 35),
    )
    # miolo branco
    draw.ellipse([x - 5, cy - 5, x + 5, cy + 5], fill=(255, 255, 255))


def _draw_north_arrow(img: Image.Image, *, margin: int | None = None) -> None:
    """Indicador de norte: seta apontando para o TOPO da imagem + letra N acima."""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    # escala proporcional, mas legível em laudos A4
    box_w = max(52, min(w, h) // 12)
    box_h = int(box_w * 1.55)
    m = margin if margin is not None else max(16, box_w // 4)
    left = w - m - box_w
    top = m
    right = left + box_w
    bottom = top + box_h

    # fundo
    try:
        draw.rounded_rectangle(
            [left, top, right, bottom],
            radius=8,
            fill=(255, 255, 255, 225),
            outline=(60, 60, 60, 230),
            width=2,
        )
    except Exception:
        draw.rectangle(
            [left, top, right, bottom],
            fill=(255, 255, 255, 225),
            outline=(60, 60, 60, 230),
            width=2,
        )

    cx = (left + right) // 2
    # Tipografia "N" NO TOPO do badge (norte = cima)
    n_top = top + 4
    try:
        from PIL import ImageFont

        font = ImageFont.load_default()
        for candidate in (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ):
            try:
                font = ImageFont.truetype(candidate, max(16, box_w // 2))
                break
            except Exception:
                continue
        # centraliza "N"
        try:
            bbox = draw.textbbox((0, 0), "N", font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception:
            tw, th = box_w // 2, box_w // 2
        draw.text((cx - tw / 2, n_top), "N", fill=(20, 20, 20, 255), font=font)
        arrow_top = n_top + th + 4
    except Exception:
        # N geométrico no topo
        nx0, nx1 = cx - 7, cx + 7
        ny0, ny1 = n_top + 2, n_top + 18
        draw.line([(nx0, ny1), (nx0, ny0), (nx1, ny1), (nx1, ny0)], fill=(20, 20, 20, 255), width=3)
        arrow_top = ny1 + 4

    # Seta clássica apontando para CIMA (ponta no topo)
    arrow_bottom = bottom - 8
    shaft_half = max(4, box_w // 10)
    head_half = max(10, box_w // 3)
    head_h = max(14, int((arrow_bottom - arrow_top) * 0.42))
    tip_y = arrow_top
    head_base_y = arrow_top + head_h
    # sombra
    draw.polygon(
        [
            (cx + 1, tip_y + 1),
            (cx - head_half + 1, head_base_y + 1),
            (cx + head_half + 1, head_base_y + 1),
        ],
        fill=(0, 0, 0, 70),
    )
    # ponta vermelha (norte = cima)
    draw.polygon(
        [
            (cx, tip_y),
            (cx - head_half, head_base_y),
            (cx + head_half, head_base_y),
        ],
        fill=(200, 30, 30, 255),
    )
    # haste
    draw.rectangle(
        [cx - shaft_half, head_base_y - 2, cx + shaft_half, arrow_bottom],
        fill=(40, 40, 40, 255),
    )
    # base da haste
    draw.rectangle(
        [cx - shaft_half * 2, arrow_bottom - 3, cx + shaft_half * 2, arrow_bottom],
        fill=(40, 40, 40, 255),
    )


def _finalize_map_image(png_bytes: bytes, *, with_pin: bool = True) -> bytes:
    """Garante orientação norte-cima + pin opcional + indicador de norte."""
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    if with_pin:
        _draw_pin(layer, img.width // 2, img.height // 2)
    _draw_north_arrow(layer)
    out = Image.alpha_composite(img, layer).convert("RGB")
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _overlay_pin_center(png_bytes: bytes) -> bytes:
    """Compat: pin + norte (mapa já norte-cima nos provedores)."""
    return _finalize_map_image(png_bytes, with_pin=True)


def _google_static_api_key() -> str | None:
    try:
        from config.settings import get_settings

        key = getattr(get_settings(), "google_maps_static_api_key", None)
        if key and str(key).strip():
            return str(key).strip()
    except Exception:
        pass
    import os

    env = os.environ.get("GOOGLE_MAPS_STATIC_API_KEY") or os.environ.get("GOOGLE_MAPS_API_KEY")
    return env.strip() if env else None


def _is_plausible_image(data: bytes | None) -> bool:
    if not data or len(data) < 64:
        return False
    return data[:8] == b"\x89PNG\r\n\x1a\n" or data[:2] == b"\xff\xd8" or data[:2] == b"BM"


def _render_fallback_map(lat: float, lon: float, width: int, height: int) -> bytes:
    """Mapa esquemático local quando provedores remotos falham (ainda com marcador)."""
    img = Image.new("RGB", (width, height), color=(52, 78, 48))
    draw = ImageDraw.Draw(img)
    # grade
    step = max(40, width // 12)
    for x in range(0, width, step):
        draw.line([(x, 0), (x, height)], fill=(68, 98, 62), width=1)
    for y in range(0, height, step):
        draw.line([(0, y), (width, y)], fill=(68, 98, 62), width=1)
    # cruz central
    cx, cy = width // 2, height // 2
    draw.line([(cx - 40, cy), (cx + 40, cy)], fill=(200, 200, 180), width=1)
    draw.line([(cx, cy - 40), (cx, cy + 40)], fill=(200, 200, 180), width=1)
    draw.rectangle([8, height - 36, width - 8, height - 8], fill=(20, 30, 18))
    draw.text((16, height - 30), f"{lat:.6f}, {lon:.6f}", fill=(240, 240, 230))
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return _finalize_map_image(buf.getvalue(), with_pin=True)


def _fetch_google_satellite(lat: float, lon: float, width: int, height: int) -> bytes | None:
    key = _google_static_api_key()
    if not key:
        return None
    url = "https://maps.googleapis.com/maps/api/staticmap"
    # Sem heading → norte no topo (padrão cartográfico)
    params = {
        "center": f"{lat},{lon}",
        "zoom": "17",
        "size": f"{min(width, 640)}x{min(height, 640)}",
        "maptype": "satellite",
        "markers": f"color:red|{lat},{lon}",
        "key": key,
        "scale": "2",
    }
    try:
        resp = requests.get(url, params=params, timeout=_HTTP_TIMEOUT)
        if resp.status_code != 200 or not _is_plausible_image(resp.content):
            logger.warning("Google Static Maps falhou: HTTP %s", resp.status_code)
            return None
        return _finalize_map_image(resp.content, with_pin=False)
    except Exception as exc:
        logger.warning("Google Static Maps erro: %s", exc)
        return None


def _fetch_esri_satellite(
    lat: float,
    lon: float,
    width: int,
    height: int,
    radius_m: float,
) -> bytes | None:
    west, south, east, north = _bbox_around(lat, lon, radius_m)
    urls = (
        "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export",
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export",
    )
    # bbox WGS84 → imagem Web Mercator (norte no topo, métrica cartográfica)
    params = {
        "bbox": f"{west},{south},{east},{north}",
        "bboxSR": "4326",
        "imageSR": "3857",
        "size": f"{width},{height}",
        "format": "png",
        "f": "image",
        "transparent": "false",
    }
    for url in urls:
        try:
            resp = requests.get(url, params=params, timeout=_HTTP_TIMEOUT)
            if resp.status_code != 200 or not _is_plausible_image(resp.content):
                logger.warning("Esri World Imagery falhou: HTTP %s (%s)", resp.status_code, url)
                continue
            return _finalize_map_image(resp.content, with_pin=True)
        except Exception as exc:
            logger.warning("Esri World Imagery erro: %s", exc)
    return None


def build_location_map_png(
    latitude: float,
    longitude: float,
    *,
    cache_path: str | Path | None = None,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    radius_m: float = DEFAULT_RADIUS_M,
    force_refresh: bool = False,
    allow_fallback: bool = True,
) -> bytes | None:
    """
    Gera PNG de mapa satélite com marcador nas coordenadas.

    Se ``cache_path`` existir e for válido, reutiliza o arquivo (evita rede no re-export).
    Sem provedor remoto: gera mapa esquemático local (``allow_fallback``).
    """
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None

    cache = Path(cache_path) if cache_path else None
    if cache and not force_refresh and cache.is_file() and _is_plausible_image(cache.read_bytes()):
        try:
            return cache.read_bytes()
        except Exception:
            pass

    png = _fetch_google_satellite(lat, lon, width, height)
    source = "google" if png else None
    if not png:
        png = _fetch_esri_satellite(lat, lon, width, height, radius_m)
        source = "esri" if png else None
    if not png and allow_fallback:
        png = _render_fallback_map(lat, lon, width, height)
        source = "fallback"
    if not png:
        return None

    if cache:
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(png)
            meta = cache.with_suffix(".source.txt")
            meta.write_text(source or "unknown", encoding="utf-8")
        except Exception as exc:
            logger.debug("Não foi possível cachear mapa: %s", exc)

    return png


def resolve_location_coords(
    *,
    georef_asset: dict[str, Any] | None = None,
    content: dict[str, Any] | None = None,
) -> tuple[float, float] | None:
    """Extrai (lat, lon) do asset georref ou de ``content.georreferencia``."""
    for source in (georef_asset, (content or {}).get("georreferencia")):
        if not isinstance(source, dict):
            continue
        lat = source.get("latitude")
        lon = source.get("longitude")
        if lat is None or lon is None:
            continue
        try:
            return float(lat), float(lon)
        except (TypeError, ValueError):
            continue
    return None


def location_map_source(cache_path: str | Path | None) -> str | None:
    if not cache_path:
        return None
    meta = Path(cache_path).with_suffix(".source.txt")
    try:
        if meta.is_file():
            return meta.read_text(encoding="utf-8").strip() or None
    except Exception:
        return None
    return None


def frame_image_for_export(
    source: str | Path | bytes,
    *,
    width_px: int = FRAME_WIDTH_PX,
    height_px: int = FRAME_HEIGHT_PX,
    border_px: int = FRAME_BORDER_PX,
) -> bytes:
    """
    Redimensiona (letterbox) a imagem para o quadro fixo e desenha borda.
    Garante mesma proporção/tamanho entre foto georref e mapa satélite.
    """
    if isinstance(source, (bytes, bytearray)):
        img = Image.open(io.BytesIO(source))
    else:
        img = Image.open(source)
    try:
        from PIL import ImageOps

        transposed = ImageOps.exif_transpose(img)
        if transposed is not None:
            img = transposed
    except Exception:
        pass
    img = img.convert("RGB")

    inner_w = max(1, width_px - 2 * border_px)
    inner_h = max(1, height_px - 2 * border_px)
    canvas = Image.new("RGB", (width_px, height_px), FRAME_BORDER_RGB)
    inner = Image.new("RGB", (inner_w, inner_h), FRAME_PAD_RGB)

    src_w, src_h = img.size
    if src_w <= 0 or src_h <= 0:
        buf = io.BytesIO()
        canvas.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    scale = min(inner_w / src_w, inner_h / src_h)
    new_w = max(1, int(src_w * scale))
    new_h = max(1, int(src_h * scale))
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    ox = (inner_w - new_w) // 2
    oy = (inner_h - new_h) // 2
    inner.paste(resized, (ox, oy))
    canvas.paste(inner, (border_px, border_px))

    buf = io.BytesIO()
    canvas.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def georef_photo_caption(georef_asset: dict[str, Any] | None) -> str:
    """Legenda da foto sem repetir coordenadas já presentes no caption."""
    asset = georef_asset or {}
    cap = str(asset.get("caption") or "Imagem georreferenciada do objeto").strip()
    label = str(asset.get("label") or "").strip()
    if not label:
        return cap
    # Evita "… — -3.11… — -3.11… (WGS84)"
    if label in cap:
        return cap
    # Se caption já traz números lat/lon e label é só WGS84, não duplica
    if "(WGS84)" in cap and "(WGS84)" in label:
        return cap
    return f"{cap} — {label}"


def location_map_caption(
    latitude: float,
    longitude: float,
    label: str | None = None,
    *,
    source: str | None = None,
) -> str:
    coords = f"{latitude:.6f}, {longitude:.6f}"
    if source == "fallback":
        base = (
            f"Mapa de localização do objeto (esquemático — satélite indisponível; "
            f"norte no topo) — {coords}"
        )
    else:
        base = f"Mapa de localização do objeto (imagem de satélite; norte no topo) — {coords}"
    lab = str(label or "").strip()
    if not lab:
        return base
    if lab in base or coords in lab:
        return base
    if "(WGS84)" in lab and coords.split(",")[0].strip() in lab:
        return base
    return f"{base} · {lab}"
