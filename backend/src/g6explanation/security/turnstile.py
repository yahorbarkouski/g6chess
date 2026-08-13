"""Cloudflare Turnstile server-side validation."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Protocol, cast

from g6explanation.security.client_identity import ClientIdentity

TURNSTILE_SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
DEFAULT_TURNSTILE_TIMEOUT_SECONDS = 5.0


class TurnstileVerificationError(ValueError):
    """Raised when a public request fails Turnstile validation."""


class TurnstileVerifier(Protocol):
    """Validation boundary for anonymous expensive starts."""

    def verify(
        self,
        *,
        token: str | None,
        identity: ClientIdentity,
        idempotency_key: str | None = None,
    ) -> None:
        """Validate a Turnstile token or raise."""
        ...


class DisabledTurnstileVerifier:
    """No-op verifier for local development and deterministic tests."""

    def verify(
        self,
        *,
        token: str | None,
        identity: ClientIdentity,
        idempotency_key: str | None = None,
    ) -> None:
        del token, identity, idempotency_key


@dataclass(frozen=True)
class CloudflareTurnstileVerifier:
    """Synchronous Cloudflare Siteverify client."""

    secret_key: str
    timeout_seconds: float = DEFAULT_TURNSTILE_TIMEOUT_SECONDS

    @classmethod
    def from_env(cls) -> CloudflareTurnstileVerifier:
        secret_key = os.environ.get("G6EXPLANATION_TURNSTILE_SECRET_KEY")
        if not secret_key:
            raise RuntimeError("G6EXPLANATION_TURNSTILE_SECRET_KEY must be set.")
        return cls(
            secret_key=secret_key,
            timeout_seconds=_float_env(
                "G6EXPLANATION_TURNSTILE_TIMEOUT_SECONDS",
                DEFAULT_TURNSTILE_TIMEOUT_SECONDS,
            ),
        )

    def verify(
        self,
        *,
        token: str | None,
        identity: ClientIdentity,
        idempotency_key: str | None = None,
    ) -> None:
        if token is None or not token.strip():
            raise TurnstileVerificationError("Turnstile token is required.")
        fields = {
            "secret": self.secret_key,
            "response": token.strip(),
            "remoteip": identity.ip,
        }
        if idempotency_key is not None:
            fields["idempotency_key"] = idempotency_key
        body = urllib.parse.urlencode(fields).encode("utf-8")
        request = urllib.request.Request(
            TURNSTILE_SITEVERIFY_URL,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw_payload: object = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise TurnstileVerificationError(
                "Turnstile validation is temporarily unavailable."
            ) from exc
        if not isinstance(raw_payload, dict):
            raise TurnstileVerificationError("Turnstile validation failed.")
        payload = cast(dict[str, object], raw_payload)
        if payload.get("success") is not True:
            raise TurnstileVerificationError("Turnstile validation failed.")


def turnstile_verifier_from_env() -> TurnstileVerifier:
    if os.environ.get("G6EXPLANATION_TURNSTILE_SECRET_KEY"):
        return CloudflareTurnstileVerifier.from_env()
    if _bool_env("G6EXPLANATION_REQUIRE_TURNSTILE", False):
        raise RuntimeError(
            "G6EXPLANATION_REQUIRE_TURNSTILE=true requires G6EXPLANATION_TURNSTILE_SECRET_KEY."
        )
    return DisabledTurnstileVerifier()


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    return default if value is None else float(value)


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
