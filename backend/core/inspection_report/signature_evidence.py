"""L19 — Evidência de assinatura (imagem de firma + hash SHA-256 do PDF)."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def get_signature_evidence(content: dict[str, Any] | None) -> dict[str, Any]:
    raw = (content or {}).get("signature_evidence")
    if not isinstance(raw, dict):
        return {
            "method": "image_hash",
            "pdf_sha256": None,
            "pdf_signed_at": None,
            "rt_signature_asset_ids": {},
            "notes": None,
            "pades": None,
        }
    ids = raw.get("rt_signature_asset_ids") or {}
    if not isinstance(ids, dict):
        ids = {}
    method = str(raw.get("method") or "image_hash").strip().lower()
    if method not in ("image_hash", "pades"):
        method = "image_hash"
    pades = raw.get("pades") if isinstance(raw.get("pades"), dict) else None
    return {
        "method": method,
        "pdf_sha256": str(raw.get("pdf_sha256") or "") or None,
        "pdf_signed_at": str(raw.get("pdf_signed_at") or "") or None,
        "rt_signature_asset_ids": {str(k): str(v) for k, v in ids.items() if k and v},
        "notes": str(raw.get("notes") or "") or None,
        "pades": pades,
    }


def merge_signature_evidence(content: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    current = get_signature_evidence(content)
    data = dict(patch or {})
    if "rt_signature_asset_ids" in data and isinstance(data["rt_signature_asset_ids"], dict):
        current["rt_signature_asset_ids"] = {
            str(k): str(v) for k, v in data["rt_signature_asset_ids"].items() if k and v
        }
    if "notes" in data:
        current["notes"] = str(data.get("notes") or "").strip()[:500] or None
    if "pdf_sha256" in data:
        current["pdf_sha256"] = str(data.get("pdf_sha256") or "") or None
    if "pdf_signed_at" in data:
        current["pdf_signed_at"] = str(data.get("pdf_signed_at") or "") or None
    if "method" in data:
        method = str(data.get("method") or "image_hash").strip().lower()
        current["method"] = method if method in ("image_hash", "pades") else "image_hash"
    if "pades" in data:
        current["pades"] = data["pades"] if isinstance(data.get("pades"), dict) else None
    out = dict(content or {})
    out["signature_evidence"] = current
    return out


def record_pdf_hash(
    content: dict[str, Any],
    pdf_bytes: bytes,
    *,
    method: str = "image_hash",
    pades_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    patch: dict[str, Any] = {
        "pdf_sha256": digest,
        "pdf_signed_at": _now_iso(),
        "method": method if method in ("image_hash", "pades") else "image_hash",
    }
    if pades_meta:
        patch["pades"] = {
            k: v for k, v in pades_meta.items() if k != "signed_bytes" and v is not None
        }
        patch["notes"] = (
            f"PAdES ({pades_meta.get('profile') or 'B'}) · "
            f"{pades_meta.get('signer_subject') or 'cert A1'}"
        )[:500]
    return merge_signature_evidence(content, patch)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def signature_asset_for_party(content: dict[str, Any] | None, party_id: str | None) -> str | None:
    if not party_id:
        return None
    ev = get_signature_evidence(content)
    return (ev.get("rt_signature_asset_ids") or {}).get(str(party_id))
