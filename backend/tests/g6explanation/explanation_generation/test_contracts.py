from __future__ import annotations

import pytest
from pydantic import ValidationError

from g6explanation.explanation_generation.contracts import (
    ExplanationLineCard,
    ExplanationOutput,
    ExplanationSegment,
)


def test_explanation_output_accepts_segments_and_line_cards() -> None:
    output = ExplanationOutput(
        segments=[
            ExplanationSegment(text="e4 claimed the center.", line_card_id="main"),
        ],
        line_cards=[
            ExplanationLineCard(
                id="main",
                moves=["e4", "e5"],
                title="Central line",
                why="The line shows the central reply.",
            )
        ],
    )

    assert output.explanation == "e4 claimed the center."


def test_explanation_output_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ExplanationOutput.model_validate(
            {
                "segments": [{"text": "e4 was the best move.", "line_card_id": None}],
                "line_cards": [],
                "line": "e4 e5",
            }
        )


def test_explanation_output_rejects_empty_text() -> None:
    with pytest.raises(ValidationError):
        ExplanationOutput(
            segments=[ExplanationSegment(text="   ", line_card_id=None)],
            line_cards=[],
        )


def test_explanation_output_rejects_unreferenced_line_card() -> None:
    with pytest.raises(ValidationError):
        ExplanationOutput(
            segments=[ExplanationSegment(text="e4 claimed the center.", line_card_id=None)],
            line_cards=[
                ExplanationLineCard(
                    id="main",
                    moves=["e4", "e5"],
                    title="Central line",
                    why="The line shows the central reply.",
                )
            ],
        )
