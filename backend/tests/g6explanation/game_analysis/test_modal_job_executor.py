from __future__ import annotations

import pytest

from g6explanation.context_engine.contracts import PlayerLevel
from g6explanation.game_analysis import (
    GameAnalysisRunner,
    GameAnalysisService,
    GameAnalysisStartRequest,
    InMemoryGameAnalysisStore,
    ModalSpawnGameAnalysisExecutor,
)

TINY_PGN = """
[Event "Tiny"]
[Site "?"]
[Date "2026.05.03"]
[Round "?"]
[White "White"]
[Black "Black"]
[Result "*"]

1. e4 *
""".strip()


def test_modal_spawn_executor_serializes_request_without_running_local_runner() -> None:
    spawned: list[tuple[str, str]] = []
    service = GameAnalysisService(
        store=InMemoryGameAnalysisStore(),
        runner=GameAnalysisRunner(),
        executor=ModalSpawnGameAnalysisExecutor(
            spawn_job=lambda analysis_id, request_json: spawned.append((analysis_id, request_json))
        ),
    )
    request = GameAnalysisStartRequest(
        pgn=TINY_PGN,
        player_level=PlayerLevel.rating(1500),
        time_control="rapid",
    )

    response = service.start(request)

    assert response.status == "pending"
    assert len(spawned) == 1
    spawned_analysis_id, spawned_request_json = spawned[0]
    assert spawned_analysis_id == response.analysis_id
    assert GameAnalysisStartRequest.model_validate_json(spawned_request_json) == request
    snapshot = service.get(response.analysis_id)
    assert snapshot is not None
    assert snapshot.status == "pending"
    assert snapshot.game is not None
    assert snapshot.game.total_plies == 1
    assert snapshot.game.moves[0].san == "e4"
    assert snapshot.game.moves[0].fen_before.startswith("rnbqkbnr/pppppppp")


def test_modal_spawn_executor_requires_keyword_job_payload() -> None:
    executor = ModalSpawnGameAnalysisExecutor(spawn_job=lambda _analysis_id, _request_json: None)

    with pytest.raises(ValueError, match="analysis_id"):
        executor.submit(lambda: None)

    with pytest.raises(TypeError, match="GameAnalysisStartRequest"):
        executor.submit(lambda: None, analysis_id="analysis-id")
