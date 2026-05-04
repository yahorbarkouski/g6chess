"""Candidate findability and time-pressure policy."""

from __future__ import annotations

import chess

from g6explanation.context_engine.contracts import (
    FindabilityLabel,
    ForcingTier,
    MoveContextRequest,
    TimeSituation,
)
from g6explanation.context_engine.move_history import previous_move_details

FINDABILITY_STEPS: tuple[FindabilityLabel, ...] = (
    "obvious",
    "findable",
    "hard",
    "very_hard",
    "engine_like",
)


def time_situation(request: MoveContextRequest) -> TimeSituation:
    clock = request.clock_before_seconds
    increment = request.increment_seconds or 0
    if clock is not None:
        if clock <= 10 and increment <= 2:
            return "time_scramble"
        if clock <= 30:
            return "low_time"

    control = (request.time_control or "").lower()
    if "bullet" in control:
        return "time_scramble"
    if "blitz" in control:
        return "blitz_normal"
    if "rapid" in control:
        return "rapid_normal"
    if "classical" in control:
        return "classical_or_no_pressure"
    return "unknown"


def assess_findability(
    probability: float | None,
    plus_400_probability: float | None,
    evidence_source: str | None,
    board: chess.Board,
    move: chess.Move,
    situation: TimeSituation,
    previous_move_uci: str | None = None,
    previous_move_was_capture: bool | None = None,
) -> tuple[FindabilityLabel, str, str, bool]:
    if probability is None:
        return "unknown", evidence_source or "unknown", "none", False

    label = _base_findability(probability)
    if (
        forcing_tier(
            board,
            move,
            previous_move_uci,
            previous_move_was_capture=previous_move_was_capture,
        )
        in FINDABILITY_BOOSTING_TIERS
    ):
        label = _improve_findability(label)
    if situation in {"low_time", "time_scramble"}:
        label = _worsen_findability(label)

    skill_gap = _teachable_skill_gap(probability, plus_400_probability)
    confidence = "model_time_adjusted" if situation != "unknown" else "model"
    return label, evidence_source or "human_probability", confidence, skill_gap


def _base_findability(probability: float) -> FindabilityLabel:
    if probability >= 0.30:
        return "obvious"
    if probability >= 0.12:
        return "findable"
    if probability >= 0.04:
        return "hard"
    if probability >= 0.01:
        return "very_hard"
    return "engine_like"


FINDABILITY_BOOSTING_TIERS: frozenset[ForcingTier] = frozenset(
    {"mate", "check", "forced_reply", "recapture", "promotion"}
)


def forcing_tier(
    board: chess.Board,
    move: chess.Move,
    previous_move_uci: str | None = None,
    *,
    previous_move_was_capture: bool | None = None,
) -> ForcingTier:
    if move not in board.legal_moves:
        return "quiet"

    after = board.copy(stack=False)
    after.push(move)
    if after.is_checkmate():
        return "mate"
    if board.gives_check(move):
        return "check"
    if _has_only_one_reply(after):
        return "forced_reply"
    if move.promotion is not None:
        return "promotion"
    if board.is_capture(move):
        if _is_recapture(board, move, previous_move_uci, previous_move_was_capture):
            return "recapture"
        return "ordinary_capture"
    return "quiet"


def _has_only_one_reply(board_after_move: chess.Board) -> bool:
    legal_moves = board_after_move.legal_moves
    return legal_moves.count() == 1


def _is_recapture(
    board: chess.Board,
    move: chess.Move,
    previous_move_uci: str | None,
    previous_move_was_capture: bool | None,
) -> bool:
    previous = previous_move_details(board)
    if previous is not None and (previous_move_uci is None or previous.uci == previous_move_uci):
        previous_move_uci = previous.uci
        previous_move_was_capture = previous.was_capture
    if previous_move_uci is None:
        return False
    try:
        previous_move = chess.Move.from_uci(previous_move_uci)
    except ValueError:
        return False
    return bool(previous_move_was_capture) and move.to_square == previous_move.to_square


def _teachable_skill_gap(probability: float, plus_400_probability: float | None) -> bool:
    if plus_400_probability is None:
        return False
    return plus_400_probability >= 0.12 and plus_400_probability - probability >= 0.08


def _worsen_findability(label: FindabilityLabel) -> FindabilityLabel:
    if label not in FINDABILITY_STEPS:
        return label
    return FINDABILITY_STEPS[min(FINDABILITY_STEPS.index(label) + 1, len(FINDABILITY_STEPS) - 1)]


def _improve_findability(label: FindabilityLabel) -> FindabilityLabel:
    if label not in FINDABILITY_STEPS:
        return label
    return FINDABILITY_STEPS[max(FINDABILITY_STEPS.index(label) - 1, 0)]
