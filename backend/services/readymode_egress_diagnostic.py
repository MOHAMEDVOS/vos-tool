"""Temporary, opt-in diagnostics for outbound networking to ReadyMode."""

import ipaddress
import logging
import socket

import requests

logger = logging.getLogger(__name__)

READYMODE_HOST = "resva.readymode.com"
IP_ECHO_ENDPOINTS = {
    "IPv4": "https://ipv4.icanhazip.com",
    "IPv6": "https://ipv6.icanhazip.com",
}


def _resolve_addresses(host: str, family: int) -> list[str]:
    try:
        results = socket.getaddrinfo(host, 443, family, socket.SOCK_STREAM)
    except OSError as exc:
        logger.info(
            "ReadyMode egress diagnostic DNS family=%s unavailable error=%s",
            "IPv4" if family == socket.AF_INET else "IPv6",
            type(exc).__name__,
        )
        return []

    return sorted({result[4][0] for result in results})


def _read_public_ip(endpoint: str, version: int) -> str:
    with requests.Session() as session:
        session.trust_env = False
        with session.get(endpoint, timeout=(3, 5)) as response:
            response.raise_for_status()
            address = ipaddress.ip_address(response.text.strip())
            if address.version != version:
                raise ValueError("echo service returned an unexpected address family")
            return str(address)


def run_readymode_egress_diagnostic() -> None:
    """Log ReadyMode DNS answers and the service's public v4/v6 egress addresses."""
    ipv4_addresses = _resolve_addresses(READYMODE_HOST, socket.AF_INET)
    ipv6_addresses = _resolve_addresses(READYMODE_HOST, socket.AF_INET6)
    logger.info(
        "ReadyMode egress diagnostic DNS host=%s A=%s AAAA=%s",
        READYMODE_HOST,
        ipv4_addresses or "unavailable",
        ipv6_addresses or "unavailable",
    )

    for label, endpoint, version in (
        ("IPv4", IP_ECHO_ENDPOINTS["IPv4"], 4),
        ("IPv6", IP_ECHO_ENDPOINTS["IPv6"], 6),
    ):
        try:
            address = _read_public_ip(endpoint, version)
        except (requests.RequestException, ValueError) as exc:
            logger.info(
                "ReadyMode egress diagnostic public_%s=unavailable error=%s",
                label.lower(),
                type(exc).__name__,
            )
            continue
        logger.info("ReadyMode egress diagnostic public_%s=%s", label.lower(), address)
