"""Recent move facts derived from a replayed board stack."""

from __future__ import annotations

from dataclasses import dataclass

import chess


@dataclass(frozen=True)
class PreviousMoveDetails:
    uci: str
    san: str
    was_capture: bool


def previous_move_details(board: chess.Board) -> PreviousMoveDetails | None:
    """Return facts about the previous move when the board was replayed with stack."""

    if not board.move_stack:
        return None

    before_previous = board.copy(stack=True)
    previous_move = before_previous.pop()
    return PreviousMoveDetails(
        uci=previous_move.uci(),
        san=before_previous.san(previous_move),
        was_capture=before_previous.is_capture(previous_move),
    )


def previous_board(board: chess.Board) -> chess.Board | None:
    """Return the board before the previous move when history is available."""

    if not board.move_stack:
        return None
    before_previous = board.copy(stack=True)
    before_previous.pop()
    return before_previous
