"""HTTP API tests for imported game analysis."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from concurrent.futures import Future
from typing import Any, cast

import chess
import pytest
from fastapi.testclient import TestClient

from g6explanation.context_engine import MoveContextBuilder
from g6explanation.context_engine.contracts import (
    ColorName,
    EngineAnalysis,
    EngineAnalysisBudget,
    EngineLine,
    Score,
)
from g6explanation.explanation_generation.contracts import CoachModelResponse, CoachPrompt
from g6explanation.game_analysis import (
    GameAnalysisRunner,
    GameAnalysisService,
    InMemoryGameAnalysisStore,
)
from g6explanation.game_imports import (
    ChessComLiveGameResolver,
    GameImportService,
    InMemoryGameAnalysisImportIndex,
)
from g6explanation.security import (
    ApiProtection,
    ClientIdentity,
    DisabledTurnstileVerifier,
    InMemoryFixedWindowRateLimiter,
    TurnstileVerificationError,
)
from g6explanation.visualization.http_api import create_app

GAME_ID = "168193636078"
TINY_PGN = """
[Event "Tiny"]
[Site "Chess.com"]
[Date "2026.05.03"]
[Round "-"]
[White "Alpha"]
[Black "Beta"]
[Result "1-0"]
[WhiteElo "1600"]
[BlackElo "1500"]
[TimeControl "180+2"]
[Link "https://www.chess.com/game/live/168193636078"]

