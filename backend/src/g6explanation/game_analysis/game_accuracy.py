"""Aggregate verified move accuracy for each side of a complete game."""

from collections.abc import Sequence
from statistics import fmean

from g6explanation.context_engine.contracts import ColorName
from g6explanation.context_engine.signals.move_accuracy import move_accuracy_percent
from g6explanation.game_analysis.contracts import GameAccuracy, GameMoveAnalysis


def game_accuracy(moves: Sequence[GameMoveAnalysis], total_plies: int) -> GameAccuracy | None:
    """Publish whole-game averages only after every requested ply is present."""

    if total_plies == 0 or len(moves) != total_plies:
        return None
    if {move.ply for move in moves} != set(range(1, total_plies + 1)):
        return None
    return GameAccuracy(
        white=_side_accuracy(moves, "white"),
        black=_side_accuracy(moves, "black"),
    )


def _side_accuracy(moves: Sequence[GameMoveAnalysis], color: ColorName) -> float | None:
    accuracies: list[float] = []
    for move in moves:
        if move.player_color != color:
            continue
        if not move.engine_top_lines or move.engine_played_line is None:
            return None
        accuracies.append(
            move_accuracy_percent(move.engine_top_lines[0].score, move.engine_played_line.score)
        )
    return round(fmean(accuracies), 1) if accuracies else None
