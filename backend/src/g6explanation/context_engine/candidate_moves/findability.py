"""Candidate findability and time-pressure policy."""

from __future__ import annotations

import chess

from g6explanation.context_engine.contracts import (
    FindabilityLabel,
    MoveContextRequest,
    TimeSituation,
)

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
) -> tuple[FindabilityLabel, str, str, bool]:
    if probability is None:
        return "unknown", evidence_source or "unknown", "none", False

    label = _base_findability(probability)
    if move in board.legal_moves and _is_forcing_move(board, move):
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


def _is_forcing_move(board: chess.Board, move: chess.Move) -> bool:
    return board.gives_check(move) or board.is_capture(move) or move.promotion is not None


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
