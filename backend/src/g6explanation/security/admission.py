"""Product-aware API admission control before expensive game-analysis work."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from typing import Literal

from fastapi import Request

from g6explanation.game_analysis.contracts import GameAnalysisStartRequest
from g6explanation.game_imports.chess_com_live_games import extract_chess_com_live_game_id
from g6explanation.game_imports.contracts import GameAnalysisImportRequest
from g6explanation.game_imports.lichess_games import extract_lichess_game_id
from g6explanation.security.client_identity import ClientIdentity, client_identity
from g6explanation.security.rate_limiter import (
    FixedWindowRateLimiter,
    RateLimitRule,
    RateLimitStoreError,
    RedisFixedWindowRateLimiter,
)
from g6explanation.security.turnstile import (
    TurnstileVerificationError,
    TurnstileVerifier,
    turnstile_verifier_from_env,
)

AdmissionRoute = Literal["game_analysis_start", "import_start", "cached_lookup", "poll"]


@dataclass(frozen=True)
class AdmissionDenied(Exception):
    """Raised when a request is denied before expensive work begins."""

    status_code: int
    code: str
    detail: str
    retry_after_seconds: int | None = None


class DisabledApiProtection:
    """No-op protection for tests and local development."""

    def protect_game_analysis_start(
        self,
        *,
        request: Request,
        payload: GameAnalysisStartRequest,
    ) -> None:
        del request, payload

    def protect_import_start(
        self,
        *,
        request: Request,
        payload: GameAnalysisImportRequest,
    ) -> None:
        del request, payload

    def protect_cached_lookup(self, *, request: Request, external_game_id: str) -> None:
        del request, external_game_id

    def protect_poll(self, *, request: Request, analysis_id: str) -> None:
        del request, analysis_id


class ApiProtection:
    """Admission control for public API routes."""

    def __init__(
        self,
        *,
        limiter: FixedWindowRateLimiter,
        turnstile_verifier: TurnstileVerifier,
        require_turnstile: bool,
        allow_public_include_context: bool,
    ) -> None:
        self._limiter = limiter
        self._turnstile = turnstile_verifier
        self._require_turnstile = require_turnstile
        self._allow_public_include_context = allow_public_include_context

    @classmethod
    def from_env(cls) -> ApiProtection | DisabledApiProtection:
        if not _bool_env("G6EXPLANATION_API_PROTECTION_ENABLED", False):
            return DisabledApiProtection()
        redis_url = os.environ.get("G6EXPLANATION_REDIS_URL")
        if redis_url is None:
            raise RuntimeError(
                "G6EXPLANATION_API_PROTECTION_ENABLED=true requires G6EXPLANATION_REDIS_URL."
            )
        require_turnstile = _bool_env("G6EXPLANATION_REQUIRE_TURNSTILE", False) or bool(
            os.environ.get("G6EXPLANATION_TURNSTILE_SECRET_KEY")
        )
        return cls(
            limiter=RedisFixedWindowRateLimiter.from_url(
                redis_url,
                key_prefix=os.getenv(
                    "G6EXPLANATION_API_RATE_LIMIT_REDIS_PREFIX",
                    "g6:api_rate_limit",
                ),
            ),
            turnstile_verifier=turnstile_verifier_from_env(),
            require_turnstile=require_turnstile,
            allow_public_include_context=_bool_env(
                "G6EXPLANATION_ALLOW_PUBLIC_INCLUDE_CONTEXT",
                False,
            ),
        )

    def protect_game_analysis_start(
        self,
        *,
        request: Request,
        payload: GameAnalysisStartRequest,
    ) -> None:
        identity = client_identity(request)
        self._validate_public_payload(include_context=payload.include_context)
        self._verify_turnstile(
            token=getattr(payload, "turnstile_token", None),
            identity=identity,
            source_key=f"direct:{_short_hash(payload.pgn)}",
        )
        self._check(
            [
                _api_minute_rule(identity.ip),
                RateLimitRule(
                    f"ip:{identity.ip}:analysis_start",
                    _int_env("G6EXPLANATION_LIMIT_ANALYSIS_START_10M", 15),
                    10 * 60,
                ),
                RateLimitRule(
                    f"ip:{identity.ip}:analysis_start_day",
                    _int_env("G6EXPLANATION_LIMIT_ANALYSIS_START_DAY", 60),
                    24 * 60 * 60,
                ),
                RateLimitRule(
                    f"ip:{identity.ip}:pgn_start",
                    _int_env("G6EXPLANATION_LIMIT_PGN_START_10M", 10),
                    10 * 60,
                ),
                RateLimitRule(
                    "global:analysis_start",
                    _int_env("G6EXPLANATION_LIMIT_GLOBAL_ANALYSIS_START_MINUTE", 100),
                    60,
                ),
            ],
            route="game_analysis_start",
        )

    def protect_import_start(
        self,
        *,
        request: Request,
        payload: GameAnalysisImportRequest,
    ) -> None:
        identity = client_identity(request)
        self._validate_public_payload(include_context=payload.include_context)
        source_key = _source_key_for_import(payload)
        self._verify_turnstile(
            token=payload.turnstile_token,
            identity=identity,
            source_key=source_key,
        )
        rules = [
            _api_minute_rule(identity.ip),
            RateLimitRule(
                f"ip:{identity.ip}:analysis_start",
                _int_env("G6EXPLANATION_LIMIT_ANALYSIS_START_10M", 15),
                10 * 60,
            ),
            RateLimitRule(
                f"ip:{identity.ip}:analysis_start_day",
                _int_env("G6EXPLANATION_LIMIT_ANALYSIS_START_DAY", 60),
                24 * 60 * 60,
            ),
            RateLimitRule(
                "global:analysis_start",
                _int_env("G6EXPLANATION_LIMIT_GLOBAL_ANALYSIS_START_MINUTE", 100),
                60,
            ),
        ]
        if payload.source == "pgn":
            rules.extend(
                [
                    RateLimitRule(
                        f"ip:{identity.ip}:pgn_start",
                        _int_env("G6EXPLANATION_LIMIT_PGN_START_10M", 10),
                        10 * 60,
                    ),
                    RateLimitRule(
                        f"ip:{identity.ip}:pgn_start_day",
                        _int_env("G6EXPLANATION_LIMIT_PGN_START_DAY", 40),
                        24 * 60 * 60,
                    ),
                ]
            )
        elif payload.source == "chess_com_live_url":
            rules.extend(
                [
                    RateLimitRule(
                        f"ip:{identity.ip}:chesscom_start",
                        _int_env("G6EXPLANATION_LIMIT_CHESSCOM_START_HOUR", 25),
                        60 * 60,
                    ),
                    RateLimitRule(
                        f"ip:{identity.ip}:chesscom_start_day",
                        _int_env("G6EXPLANATION_LIMIT_CHESSCOM_START_DAY", 100),
                        24 * 60 * 60,
                    ),
                    RateLimitRule(
                        "global:chesscom_egress",
                        _int_env("G6EXPLANATION_LIMIT_GLOBAL_CHESSCOM_MINUTE", 150),
                        60,
                    ),
                ]
            )
        else:
            rules.extend(
                [
                    RateLimitRule(
                        f"ip:{identity.ip}:lichess_start",
                        _int_env("G6EXPLANATION_LIMIT_LICHESS_START_HOUR", 50),
                        60 * 60,
                    ),
                    RateLimitRule(
                        f"ip:{identity.ip}:lichess_start_day",
                        _int_env("G6EXPLANATION_LIMIT_LICHESS_START_DAY", 200),
                        24 * 60 * 60,
                    ),
                    RateLimitRule(
                        "global:lichess_egress",
                        _int_env("G6EXPLANATION_LIMIT_GLOBAL_LICHESS_MINUTE", 100),
                        60,
                    ),
                ]
            )
        self._check(rules, route="import_start")

    def protect_cached_lookup(self, *, request: Request, external_game_id: str) -> None:
        del external_game_id
        identity = client_identity(request)
        self._check(
            [
                _api_minute_rule(identity.ip),
                RateLimitRule(
                    f"ip:{identity.ip}:cached_lookup",
                    _int_env("G6EXPLANATION_LIMIT_CACHED_LOOKUP_MINUTE", 300),
                    60,
                ),
            ],
            route="cached_lookup",
            fail_open=True,
        )

    def protect_poll(self, *, request: Request, analysis_id: str) -> None:
        identity = client_identity(request)
        safe_analysis_id = _safe_key_part(analysis_id)
        self._check(
            [
                _api_minute_rule(identity.ip),
                RateLimitRule(
                    f"analysis:{safe_analysis_id}:poll:{identity.ip}",
                    _int_env("G6EXPLANATION_LIMIT_POLL_ANALYSIS_IP_MINUTE", 450),
                    60,
                ),
                RateLimitRule(
                    f"analysis:{safe_analysis_id}:poll:global",
                    _int_env("G6EXPLANATION_LIMIT_POLL_ANALYSIS_GLOBAL_MINUTE", 3000),
                    60,
                ),
            ],
            route="poll",
            fail_open=True,
        )

    def _validate_public_payload(self, *, include_context: bool) -> None:
        if include_context and not self._allow_public_include_context:
            raise AdmissionDenied(
                status_code=403,
                code="include_context_forbidden",
                detail="Public requests may not request full context payloads.",
            )

    def _verify_turnstile(
        self,
        *,
        token: str | None,
        identity: ClientIdentity,
        source_key: str,
    ) -> None:
        if not self._require_turnstile:
            return
        try:
            self._turnstile.verify(
                token=token,
                identity=identity,
                idempotency_key=_short_hash(source_key),
            )
        except TurnstileVerificationError as exc:
            raise AdmissionDenied(
                status_code=403,
                code="turnstile_failed",
                detail=str(exc),
            ) from exc

    def _check(
        self,
        rules: list[RateLimitRule],
        *,
        route: AdmissionRoute,
        fail_open: bool = False,
    ) -> None:
        try:
            decision = self._limiter.check_many(rules)
        except RateLimitStoreError as exc:
            if fail_open:
                return
            raise AdmissionDenied(
                status_code=503,
                code="admission_unavailable",
                detail="Admission control is temporarily unavailable.",
                retry_after_seconds=30,
            ) from exc
        if decision.allowed:
            return
        raise AdmissionDenied(
            status_code=429,
            code=f"{route}_rate_limited",
            detail="Too many requests. Try again after the cooldown.",
            retry_after_seconds=decision.retry_after_seconds,
        )


def _source_key_for_import(request: GameAnalysisImportRequest) -> str:
    if request.source == "chess_com_live_url":
        assert request.url is not None
        try:
            external_game_id = extract_chess_com_live_game_id(request.url)
        except ValueError:
            return f"chess_com_live:invalid:{_short_hash(request.url)}"
        return f"chess_com_live:{external_game_id}"
    if request.source == "lichess_game_url":
        assert request.url is not None
        try:
            external_game_id = extract_lichess_game_id(request.url)
        except ValueError:
            return f"lichess_game:invalid:{_short_hash(request.url)}"
        return f"lichess_game:{external_game_id}"
    assert request.pgn is not None
    return f"pgn:{_short_hash(_normalized_pgn(request.pgn))}"


def _api_minute_rule(ip: str) -> RateLimitRule:
    return RateLimitRule(
        f"ip:{ip}:api",
        _int_env("G6EXPLANATION_LIMIT_API_MINUTE", 1500),
        60,
    )


def _normalized_pgn(pgn: str) -> str:
    return "\n".join(line.rstrip() for line in pgn.strip().splitlines())


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def _safe_key_part(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value)[:128] or "unknown"


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value is None else int(value)


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
