from __future__ import annotations

import chess
import pytest

from g6explanation.context_engine.candidate_moves.findability import (
    assess_findability,
    forcing_tier,
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


def test_ordinary_capture_does_not_improve_findability() -> None:
    board = chess.Board("rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2")
    move = chess.Move.from_uci("e4d5")

    label, _, _, _ = assess_findability(
        probability=0.04,
        plus_400_probability=None,
        evidence_source=None,
        board=board,
        move=move,
        situation="unknown",
    )

    assert forcing_tier(board, move) == "ordinary_capture"
    assert label == "hard"


def test_check_improves_findability_one_bucket() -> None:
    board = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/2B1P3/8/PPPP1PPP/RNBQK1NR w KQkq - 0 2")
    move = chess.Move.from_uci("c4f7")

    label, _, _, _ = assess_findability(
        probability=0.04,
        plus_400_probability=None,
        evidence_source=None,
        board=board,
        move=move,
        situation="unknown",
    )

    assert forcing_tier(board, move) == "check"
    assert label == "findable"


def test_capture_after_non_capture_previous_move_is_not_recapture() -> None:
    board = chess.Board()
    board.push_san("e4")
    board.push_san("d5")
    move = chess.Move.from_uci("e4d5")
    previous_move_uci = board.peek().uci()

    label, _, _, _ = assess_findability(
        probability=0.04,
        plus_400_probability=None,
        evidence_source=None,
        board=board,
        move=move,
        situation="unknown",
        previous_move_uci=previous_move_uci,
    )

    assert forcing_tier(board, move, previous_move_uci) == "ordinary_capture"
    assert label == "hard"


def test_recapture_improves_findability_when_previous_move_was_capture() -> None:
    board = chess.Board()
    for san in ["e4", "c6", "Nf3", "d5", "exd5"]:
        board.push_san(san)
    move = chess.Move.from_uci("c6d5")
    previous_move_uci = board.peek().uci()

    label, _, _, _ = assess_findability(
        probability=0.04,
        plus_400_probability=None,
        evidence_source=None,
        board=board,
        move=move,
        situation="unknown",
        previous_move_uci=previous_move_uci,
    )

    assert forcing_tier(board, move, previous_move_uci) == "recapture"
    assert label == "findable"


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
