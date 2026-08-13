"""Admission-control policy tests."""

from __future__ import annotations

import pytest
from fastapi import Request

from g6explanation.context_engine.contracts import PlayerLevel
from g6explanation.game_analysis.contracts import GameAnalysisStartRequest
from g6explanation.game_imports.contracts import (
    ChessComLiveImportRequest,
    LichessGameImportRequest,
    PgnImportRequest,
)
from g6explanation.security import (
    ApiProtection,
    DisabledTurnstileVerifier,
    RateLimitDecision,
    RateLimitRule,
)

CLIENT_IP = "203.0.113.17"
TINY_PGN = '[Event "Tiny"]\n\n1. e4 *'
LIMIT_ENV_VARS = (
    "G6EXPLANATION_LIMIT_API_MINUTE",
    "G6EXPLANATION_LIMIT_ANALYSIS_START_10M",
    "G6EXPLANATION_LIMIT_ANALYSIS_START_DAY",
    "G6EXPLANATION_LIMIT_PGN_START_10M",
    "G6EXPLANATION_LIMIT_GLOBAL_ANALYSIS_START_MINUTE",
    "G6EXPLANATION_LIMIT_PGN_START_DAY",
    "G6EXPLANATION_LIMIT_CHESSCOM_START_HOUR",
    "G6EXPLANATION_LIMIT_CHESSCOM_START_DAY",
    "G6EXPLANATION_LIMIT_GLOBAL_CHESSCOM_MINUTE",
    "G6EXPLANATION_LIMIT_LICHESS_START_HOUR",
    "G6EXPLANATION_LIMIT_LICHESS_START_DAY",
    "G6EXPLANATION_LIMIT_GLOBAL_LICHESS_MINUTE",
    "G6EXPLANATION_LIMIT_CACHED_LOOKUP_MINUTE",
    "G6EXPLANATION_LIMIT_POLL_ANALYSIS_IP_MINUTE",
    "G6EXPLANATION_LIMIT_POLL_ANALYSIS_GLOBAL_MINUTE",
)


@pytest.fixture(autouse=True)
def clear_limit_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in LIMIT_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


class RecordingRateLimiter:
    def __init__(self) -> None:
        self.calls: list[list[RateLimitRule]] = []

    def check_many(
        self,
        rules: list[RateLimitRule],
        *,
        now: float | None = None,
    ) -> RateLimitDecision:
        del now
        self.calls.append(rules)
        return RateLimitDecision(allowed=True, retry_after_seconds=0)

    def pop_call(self) -> list[RateLimitRule]:
        return self.calls.pop()


def test_api_protection_default_rate_limits_are_five_times_larger() -> None:
    limiter = RecordingRateLimiter()
    protection = ApiProtection(
        limiter=limiter,
        turnstile_verifier=DisabledTurnstileVerifier(),
        require_turnstile=False,
        allow_public_include_context=True,
    )

    protection.protect_game_analysis_start(
        request=_request(),
        payload=GameAnalysisStartRequest(
            pgn=TINY_PGN,
            player_level=PlayerLevel.rating(1500),
        ),
    )
    assert _rule_contracts(limiter.pop_call()) == {
        f"ip:{CLIENT_IP}:api": (1500, 60),
        f"ip:{CLIENT_IP}:analysis_start": (15, 600),
        f"ip:{CLIENT_IP}:analysis_start_day": (60, 86400),
        f"ip:{CLIENT_IP}:pgn_start": (10, 600),
        "global:analysis_start": (100, 60),
    }

    protection.protect_import_start(
        request=_request(),
        payload=PgnImportRequest(
            source="pgn",
            pgn=TINY_PGN,
        ),
    )
    assert _rule_contracts(limiter.pop_call()) == {
        f"ip:{CLIENT_IP}:api": (1500, 60),
        f"ip:{CLIENT_IP}:analysis_start": (15, 600),
        f"ip:{CLIENT_IP}:analysis_start_day": (60, 86400),
        "global:analysis_start": (100, 60),
        f"ip:{CLIENT_IP}:pgn_start": (10, 600),
        f"ip:{CLIENT_IP}:pgn_start_day": (40, 86400),
    }

    protection.protect_import_start(
        request=_request(),
        payload=ChessComLiveImportRequest(
            source="chess_com_live_url",
            url="https://www.chess.com/game/live/168193636078",
        ),
    )
    assert _rule_contracts(limiter.pop_call()) == {
        f"ip:{CLIENT_IP}:api": (1500, 60),
        f"ip:{CLIENT_IP}:analysis_start": (15, 600),
        f"ip:{CLIENT_IP}:analysis_start_day": (60, 86400),
        "global:analysis_start": (100, 60),
        f"ip:{CLIENT_IP}:chesscom_start": (25, 3600),
        f"ip:{CLIENT_IP}:chesscom_start_day": (100, 86400),
        "global:chesscom_egress": (150, 60),
    }

    protection.protect_import_start(
        request=_request(),
        payload=LichessGameImportRequest(
            source="lichess_game_url",
            url="https://lichess.org/fY44h4OY",
        ),
    )
    assert _rule_contracts(limiter.pop_call()) == {
        f"ip:{CLIENT_IP}:api": (1500, 60),
        f"ip:{CLIENT_IP}:analysis_start": (15, 600),
        f"ip:{CLIENT_IP}:analysis_start_day": (60, 86400),
        "global:analysis_start": (100, 60),
        f"ip:{CLIENT_IP}:lichess_start": (50, 3600),
        f"ip:{CLIENT_IP}:lichess_start_day": (200, 86400),
        "global:lichess_egress": (100, 60),
    }

    protection.protect_cached_lookup(request=_request(), external_game_id="168193636078")
    assert _rule_contracts(limiter.pop_call()) == {
        f"ip:{CLIENT_IP}:api": (1500, 60),
        f"ip:{CLIENT_IP}:cached_lookup": (300, 60),
    }

    protection.protect_poll(request=_request(), analysis_id="analysis-1")
    assert _rule_contracts(limiter.pop_call()) == {
        f"ip:{CLIENT_IP}:api": (1500, 60),
        f"analysis:analysis-1:poll:{CLIENT_IP}": (450, 60),
        "analysis:analysis-1:poll:global": (3000, 60),
    }


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [
                (b"x-forwarded-for", b"192.0.2.99"),
                (b"user-agent", b"pytest"),
            ],
            "client": (CLIENT_IP, 49500),
        }
    )


def _rule_contracts(rules: list[RateLimitRule]) -> dict[str, tuple[int, int]]:
    return {rule.key: (rule.limit, rule.window_seconds) for rule in rules}
