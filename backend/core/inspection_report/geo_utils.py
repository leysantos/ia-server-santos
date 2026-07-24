"""Extração de coordenadas GPS (EXIF) de imagens georreferenciadas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _ratio_to_float(value: Any) -> float:
    try:
        if hasattr(value, "numerator") and hasattr(value, "denominator"):
            den = float(value.denominator) or 1.0
            return float(value.numerator) / den
        if isinstance(value, tuple) and len(value) == 2:
            den = float(value[1]) or 1.0
            return float(value[0]) / den
        return float(value)
    except Exception:
        return 0.0


def _dms_to_decimal(dms: Any, ref: str | None) -> float | None:
    try:
        if not dms or len(dms) < 3:
            return None
        deg = _ratio_to_float(dms[0])
        minutes = _ratio_to_float(dms[1])
        seconds = _ratio_to_float(dms[2])
        decimal = deg + (minutes / 60.0) + (seconds / 3600.0)
        if ref and str(ref).upper() in {"S", "W"}:
            decimal = -abs(decimal)
        return decimal
    except Exception:
        return None


def extract_gps_from_image(path: str | Path) -> dict[str, Any] | None:
    """
    Lê GPSInfo do EXIF (JPEG/TIFF). Retorna dict com lat/lon ou None.
    """
    try:
        from PIL import Image
        from PIL.ExifTags import GPSTAGS, TAGS
    except Exception:
        return None

    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return None
            gps_ifd = None
            # Pillow 10+: get_ifd
            try:
                gps_ifd = exif.get_ifd(0x8825)
            except Exception:
                gps_ifd = None
            if not gps_ifd:
                # fallback via TAGS
                for tag_id, value in exif.items():
                    if TAGS.get(tag_id) == "GPSInfo" and isinstance(value, dict):
                        gps_ifd = value
                        break
            if not gps_ifd:
                return None

            gps: dict[str, Any] = {}
            for key, val in gps_ifd.items():
                name = GPSTAGS.get(key, key)
                gps[name] = val

            lat = _dms_to_decimal(gps.get("GPSLatitude"), gps.get("GPSLatitudeRef"))
            lon = _dms_to_decimal(gps.get("GPSLongitude"), gps.get("GPSLongitudeRef"))
            if lat is None or lon is None:
                return None
            return {
                "latitude": round(float(lat), 7),
                "longitude": round(float(lon), 7),
                "label": f"{lat:.6f}, {lon:.6f} (WGS84)",
            }
    except Exception:
        return None


def encode_gps_payload(gps: dict[str, Any] | None, *, note: str = "") -> str:
    payload = dict(gps or {})
    if note:
        payload["note"] = note
    return json.dumps(payload, ensure_ascii=False)


def decode_gps_payload(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and ("latitude" in data or "label" in data):
            return data
    except Exception:
        pass
    return None
