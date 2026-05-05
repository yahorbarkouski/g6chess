"""Fixed-window Redis rate limiting for public API admission control."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, cast

from redis import Redis
from redis.exceptions import RedisError


class RateLimitStoreError(RuntimeError):
    """Raised when the shared limiter store is unavailable."""


@dataclass(frozen=True)
class RateLimitRule:
    """One fixed-window rate-limit bucket."""

    key: str
    limit: int
    window_seconds: int

    def __post_init__(self) -> None:
        if self.limit <= 0:
            raise ValueError("Rate limit must be positive.")
        if self.window_seconds <= 0:
            raise ValueError("Rate-limit window must be positive.")


@dataclass(frozen=True)
class RateLimitDecision:
    """Result of checking one or more buckets."""

    allowed: bool
    retry_after_seconds: int
    rule_key: str | None = None


class FixedWindowRateLimiter(Protocol):
    """Shared admission-control limiter."""

    def check_many(
        self,
        rules: list[RateLimitRule],
        *,
        now: float | None = None,
    ) -> RateLimitDecision:
        """Atomically allow or deny the full rule set."""
        ...


class RedisFixedWindowRateLimiter:
    """Atomic fixed-window limiter backed by Redis."""

    _SCRIPT = """
local allowed = 1
local retry_after = 0
local denied_key = ""
local count = #KEYS
for i = 1, count do
  local current = redis.call("GET", KEYS[i])
  local limit = tonumber(ARGV[i])
  if current and tonumber(current) >= limit then
    allowed = 0
    local rule_retry = tonumber(ARGV[count + i])
    if rule_retry > retry_after then
      retry_after = rule_retry
      denied_key = KEYS[i]
    end
  end
end
if allowed == 1 then
  for i = 1, count do
    local next_count = redis.call("INCR", KEYS[i])
    if next_count == 1 then
      redis.call("EXPIRE", KEYS[i], tonumber(ARGV[count + i]))
    end
  end
end
return {allowed, retry_after, denied_key}
"""

    def __init__(
        self,
        redis_client: Any,
        *,
        key_prefix: str = "g6:api_rate_limit",
    ) -> None:
        self._redis: Any = redis_client
        self._key_prefix = key_prefix

    @classmethod
    def from_url(
        cls,
        redis_url: str,
        *,
        key_prefix: str = "g6:api_rate_limit",
    ) -> RedisFixedWindowRateLimiter:
        return cls(
            cast(
                Callable[[str], Any],
                Redis.from_url,  # pyright: ignore[reportUnknownMemberType]
            )(redis_url),
            key_prefix=key_prefix,
        )

    def check_many(
        self,
        rules: list[RateLimitRule],
        *,
        now: float | None = None,
    ) -> RateLimitDecision:
        if not rules:
            return RateLimitDecision(allowed=True, retry_after_seconds=0)
        checked_at = time.time() if now is None else now
        keys = [_window_key(self._key_prefix, rule, checked_at) for rule in rules]
        retry_after_values = [_retry_after(rule, checked_at) for rule in rules]
        args = [str(rule.limit) for rule in rules] + [str(value) for value in retry_after_values]
        try:
            raw = self._redis.eval(self._SCRIPT, len(keys), *keys, *args)
        except RedisError as exc:
            raise RateLimitStoreError(f"Rate limiter Redis is unavailable: {exc}") from exc
        if not isinstance(raw, list):
            raise RateLimitStoreError("Rate limiter Redis returned an invalid response.")
        response = cast(list[object], raw)
        if len(response) < 2:
            raise RateLimitStoreError("Rate limiter Redis returned an invalid response.")
        allowed = _int_response_item(response[0]) == 1
        retry_after = max(1, _int_response_item(response[1])) if not allowed else 0
        denied_key = (
            response[2].decode("utf-8")
            if len(response) > 2 and isinstance(response[2], bytes)
            else None
        )
        rule_key = _rule_key_from_window_key(denied_key) if denied_key else None
        return RateLimitDecision(
            allowed=allowed,
            retry_after_seconds=retry_after,
            rule_key=rule_key,
        )


class InMemoryFixedWindowRateLimiter:
    """Deterministic fixed-window limiter for tests."""

    def __init__(self, *, key_prefix: str = "g6:api_rate_limit") -> None:
        self._key_prefix = key_prefix
        self._items: dict[str, tuple[int, float]] = {}

    def check_many(
        self,
        rules: list[RateLimitRule],
        *,
        now: float | None = None,
    ) -> RateLimitDecision:
        checked_at = time.time() if now is None else now
        self._expire(checked_at)
        denied: tuple[RateLimitRule, int] | None = None
        for rule in rules:
            key = _window_key(self._key_prefix, rule, checked_at)
            current = self._items.get(key, (0, 0.0))[0]
            if current >= rule.limit:
                retry_after = _retry_after(rule, checked_at)
                if denied is None or retry_after > denied[1]:
                    denied = (rule, retry_after)
        if denied is not None:
            return RateLimitDecision(
                allowed=False,
                retry_after_seconds=denied[1],
                rule_key=denied[0].key,
            )
        for rule in rules:
            key = _window_key(self._key_prefix, rule, checked_at)
            current, _expires_at = self._items.get(key, (0, 0.0))
            self._items[key] = (current + 1, checked_at + _retry_after(rule, checked_at))
        return RateLimitDecision(allowed=True, retry_after_seconds=0)

    def _expire(self, now: float) -> None:
        expired = [key for key, (_count, expires_at) in self._items.items() if expires_at <= now]
        for key in expired:
            del self._items[key]


def _window_key(prefix: str, rule: RateLimitRule, now: float) -> str:
    bucket = math.floor(now / rule.window_seconds)
    return f"{prefix}:{rule.key}:{bucket}"


def _retry_after(rule: RateLimitRule, now: float) -> int:
    elapsed = now % rule.window_seconds
    return max(1, math.ceil(rule.window_seconds - elapsed))


def _rule_key_from_window_key(window_key: str | None) -> str | None:
    if window_key is None:
        return None
    parts = window_key.split(":")
    if len(parts) < 2:
        return window_key
    return ":".join(parts[3:-1]) or window_key


def _int_response_item(value: object) -> int:
    if isinstance(value, bytes):
        return int(value.decode("utf-8"))
    if isinstance(value, (int, str)):
        return int(value)
    raise RateLimitStoreError("Rate limiter Redis returned an invalid numeric response.")
