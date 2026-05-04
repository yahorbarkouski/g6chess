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
            ExplanationSegment(
                text="e4 claimed the center.",
                line_card_id="main",
                line_card_anchor="e4",
            ),
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


def test_explanation_output_rejects_card_segment_without_anchor() -> None:
    with pytest.raises(ValidationError):
        ExplanationOutput(
            segments=[
                ExplanationSegment(
                    text="e4 claimed the center.",
                    line_card_id="main",
                ),
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


def test_explanation_output_rejects_anchor_without_card() -> None:
    with pytest.raises(ValidationError):
        ExplanationOutput(
            segments=[
                ExplanationSegment(
                    text="e4 claimed the center.",
                    line_card_id=None,
                    line_card_anchor="e4",
                )
            ],
            line_cards=[],
        )


def test_explanation_output_rejects_anchor_not_in_segment_text() -> None:
    with pytest.raises(ValidationError):
        ExplanationOutput(
            segments=[
                ExplanationSegment(
                    text="e4 claimed the center.",
                    line_card_id="main",
                    line_card_anchor="Nf3",
                )
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


def test_explanation_output_rejects_long_anchor() -> None:
    with pytest.raises(ValidationError):
        ExplanationOutput(
            segments=[
                ExplanationSegment(
                    text=(
                        "e4 was important because the exact central pawn break "
                        "claimed space with tempo."
                    ),
                    line_card_id="main",
                    line_card_anchor="the exact central pawn break claimed space with tempo",
                )
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


def test_explanation_output_rejects_whole_long_segment_anchor() -> None:
    text = "one two three four five six seven eight nine"
    with pytest.raises(ValidationError):
        ExplanationOutput(
            segments=[
                ExplanationSegment(
                    text=text,
                    line_card_id="main",
                    line_card_anchor=text,
                )
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
