from __future__ import annotations

from fastapi.testclient import TestClient

from g6explanation.visualization.example_catalog import visualization_examples
from g6explanation.visualization.http_api import app


def test_visualization_catalog_exposes_three_verified_test_examples() -> None:
    examples = visualization_examples()

    assert [example.id for example in examples] == [
        "practical-alternative-g4",
        "hard-resource-a3",
        "quiet-queen-sacrifice",
    ]
    assert all(example.moves for example in examples)
    assert all(example.contexts for example in examples)
    for example in examples:
        context_plies = {context.ply for context in example.contexts}
        assert context_plies == {move.ply for move in example.moves if move.has_context}
        assert all(context.result.verification.passed for context in example.contexts)


def test_visualization_http_api_returns_summary_and_full_example() -> None:
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
    assert example["contexts"][0]["result"]["verification"]["passed"] is True


def test_visualization_http_api_returns_404_for_unknown_example() -> None:
    client = TestClient(app)

    response = client.get("/api/visualization/examples/not-here")

    assert response.status_code == 404
