from __future__ import annotations

import chess
import pytest

from g6explanation.context_engine.candidate_moves.findability import (
    assess_findability,
    time_situation,
)
from g6explanation.context_engine.contracts import MoveContextRequest, PlayerLevel


@pytest.mark.parametrize(
    ("probability", "expected"),
    [
        (0.30, "obvious"),
        (0.12, "findable"),
        (0.04, "hard"),
        (0.01, "very_hard"),
        (0.009, "engine_like"),
    ],
)
def test_findability_probability_thresholds(probability: float, expected: str) -> None:
    board = chess.Board()
    move = chess.Move.from_uci("e2e4")

    label, source, confidence, skill_gap = assess_findability(
        probability=probability,
        plus_400_probability=None,
        evidence_source=None,
        board=board,
        move=move,
        situation="unknown",
    )

    assert label == expected
    assert source == "human_probability"
    assert confidence == "model"
    assert skill_gap is False


def test_low_time_worsens_findability() -> None:
    board = chess.Board()
    move = chess.Move.from_uci("e2e4")
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g2g4",
        player_color="white",
        player_level=PlayerLevel.rating(1000),
        clock_before_seconds=20,
    )

    label, _, confidence, _ = assess_findability(
        probability=0.12,
        plus_400_probability=None,
        evidence_source=None,
        board=board,
        move=move,
        situation=time_situation(request),
    )

    assert label == "hard"
    assert confidence == "model_time_adjusted"


def test_plus_400_probability_marks_teachable_skill_gap() -> None:
    board = chess.Board()
    move = chess.Move.from_uci("e2e4")

    _, _, _, skill_gap = assess_findability(
        probability=0.03,
        plus_400_probability=0.20,
        evidence_source=None,
        board=board,
        move=move,
        situation="unknown",
    )

    assert skill_gap is True


def test_unknown_human_evidence_stays_unknown_findability() -> None:
    board = chess.Board()
    move = chess.Move.from_uci("e2e4")

    label, source, confidence, skill_gap = assess_findability(
        probability=None,
        plus_400_probability=None,
        evidence_source=None,
        board=board,
        move=move,
        situation="unknown",
    )

    assert label == "unknown"
    assert source == "unknown"
    assert confidence == "none"
    assert skill_gap is False