1. e4 {[%clk 0:03:01]} 1... e5 {[%clk 0:02:59]} 2. Nf3 {[%clk 0:02:58]} 1-0
""".strip()


def test_import_api_starts_analysis_from_chess_com_url() -> None:
    client = _client(
        ChessComLiveGameResolver(
            transport=FakeChessComTransport(),
            sleep=lambda _: None,
        )
    )

    response = client.post(
        "/api/game-analysis/import",
        json={
            "source": "chess_com_live_url",
            "url": f"https://www.chess.com/game/{GAME_ID}",
            "explain_significance": ["low", "moderate", "high", "critical"],
            "include_context": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"]["source"] == "chess_com_live_url"
    assert payload["source"]["external_game_id"] == GAME_ID
    assert payload["source"]["allows_global_training"] is False
    assert payload["game"]["total_plies"] == 3
    assert [move["san"] for move in payload["game"]["moves"]] == ["e4", "e5", "Nf3"]
    assert [move["move_number"] for move in payload["game"]["moves"]] == [1, 1, 2]
    assert payload["game"]["moves"][0]["fen_before"].startswith("rnbqkbnr/pppppppp")
    assert [move["remaining_clock_seconds"] for move in payload["game"]["moves"]] == [
        181.0,
        179.0,
        178.0,
    ]

    snapshot_response = client.get(payload["status_url"])
    assert snapshot_response.status_code == 200
    snapshot = snapshot_response.json()
    assert snapshot["status"] == "succeeded"
    assert snapshot["total_plies"] == 3
    assert [move["san"] for move in snapshot["game"]["moves"]] == ["e4", "e5", "Nf3"]
    assert [move["san"] for move in snapshot["moves"]] == ["e4", "e5", "Nf3"]
    assert all(move["context"] is not None for move in snapshot["moves"])
    requests = [move["context"]["evidence"]["request"] for move in snapshot["moves"]]
    assert [request["player_level"]["value"] for request in requests] == [1600, 1500, 1600]
    assert [request["player_level"]["system"] for request in requests] == [
        "chess.com",
        "chess.com",
        "chess.com",
    ]
    assert [request["opponent_level"]["value"] for request in requests] == [1500, 1600, 1500]
    assert [request["clock_before_seconds"] for request in requests] == [180.0, 180.0, 181.0]
    assert [request["increment_seconds"] for request in requests] == [2.0, 2.0, 2.0]
    assert [move["remaining_clock_seconds"] for move in snapshot["moves"]] == [181.0, 179.0, 178.0]
    assert [move["think_time_seconds"] for move in snapshot["moves"]] == [1.0, 3.0, 5.0]


def test_import_api_returns_cached_chess_com_analysis_without_resubmitting() -> None:
    transport = CountingChessComTransport()
    client = _client(
        ChessComLiveGameResolver(
            transport=transport,
            sleep=lambda _: None,
        ),
        analysis_index=InMemoryGameAnalysisImportIndex(),
    )

    first_response = client.post(
        "/api/game-analysis/import",
        json={
            "source": "chess_com_live_url",
            "url": f"https://www.chess.com/game/live/{GAME_ID}",
            "explain_significance": ["critical"],
            "include_context": True,
        },
    )
    second_response = client.post(
        "/api/game-analysis/import",
        json={
            "source": "chess_com_live_url",
            "url": f"https://www.chess.com/game/live/{GAME_ID}",
            "explain_significance": ["critical"],
            "include_context": True,
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json()["analysis_id"] == first_response.json()["analysis_id"]
    assert transport.request_count == 2


def test_cached_import_lookup_returns_existing_chess_com_analysis() -> None:
    client = _client(
        ChessComLiveGameResolver(
            transport=FakeChessComTransport(),
            sleep=lambda _: None,
        ),
        analysis_index=InMemoryGameAnalysisImportIndex(),
    )

    import_response = client.post(
        "/api/game-analysis/import",
        json={
            "source": "chess_com_live_url",
            "url": f"https://www.chess.com/game/live/{GAME_ID}",
            "explain_significance": ["critical"],
            "include_context": True,
        },
    )
    lookup_response = client.get(f"/api/game-analysis/import/chess-com/live/{GAME_ID}")

    assert lookup_response.status_code == 200
    assert lookup_response.json()["analysis_id"] == import_response.json()["analysis_id"]
    assert lookup_response.json()["status_url"] == import_response.json()["status_url"]
    assert lookup_response.json()["source"]["external_game_id"] == GAME_ID


def test_cached_import_lookup_misses_unknown_chess_com_analysis() -> None:
    client = _client(
        ChessComLiveGameResolver(
            transport=FakeChessComTransport(),
            sleep=lambda _: None,
        ),
        analysis_index=InMemoryGameAnalysisImportIndex(),
    )

    response = client.get("/api/game-analysis/import/chess-com/live/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Cached game analysis not found."


def test_import_api_starts_analysis_from_pasted_pgn() -> None:
    client = _client(
        ChessComLiveGameResolver(
            transport=FakeChessComTransport(),
            sleep=lambda _: None,
        )
    )

    response = client.post(
        "/api/game-analysis/import",
        json={
            "source": "pgn",
            "pgn": TINY_PGN,
            "explain_significance": ["low", "moderate", "high", "critical"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"]["source"] == "pgn"
    assert payload["source"]["title"] == "Alpha vs Beta"
    assert payload["source"]["white_rating"] == 1600
    assert payload["source"]["black_rating"] == 1500
    assert payload["source"]["allows_global_training"] is False
    assert [move["san"] for move in payload["game"]["moves"]] == ["e4", "e5", "Nf3"]
    snapshot = client.get(payload["status_url"]).json()
    assert snapshot["status"] == "succeeded"


def test_import_api_rejects_pgn_without_ratings_instead_of_defaulting() -> None:
    client = _client(
        ChessComLiveGameResolver(
            transport=FakeChessComTransport(),
            sleep=lambda _: None,
        )
    )

    response = client.post(
        "/api/game-analysis/import",
        json={
            "source": "pgn",
            "pgn": '[Event "No ratings"]\n\n1. e4 e5 *',
        },
    )

    assert response.status_code == 422
    assert "PGN import did not include a white rating" in response.json()["detail"]


def test_import_api_accepts_explicit_side_ratings_for_unrated_pgn() -> None:
    client = _client(
        ChessComLiveGameResolver(
            transport=FakeChessComTransport(),
            sleep=lambda _: None,
        )
    )

    response = client.post(
        "/api/game-analysis/import",
        json={
            "source": "pgn",
            "pgn": '[Event "No ratings"]\n\n1. e4 e5 *',
            "white_player_level": {"kind": "rating", "value": 1400, "system": "manual"},
            "black_player_level": {"kind": "rating", "value": 1300, "system": "manual"},
            "include_context": True,
        },
    )

    assert response.status_code == 200
    snapshot = client.get(response.json()["status_url"]).json()
    assert snapshot["status"] == "succeeded"
    requests = [move["context"]["evidence"]["request"] for move in snapshot["moves"]]
    assert [request["player_level"]["value"] for request in requests] == [1400, 1300]


def test_import_api_denies_public_context_before_chess_com_resolution() -> None:
    transport = CountingChessComTransport()
    client = _client(
        ChessComLiveGameResolver(
            transport=transport,
            sleep=lambda _: None,
        ),
        api_protection=ApiProtection(
            limiter=InMemoryFixedWindowRateLimiter(),
            turnstile_verifier=DisabledTurnstileVerifier(),
            require_turnstile=False,
            allow_public_include_context=False,
        ),
    )

    response = client.post(
        "/api/game-analysis/import",
        json={
            "source": "chess_com_live_url",
            "url": f"https://www.chess.com/game/live/{GAME_ID}",
            "include_context": True,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "include_context_forbidden"
    assert transport.request_count == 0


def test_import_api_rate_limits_before_chess_com_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("G6EXPLANATION_LIMIT_ANALYSIS_START_10M", "1")
    transport = CountingChessComTransport()
    client = _client(
        ChessComLiveGameResolver(
            transport=transport,
            sleep=lambda _: None,
        ),
        api_protection=ApiProtection(
            limiter=InMemoryFixedWindowRateLimiter(),
            turnstile_verifier=DisabledTurnstileVerifier(),
            require_turnstile=False,
            allow_public_include_context=True,
        ),
    )

    first_response = client.post(
        "/api/game-analysis/import",
        json={
            "source": "chess_com_live_url",
            "url": f"https://www.chess.com/game/live/{GAME_ID}",
            "include_context": True,
        },
    )
    second_response = client.post(
        "/api/game-analysis/import",
        json={
            "source": "chess_com_live_url",
            "url": f"https://www.chess.com/game/live/{GAME_ID}",
            "include_context": True,
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 429
    assert second_response.headers["retry-after"]
    assert second_response.json()["detail"]["code"] == "import_start_rate_limited"
    assert transport.request_count == 2


def test_import_api_requires_turnstile_before_chess_com_resolution() -> None:
    transport = CountingChessComTransport()
    verifier = RequiredTurnstileVerifier()
    client = _client(
        ChessComLiveGameResolver(
            transport=transport,
            sleep=lambda _: None,
        ),
        api_protection=ApiProtection(
            limiter=InMemoryFixedWindowRateLimiter(),
            turnstile_verifier=verifier,
            require_turnstile=True,
            allow_public_include_context=True,
        ),
    )

    response = client.post(
        "/api/game-analysis/import",
        json={
            "source": "chess_com_live_url",
            "url": f"https://www.chess.com/game/live/{GAME_ID}",
            "include_context": True,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "turnstile_failed"
    assert transport.request_count == 0


def _client(
    resolver: ChessComLiveGameResolver,
    *,
    analysis_index: InMemoryGameAnalysisImportIndex | None = None,
    api_protection: ApiProtection | None = None,
) -> TestClient:
    store = InMemoryGameAnalysisStore()
    analysis_service = GameAnalysisService(
        store=store,
        runner=GameAnalysisRunner(
            context_builder_factory=lambda: MoveContextBuilder(DynamicStaticAnalysisProvider()),
            coach_provider_factory=PromptEchoCoachProvider,
            context_workers=2,
            openrouter_concurrency=4,
        ),
        executor=InlineExecutor(),
    )
    import_service = GameImportService(
        analysis_index=analysis_index,
        analysis_service=analysis_service,
        chess_com_resolver=resolver,
    )
    return TestClient(
        create_app(
            game_analysis_service=analysis_service,
            game_import_service=import_service,
            api_protection=api_protection,
        )
    )


class FakeChessComTransport:
    def __call__(
        self,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> tuple[int, bytes]:
        del headers, timeout_seconds
        if url.endswith(f"/callback/live/game/{GAME_ID}"):
            return 200, _json_bytes(
                {
                    "game": {
                        "isFinished": True,
                        "pgnHeaders": {
                            "Date": "2026.05.03",
                            "White": "Alpha",
                            "Black": "Beta",
                        },
                    }
                }
            )
        if "/player/alpha/games/2026/05" in url:
            return 200, _json_bytes(
                {
                    "games": [
                        {
                            "url": f"https://www.chess.com/game/live/{GAME_ID}",
                            "pgn": TINY_PGN,
                            "rules": "chess",
                        }
                    ]
                }
            )
        if "/player/beta/games/2026/05" in url:
            return 200, _json_bytes({"games": []})
        return 404, b"{}"


class CountingChessComTransport(FakeChessComTransport):
    def __init__(self) -> None:
        self.request_count = 0

    def __call__(
        self,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> tuple[int, bytes]:
        self.request_count += 1
        return super().__call__(url, headers, timeout_seconds)


class RequiredTurnstileVerifier:
    def verify(
        self,
        *,
        token: str | None,
        identity: ClientIdentity,
        idempotency_key: str | None = None,
    ) -> None:
        del identity, idempotency_key
        if token != "valid-turnstile-token":
            raise TurnstileVerificationError("Turnstile token is required.")


class InlineExecutor:
    def submit(
        self,
        fn: Callable[..., object],
        /,
        *args: object,
        **kwargs: object,
    ) -> Future[object]:
        future: Future[object] = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as exc:
            future.set_exception(exc)
        return future


class DynamicStaticAnalysisProvider:
    def analyze(
        self,
        board: chess.Board,
        played_move: chess.Move,
        player_color: ColorName,
    ) -> EngineAnalysis:
        after_board = board.copy(stack=False)
        after_board.push(played_move)
        return EngineAnalysis(
            engine_version="static-import-api-test",
            analysis_budget=EngineAnalysisBudget(kind="static", value=1, multipv=1),
            top_lines=[_engine_line(board, played_move, 30, rank=1)],
            played_line=_engine_line(board, played_move, 30, rank=None),
            after_line=_engine_line(after_board, next(iter(after_board.legal_moves)), 30, rank=1)
            if not after_board.is_game_over()
            else None,
        )


class PromptEchoCoachProvider:
    @property
    def provider_name(self) -> str:
        return "static-coach"

    @property
    def model(self) -> str:
        return "static-coach.v1"

    def generate(self, prompt: CoachPrompt) -> CoachModelResponse:
        payload = cast(dict[str, Any], json.loads(prompt.messages[1]["content"]))
        llm_context = cast(dict[str, str], payload["llm_context"])
        explanation = f"{llm_context['played']} was {llm_context['quality']}."
        return CoachModelResponse(
            provider_name=self.provider_name,
            model=self.model,
            content=json.dumps(
                {
                    "segments": [{"text": explanation, "line_card_id": None}],
                    "line_cards": [],
                }
            ),
            finish_reason="stop",
        )


def _engine_line(
    board: chess.Board,
    move: chess.Move,
    cp: int,
    *,
    rank: int | None,
) -> EngineLine:
    return EngineLine(
        move_uci=move.uci(),
        move_san=board.san(move),
        score=Score.cp(cp),
        rank=rank,
        pv_uci=[move.uci()],
        pv_san=[board.san(move)],
    )


def _json_bytes(value: dict[str, object]) -> bytes:
    return json.dumps(value).encode("utf-8")
