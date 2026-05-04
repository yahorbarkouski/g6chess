from __future__ import annotations

import json
import logging
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass, field
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
    PlayerLevel,
    Score,
)
from g6explanation.explanation_generation.contracts import CoachModelResponse, CoachPrompt
from g6explanation.explanation_generation.exceptions import CoachModelError
from g6explanation.game_analysis import (
    GameAnalysisRunner,
    GameAnalysisService,
    GameAnalysisSnapshot,
    GameAnalysisStartRequest,
    InMemoryGameAnalysisStore,
)
from g6explanation.visualization.http_api import create_app

TINY_PGN = """
[Event "Tiny"]
[Site "?"]
[Date "2026.05.03"]
[Round "?"]
[White "White"]
[Black "Black"]
[Result "*"]

1. e4 e5 2. Nf3 *
""".strip()


def test_game_analysis_http_api_starts_job_and_returns_completed_snapshot() -> None:
    store = RecordingGameAnalysisStore()
    service = GameAnalysisService(
        store=store,
        runner=GameAnalysisRunner(
            context_builder_factory=lambda: MoveContextBuilder(DynamicStaticAnalysisProvider()),
            coach_provider_factory=PromptEchoCoachProvider,
            context_workers=2,
            openrouter_concurrency=4,
        ),
        executor=InlineExecutor(),
    )
    client = TestClient(create_app(game_analysis_service=service))

    response = client.post(
        "/api/game-analysis",
        json=GameAnalysisStartRequest(
            pgn=TINY_PGN,
            player_level=PlayerLevel.rating(1500),
            time_control="rapid",
            explain_significance=["low", "moderate", "high", "critical"],
        ).to_dict(),
    )

    assert response.status_code == 200
    analysis_id = response.json()["analysis_id"]
    state_response = client.get(f"/api/game-analysis/{analysis_id}")
    assert state_response.status_code == 200
    snapshot = state_response.json()
    assert snapshot["status"] == "succeeded"
    assert snapshot["total_plies"] == 3
    assert snapshot["context_completed"] == 3
    assert snapshot["explanation_required"] == 3
    assert snapshot["explanation_completed"] == 3
    assert [move["san"] for move in snapshot["moves"]] == ["e4", "e5", "Nf3"]
    assert all(move["quality"] == "best" for move in snapshot["moves"])
    assert all(move["explanation"] for move in snapshot["moves"])
    assert any(saved.status == "running" and saved.context_completed > 0 for saved in store.saved)


def test_game_analysis_http_api_returns_404_for_unknown_job() -> None:
    service = GameAnalysisService(
        store=InMemoryGameAnalysisStore(),
        runner=GameAnalysisRunner(
            context_builder_factory=lambda: MoveContextBuilder(DynamicStaticAnalysisProvider()),
            coach_provider_factory=PromptEchoCoachProvider,
        ),
        executor=InlineExecutor(),
    )
    client = TestClient(create_app(game_analysis_service=service))

    response = client.get("/api/game-analysis/not-here")

    assert response.status_code == 404


def test_game_analysis_logs_explanation_provider_failures(caplog: pytest.LogCaptureFixture) -> None:
    store = RecordingGameAnalysisStore()
    service = GameAnalysisService(
        store=store,
        runner=GameAnalysisRunner(
            context_builder_factory=lambda: MoveContextBuilder(DynamicStaticAnalysisProvider()),
            coach_provider_factory=FailingCoachProvider,
            context_workers=1,
            openrouter_concurrency=1,
        ),
        executor=InlineExecutor(),
    )
    client = TestClient(create_app(game_analysis_service=service))

    with caplog.at_level(logging.ERROR, logger="g6explanation.game_analysis.analysis_runner"):
        response = client.post(
            "/api/game-analysis",
            json=GameAnalysisStartRequest(
                pgn=TINY_PGN,
                player_level=PlayerLevel.rating(1500),
                time_control="rapid",
                explain_significance=["low"],
                use_baseline_fallback=False,
            ).to_dict(),
        )

    assert response.status_code == 200
    snapshot = client.get(response.json()["status_url"]).json()
    assert snapshot["status"] == "failed"
    assert snapshot["error"] == (
        "3 requested explanation(s) failed. See per-move explanation_error fields and server logs."
    )
    assert snapshot["explanation_failed"] == 3
    assert all(
        "OpenRouter returned HTTP 400" in move["explanation_error"] for move in snapshot["moves"]
    )
    assert "Explanation generation failed" in caplog.text
    assert "OpenRouter returned HTTP 400" in caplog.text
    assert "line_card_anchor" in caplog.text


def _empty_snapshots() -> list[GameAnalysisSnapshot]:
    return []


@dataclass
class RecordingGameAnalysisStore:
    inner: InMemoryGameAnalysisStore = field(default_factory=InMemoryGameAnalysisStore)
    saved: list[GameAnalysisSnapshot] = field(default_factory=_empty_snapshots)

    def save(self, snapshot: GameAnalysisSnapshot) -> None:
        self.saved.append(snapshot)
        self.inner.save(snapshot)

    def get(self, analysis_id: str) -> GameAnalysisSnapshot | None:
        return self.inner.get(analysis_id)


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
            engine_version="static-game-analysis-test",
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
                    "segments": [
                        {"text": explanation, "line_card_id": None, "line_card_anchor": None}
                    ],
                    "line_cards": [],
                }
            ),
            finish_reason="stop",
        )


class FailingCoachProvider:
    @property
    def provider_name(self) -> str:
        return "openrouter"

    @property
    def model(self) -> str:
        return "openai/gpt-5.5"

    def generate(self, prompt: CoachPrompt) -> CoachModelResponse:
        del prompt
        raise CoachModelError(
            "OpenRouter returned HTTP 400 after 1 attempts: invalid schema missing line_card_anchor"
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
