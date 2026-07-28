"""Assinatura PAdES do PDF do laudo (ICP-Brasil via certificado A1 PKCS#12).

Feature-flag: LAUDO_PADES_ENABLED=true + LAUDO_PADES_P12_PATH (+ senha).
Sem certificado ou sem pyhanko instalado, o export permanece em L19 (imagem + hash).
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def pades_settings() -> dict[str, Any]:
    from config.settings import get_settings

    s = get_settings()
    return {
        "enabled": bool(getattr(s, "laudo_pades_enabled", False)),
        "p12_path": getattr(s, "laudo_pades_p12_path", None) or None,
        "p12_password": getattr(s, "laudo_pades_p12_password", "") or "",
    }


def pades_configured() -> bool:
    cfg = pades_settings()
    if not cfg["enabled"]:
        return False
    path = cfg["p12_path"]
    if not path:
        return False
    return Path(str(path)).is_file()


def pades_status() -> dict[str, Any]:
    cfg = pades_settings()
    try:
        import pyhanko  # noqa: F401

        lib_ok = True
    except ImportError:
        lib_ok = False
    return {
        "enabled": cfg["enabled"],
        "library_installed": lib_ok,
        "certificate_configured": bool(cfg["p12_path"] and Path(str(cfg["p12_path"])).is_file()),
        "ready": pades_configured() and lib_ok,
        "method_when_ready": "pades",
    }


def sign_pdf_pades(pdf_bytes: bytes) -> tuple[bytes, dict[str, Any]]:
    """Assina PDF em PAdES-B com PKCS#12. Levanta RuntimeError se indisponível."""
    if not pdf_bytes:
        raise ValueError("PDF vazio")
    status = pades_status()
    if not status["ready"]:
        raise RuntimeError(
            "PAdES indisponível — defina LAUDO_PADES_ENABLED, LAUDO_PADES_P12_PATH "
            "e instale pyhanko (pip install pyhanko)"
        )

    cfg = pades_settings()
    p12_path = Path(str(cfg["p12_path"]))
    password = str(cfg["p12_password"] or "").encode("utf-8")

    try:
        from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
        from pyhanko.sign import signers
        from pyhanko.sign.fields import SigFieldSpec
        from io import BytesIO
    except ImportError as exc:
        raise RuntimeError("pyhanko não instalado") from exc

    signer = signers.SimpleSigner.load_pkcs12(
        str(p12_path),
        passphrase=password or None,
    )
    if signer is None:
        raise RuntimeError("Falha ao carregar PKCS#12 — verifique caminho e senha")

    in_buf = BytesIO(pdf_bytes)
    writer = IncrementalPdfFileWriter(in_buf)
    out_buf = BytesIO()
    meta: dict[str, Any] = {
        "method": "pades",
        "signed_at": _now_iso(),
        "profile": "PAdES-B",
        "library": "pyhanko",
    }
    try:
        subject = getattr(getattr(signer, "signing_cert", None), "subject", None)
        if subject is not None:
            meta["signer_subject"] = str(subject)[:300]
    except Exception:
        pass

    pdf_signer = signers.PdfSigner(
        signers.PdfSignatureMetadata(
            field_name="AssinaturaLaudo",
            reason="Laudo técnico de vistoria — IA Server Santos",
            location="Brasil",
        ),
        signer=signer,
        new_field_spec=SigFieldSpec(sig_field_name="AssinaturaLaudo", on_page=0, box=(50, 50, 250, 100)),
    )
    pdf_signer.sign_pdf(writer, output=out_buf)
    signed = out_buf.getvalue()
    if not signed.startswith(b"%PDF"):
        raise RuntimeError("Saída PAdES inválida")
    meta["signed_bytes"] = len(signed)
    return signed, meta
