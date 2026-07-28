"""Validação CNPJ/CREA/ART e checklist pré-export (L9)."""

from __future__ import annotations

import re
from typing import Any


def only_digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def validate_cnpj(value: str | None) -> tuple[bool, str]:
    """Valida dígitos verificadores do CNPJ. Vazio = ok (campo opcional)."""
    raw = (value or "").strip()
    if not raw:
        return True, ""
    digits = only_digits(raw)
    if len(digits) != 14:
        return False, "CNPJ deve ter 14 dígitos"
    if digits == digits[0] * 14:
        return False, "CNPJ inválido"
    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    def _digit(base: str, weights: list[int]) -> str:
        total = sum(int(d) * w for d, w in zip(base, weights))
        rest = total % 11
        return "0" if rest < 2 else str(11 - rest)

    d1 = _digit(digits[:12], weights1)
    d2 = _digit(digits[:12] + d1, weights2)
    if digits[-2:] != d1 + d2:
        return False, "CNPJ com dígitos verificadores inválidos"
    return True, ""


def validate_crea(value: str | None) -> tuple[bool, str]:
    raw = (value or "").strip()
    if not raw:
        return True, ""
    if len(raw) < 4:
        return False, "CREA/CAU muito curto"
    if not re.search(r"\d", raw):
        return False, "CREA/CAU deve conter número de registro"
    return True, ""


def validate_art(value: str | None) -> tuple[bool, str]:
    raw = (value or "").strip()
    if not raw:
        return True, ""
    if len(raw) < 3:
        return False, "ART muito curta"
    return True, ""


def build_export_checklist(content: dict[str, Any] | None, *, assets: list[Any] | None = None) -> dict[str, Any]:
    """Checklist pré-export «oficial» — itens + bloqueantes."""
    content = content if isinstance(content, dict) else {}
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    solicitante = content.get("solicitante") or {}
    if isinstance(solicitante, dict):
        ok, msg = validate_cnpj(solicitante.get("cnpj"))
        if not ok:
            issues.append({"code": "cnpj", "message": msg})
        if not (solicitante.get("empresa") or "").strip():
            warnings.append({"code": "solicitante_empresa", "message": "Solicitante sem empresa"})
    else:
        warnings.append({"code": "solicitante", "message": "Solicitante não informado"})

    rts = content.get("responsaveis_tecnicos") or []
    if not rts:
        issues.append({"code": "rt_missing", "message": "Informe ao menos um responsável técnico"})
    else:
        for i, rt in enumerate(rts):
            if not isinstance(rt, dict):
                continue
            if not (rt.get("nome") or "").strip():
                issues.append({"code": f"rt_{i}_nome", "message": f"RT #{i + 1} sem nome"})
            ok, msg = validate_crea(rt.get("crea"))
            if not ok:
                issues.append({"code": f"rt_{i}_crea", "message": f"RT #{i + 1}: {msg}"})
            ok, msg = validate_art(rt.get("art"))
            if not ok:
                warnings.append({"code": f"rt_{i}_art", "message": f"RT #{i + 1}: {msg}"})
            elif not (rt.get("art") or "").strip() and not (rt.get("art_asset_id") or "").strip():
                warnings.append(
                    {
                        "code": f"rt_{i}_art_empty",
                        "message": f"RT #{i + 1} sem ART textual nem anexo PDF (L18)",
                    }
                )
            elif (rt.get("art_asset_id") or "").strip():
                # rastreável via anexo — ok
                pass

    # L19 / PAdES — evidência de assinatura
    sig = content.get("signature_evidence") if isinstance(content.get("signature_evidence"), dict) else {}
    method = str(sig.get("method") or "image_hash").lower()
    if method == "pades" and sig.get("pdf_sha256"):
        pass  # assinado digitalmente
    elif not sig.get("pdf_sha256"):
        warnings.append(
            {
                "code": "signature_icp",
                "message": "Assinatura tipográfica/imagem — ICP-Brasil PAdES não aplicado (L19 evidência)",
            }
        )
    else:
        warnings.append(
            {
                "code": "signature_icp",
                "message": "PDF com hash SHA-256 (L19) — PAdES/ICP-Brasil ainda não aplicado neste export",
            }
        )

    fotos = content.get("photographic_report") or []
    asset_images = [a for a in (assets or []) if getattr(a, "kind", None) == "image" or (isinstance(a, dict) and a.get("kind") == "image")]
    if not fotos and not asset_images:
        warnings.append({"code": "photos", "message": "Sem relatório fotográfico"})

    geo = content.get("georreferencia") or {}
    if not geo.get("has_gps") and geo.get("latitude") is None:
        warnings.append({"code": "georef", "message": "Sem imagem georreferenciada / GPS"})

    if not (content.get("titulo") or "").strip():
        warnings.append({"code": "titulo", "message": "Título do laudo vazio"})

    chapters = content.get("chapters") or []
    if not chapters:
        issues.append({"code": "chapters", "message": "Laudo sem capítulos — gere ou edite o conteúdo"})

    blocking = len(issues) > 0
    return {
        "ok": not blocking,
        "blocking": blocking,
        "issues": issues,
        "warnings": warnings,
        "ready_for_official_export": not blocking and len(warnings) == 0,
    }
