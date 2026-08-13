"""Client identity extraction for Cloudflare-fronted HTTP requests."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

from fastapi import Request


@dataclass(frozen=True)
class ClientIdentity:
    """Normalized request identity used for rate-limit keys and observability."""

    ip: str
    country: str | None
    user_agent_hash: str
    cf_ray: str | None
    via_cloudflare: bool


def client_identity(request: Request) -> ClientIdentity:
    """Extract a stable, privacy-light client identity from request headers."""

    headers = request.headers
    trust_proxy_headers = _bool_env("G6EXPLANATION_TRUST_PROXY_HEADERS", False)
    cf_ip = _blank_to_none(headers.get("cf-connecting-ip")) if trust_proxy_headers else None
    forwarded_for = (
        _first_forwarded_for(headers.get("x-forwarded-for")) if trust_proxy_headers else None
    )
    client_host = request.client.host if request.client is not None else None
    ip = cf_ip or forwarded_for or client_host or "unknown"
    user_agent = headers.get("user-agent", "")
    cf_ray = _blank_to_none(headers.get("cf-ray"))
    return ClientIdentity(
        ip=ip,
        country=_blank_to_none(headers.get("cf-ipcountry")),
        user_agent_hash=hashlib.sha256(user_agent.encode("utf-8")).hexdigest()[:16],
        cf_ray=cf_ray,
        via_cloudflare=cf_ip is not None or cf_ray is not None,
    )


def _first_forwarded_for(value: str | None) -> str | None:
    if value is None:
        return None
    first = value.split(",", 1)[0].strip()
    return first or None


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
