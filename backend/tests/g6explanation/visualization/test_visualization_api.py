from __future__ import annotations

import chess
import pytest
from fastapi.testclient import TestClient

from g6explanation.context_engine import MoveContextBuilder
from g6explanation.context_engine.contracts import MoveContextRequest, PlayerLevel
from g6explanation.visualization.contracts import VisualizationMoveContext
from g6explanation.visualization.example_catalog import visualization_examples
from g6explanation.visualization.http_api import app, create_app
from tests.g6explanation.context_engine.helpers import StaticAnalysisProvider, analysis


def test_visualization_catalog_exposes_three_real_game_experiments_without_context_cache() -> None:
    examples = visualization_examples()

    assert [example.id for example in examples] == [
        "morphy-opera-1858",
        "byrne-fischer-1956",
        "kasparov-topalov-1999",
    ]
    assert all(example.moves for example in examples)
    assert all(not example.contexts for example in examples)
    for example in examples:
        assert all(move.has_context for move in example.moves)


def test_visualization_http_api_returns_summary_and_full_experiment_metadata() -> None:
    client = TestClient(app)

    summary_response = client.get("/api/visualization/examples")
    assert summary_response.status_code == 200
    summaries = summary_response.json()["examples"]
    assert len(summaries) == 3

    example_id = summaries[0]["id"]
    example_response = client.get(f"/api/visualization/examples/{example_id}")
    assert example_response.status_code == 200
    example = example_response.json()
    assert example["id"] == example_id
    assert example["source"].startswith("PGN:")
    assert example["contexts"] == []


def test_visualization_http_api_returns_404_for_unknown_example() -> None:
    client = TestClient(app)

    response = client.get("/api/visualization/examples/not-here")

    assert response.status_code == 404


def test_visualization_http_api_builds_context_on_context_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_context(example_id: str, ply: int) -> VisualizationMoveContext | None:
        assert example_id == "morphy-opera-1858"
        assert ply == 1
        board = chess.Board()
        result = MoveContextBuilder(
            StaticAnalysisProvider(
                analysis(
                    board,
                    played_uci="e2e4",
                    top_scores=[("e2e4", 40), ("d2d4", 20)],
                    played_score=40,
                )
            )
        ).build(
            MoveContextRequest(
                fen_before=board.fen(),
                played_move="e2e4",
                player_color="white",
                player_level=PlayerLevel.rating(2400, "test"),
                time_control="classical",
            )
        )
        return VisualizationMoveContext(ply=ply, result=result)

    monkeypatch.setattr(
        "g6explanation.visualization.http_api.build_visualization_context",
        fake_context,
    )
    client = TestClient(app)

    response = client.get("/api/visualization/examples/morphy-opera-1858/contexts/1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ply"] == 1
    assert payload["result"]["verification"]["passed"] is True


def test_visualization_context_endpoint_can_be_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("G6EXPLANATION_ENABLE_VISUALIZATION_CONTEXTS", "false")
    client = TestClient(create_app())

    response = client.get("/api/visualization/examples/morphy-opera-1858/contexts/1")

    assert response.status_code == 404
