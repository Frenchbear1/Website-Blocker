from __future__ import annotations

import ipaddress
import re

DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$",
    re.IGNORECASE,
)


def normalize_domain(value: str) -> str:
    text = value.strip().lower()
    for prefix in ("https://", "http://"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    text = text.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    if text.startswith("www."):
        text = text[4:]
    if ":" in text:
        host, _, port = text.rpartition(":")
        if port.isdigit():
            text = host
    try:
        ipaddress.ip_address(text)
        raise ValueError("Enter a domain name, not an IP address")
    except ValueError as exc:
        if str(exc) == "Enter a domain name, not an IP address":
            raise
    if not DOMAIN_RE.fullmatch(text):
        raise ValueError("Enter a valid domain, such as example.com")
    return text


def unique_domains(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        try:
            domain = normalize_domain(value)
        except ValueError:
            continue
        if domain not in seen:
            normalized.append(domain)
            seen.add(domain)
    return normalized

