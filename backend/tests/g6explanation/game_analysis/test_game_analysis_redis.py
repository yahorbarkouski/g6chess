from __future__ import annotations

import os
import time
import uuid
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from g6explanation.context_engine import PlayerLevel
from g6explanation.game_analysis import (
    GameAnalysisRunner,
    GameAnalysisService,
    GameAnalysisStartRequest,
    RedisGameAnalysisStore,
)
from g6explanation.game_analysis.contracts import GameAnalysisSnapshot
from g6explanation.game_analysis.state_store import GameAnalysisStoreError
from g6explanation.real_game_evaluation.real_games import OPERA_GAME
from g6explanation.visualization.http_api import create_app

REDIS_URL = os.getenv("G6EXPLANATION_REDIS_URL", "redis://localhost:6379/0")


def test_redis_game_analysis_store_round_trips_snapshot_when_redis_is_available() -> None:
    store = _redis_store_or_skip("redis-roundtrip")
    now = "2026-05-03T00:00:00+00:00"
    snapshot = GameAnalysisSnapshot(
        analysis_id=uuid.uuid4().hex,
        status="pending",
        total_plies=1,
        context_completed=0,
        explanation_required=0,
        explanation_completed=0,
        explanation_failed=0,
        explain_significance=["critical"],
        created_at=now,
        updated_at=now,
    )

    store.save(snapshot)

    assert store.get(snapshot.analysis_id) == snapshot


@pytest.mark.skipif(
    os.getenv("G6EXPLANATION_RUN_REAL_GAME_ANALYSIS") != "1",
    reason=(
        "set G6EXPLANATION_RUN_REAL_GAME_ANALYSIS=1 to run real Redis, "
        "Stockfish, Maia, and OpenRouter game analysis"
    ),
)
def test_real_game_analysis_endpoint_runs_opera_game_with_real_providers() -> None:
    store = _redis_store_or_skip("real-game-analysis")
    service = GameAnalysisService(
        store=store,
        runner=GameAnalysisRunner(context_workers=8, openrouter_concurrency=30),
    )
    client = TestClient(create_app(game_analysis_service=service))

    response = client.post(
        "/api/game-analysis",
        json=GameAnalysisStartRequest(
            pgn=OPERA_GAME,
            player_level=PlayerLevel.rating(2400, "historical-demo"),
            time_control="classical",
            explain_significance=["critical"],
            include_context=True,
            use_baseline_fallback=False,
        ).to_dict(),
    )

    assert response.status_code == 200
    analysis_id = response.json()["analysis_id"]
    snapshot = _poll_until_terminal(client, analysis_id, timeout_seconds=180)

    assert snapshot["status"] == "succeeded"
    assert snapshot["total_plies"] == 33
    assert snapshot["context_completed"] == 33
    assert cast(int, snapshot["explanation_required"]) > 0
    assert snapshot["explanation_completed"] == snapshot["explanation_required"]
    assert snapshot["explanation_failed"] == 0
    moves = cast(list[dict[str, Any]], snapshot["moves"])
    explained = [move for move in moves if move["requires_explanation"]]
    assert all(move["explanation"] for move in explained)
    assert all(cast(str, move["explanation_model"]).startswith("openai/gpt") for move in explained)
    assert all(
        min(line["depth"] for line in move["context"]["evidence"]["engine"]["top_lines"]) >= 16
        for move in moves
    )
    assert any(
        candidate["player_level_probability"] is not None
        for move in moves
        for candidate in move["context"]["evidence"]["candidates"]
    )


def _redis_store_or_skip(name: str) -> RedisGameAnalysisStore:
    store = RedisGameAnalysisStore.from_url(
        REDIS_URL,
        key_prefix=f"g6:test:{name}:{uuid.uuid4().hex}",
        ttl_seconds=10 * 60,
    )
    try:
        store.ping()
    except GameAnalysisStoreError as exc:
        pytest.skip(str(exc))
    return store


def _poll_until_terminal(
    client: TestClient,
    analysis_id: str,
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_snapshot: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        response = client.get(f"/api/game-analysis/{analysis_id}")
        assert response.status_code == 200
        last_snapshot = cast(dict[str, Any], response.json())
        if last_snapshot["status"] in {"succeeded", "failed"}:
            return last_snapshot
        time.sleep(1.0)
    raise AssertionError(f"Game analysis did not finish: {last_snapshot}")
