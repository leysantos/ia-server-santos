"""Validação de URLs — proteção SSRF básica."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeURLError(ValueError):
    pass


_BLOCKED_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1"})


def validate_public_http_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise UnsafeURLError("Apenas URLs http/https são permitidas")
    if not parsed.netloc:
        raise UnsafeURLError("URL inválida")

    host = parsed.hostname
    if not host:
        raise UnsafeURLError("Host ausente na URL")
    if host.lower() in _BLOCKED_HOSTS:
        raise UnsafeURLError(f"Host bloqueado: {host}")

    try:
        addr_infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Não foi possível resolver o host: {host}") from exc

    for info in addr_infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise UnsafeURLError(f"URL aponta para endereço privado/reservado: {ip_str}")

    return url.strip()
