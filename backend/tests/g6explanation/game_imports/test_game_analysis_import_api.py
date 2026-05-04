"""HTTP API tests for imported game analysis."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from concurrent.futures import Future
from typing import Any, cast

import chess
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
from g6explanation.game_imports import ChessComLiveGameResolver, GameImportService
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

1. e4 e5 2. Nf3 1-0
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
            "url": f"https://www.chess.com/game/live/{GAME_ID}",
            "explain_significance": ["low", "moderate", "high", "critical"],
            "include_context": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"]["source"] == "chess_com_live_url"
    assert payload["source"]["external_game_id"] == GAME_ID
    assert payload["source"]["allows_global_training"] is False

    snapshot_response = client.get(payload["status_url"])
    assert snapshot_response.status_code == 200
    snapshot = snapshot_response.json()
    assert snapshot["status"] == "succeeded"
    assert snapshot["total_plies"] == 3
    assert [move["san"] for move in snapshot["moves"]] == ["e4", "e5", "Nf3"]
    assert all(move["context"] is not None for move in snapshot["moves"])


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
    snapshot = client.get(payload["status_url"]).json()
    assert snapshot["status"] == "succeeded"


def _client(resolver: ChessComLiveGameResolver) -> TestClient:
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
        analysis_service=analysis_service,
        chess_com_resolver=resolver,
    )
    return TestClient(
        create_app(
            game_analysis_service=analysis_service,
            game_import_service=import_service,
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
            content=json.dumps({"explanation": explanation}),
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
