"""HTTP abuse-protection primitives for public API entrypoints."""

from g6explanation.security.admission import (
    AdmissionDenied,
    ApiProtection,
    DisabledApiProtection,
)
from g6explanation.security.client_identity import ClientIdentity, client_identity
from g6explanation.security.rate_limiter import (
    InMemoryFixedWindowRateLimiter,
    RateLimitDecision,
    RateLimitRule,
    RateLimitStoreError,
    RedisFixedWindowRateLimiter,
)
from g6explanation.security.turnstile import (
    CloudflareTurnstileVerifier,
    DisabledTurnstileVerifier,
    TurnstileVerificationError,
)

__all__ = [
    "AdmissionDenied",
    "ApiProtection",
    "ClientIdentity",
    "CloudflareTurnstileVerifier",
    "DisabledApiProtection",
    "DisabledTurnstileVerifier",
    "InMemoryFixedWindowRateLimiter",
    "RateLimitDecision",
    "RateLimitRule",
    "RateLimitStoreError",
    "RedisFixedWindowRateLimiter",
    "TurnstileVerificationError",
    "client_identity",
]
