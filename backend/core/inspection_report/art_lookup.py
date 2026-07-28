"""Consulta live de ART / portais CREA e link público SICAR (CAR).

Não há API oficial estável e unificada CREA/SICAR para ART.
Este módulo monta URLs de consulta por UF, opcionalmente sonda HTTP
e devolve metadados para preencher `art_url` / `art_protocolo`.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import requests

# Portais públicos conhecidos (consulta ART / serviços CREA por UF).
# URLs podem mudar — fallback nacional sempre disponível.
_CREA_PORTALS: dict[str, str] = {
    "AC": "https://www.crea-ac.org.br/",
    "AL": "https://www.crea-al.org.br/",
    "AM": "https://www.crea-am.org.br/",
    "AP": "https://www.crea-ap.org.br/",
    "BA": "https://www.crea-ba.org.br/",
    "CE": "https://www.crea-ce.org.br/",
    "DF": "https://www.crea-df.org.br/",
    "ES": "https://www.crea-es.org.br/",
    "GO": "https://www.crea-go.org.br/",
    "MA": "https://www.crea-ma.org.br/",
    "MG": "https://www.crea-mg.org.br/",
    "MS": "https://www.crea-ms.org.br/",
    "MT": "https://www.crea-mt.org.br/",
    "PA": "https://www.crea-pa.org.br/",
    "PB": "https://www.crea-pb.org.br/",
    "PE": "https://www.crea-pe.org.br/",
    "PI": "https://www.crea-pi.org.br/",
    "PR": "https://www.crea-pr.org.br/",
    "RJ": "https://www.crea-rj.org.br/",
    "RN": "https://www.crea-rn.org.br/",
    "RO": "https://www.crea-ro.org.br/",
    "RR": "https://www.crea-rr.org.br/",
    "RS": "https://www.crea-rs.org.br/",
    "SC": "https://www.crea-sc.org.br/",
    "SE": "https://www.crea-se.org.br/",
    "SP": "https://www.crea-sp.org.br/",
    "TO": "https://www.crea-to.org.br/",
}

SICAR_PUBLIC_URL = "https://www.car.gov.br/publico/imoveis/index"
CONFEA_ART_INFO = "https://www.confea.org.br/"

_UF_RE = re.compile(
    r"\b(AC|AL|AM|AP|BA|CE|DF|ES|GO|MA|MG|MS|MT|PA|PB|PE|PI|PR|RJ|RN|RO|RR|RS|SC|SE|SP|TO)\b",
    re.I,
)


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def extract_uf(*parts: str | None) -> str | None:
    for part in parts:
        if not part:
            continue
        m = _UF_RE.search(str(part))
        if m:
            return m.group(1).upper()
    return None


def build_crea_consultation_url(
    *,
    uf: str | None,
    art: str | None = None,
    protocolo: str | None = None,
) -> str:
    code = (uf or "").upper().strip()
    base = _CREA_PORTALS.get(code) or CONFEA_ART_INFO
    q: dict[str, str] = {}
    if protocolo:
        q["protocolo"] = str(protocolo).strip()[:80]
    if art:
        q["art"] = str(art).strip()[:80]
    if not q:
        return base
    sep = "&" if "?" in base else "?"
    return f"{base.rstrip('/')}{sep}{urlencode(q)}"


def probe_url(url: str, *, timeout: float = 4.0) -> dict[str, Any]:
    """Sonda HTTP leve (HEAD→GET). Nunca lança — só status operacional."""
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True)
        if resp.status_code >= 400:
            resp = requests.get(url, timeout=timeout, allow_redirects=True, stream=True)
            resp.close()
        ok = 200 <= resp.status_code < 400
        return {
            "reachable": ok,
            "http_status": resp.status_code,
            "final_url": str(resp.url),
        }
    except Exception as exc:
        return {"reachable": False, "http_status": None, "error": str(exc)[:200]}


def lookup_art(
    *,
    crea: str | None = None,
    art: str | None = None,
    art_protocolo: str | None = None,
    uf: str | None = None,
    probe: bool = True,
) -> dict[str, Any]:
    """Monta URL de consulta ART + opcionalmente sonda o portal e link SICAR."""
    resolved_uf = extract_uf(uf, crea, art, art_protocolo)
    art_url = build_crea_consultation_url(
        uf=resolved_uf,
        art=art,
        protocolo=art_protocolo,
    )
    live: dict[str, Any] | None = None
    if probe and art_url:
        live = probe_url(art_url)

    notes_parts = [
        "Consulta montada a partir do portal CREA/CONFEA (sem API oficial unificada).",
    ]
    if not resolved_uf:
        notes_parts.append("UF não detectada no CREA — usando portal CONFEA.")
    if live and not live.get("reachable"):
        notes_parts.append("Portal não respondeu a tempo; URL ainda pode ser usada manualmente.")

    return {
        "uf": resolved_uf,
        "art": (art or "").strip() or None,
        "art_protocolo": (art_protocolo or "").strip() or None,
        "art_url": art_url,
        "sicar_url": SICAR_PUBLIC_URL,
        "source": "crea_portal" if resolved_uf else "confea_fallback",
        "live": live,
        "consulted_at": _now_iso(),
        "notes": " ".join(notes_parts),
    }


def apply_lookup_to_party(party: dict[str, Any], lookup: dict[str, Any]) -> dict[str, Any]:
    """Mescla resultado do lookup no party (não apaga ART/protocolo existentes)."""
    out = dict(party or {})
    if lookup.get("art_url"):
        out["art_url"] = str(lookup["art_url"])[:400]
    if lookup.get("art_protocolo") and not out.get("art_protocolo"):
        out["art_protocolo"] = str(lookup["art_protocolo"])[:80]
    if lookup.get("art") and not out.get("art"):
        out["art"] = str(lookup["art"])[:80]
    return out
