"""Aggregate verified move accuracy for each side through each game position."""

from collections.abc import Sequence

from g6explanation.context_engine.contracts import ColorName
from g6explanation.context_engine.signals.move_accuracy import move_accuracy_percent
from g6explanation.game_analysis.contracts import GameAccuracy, GameMoveAnalysis


def game_accuracy(moves: Sequence[GameMoveAnalysis], total_plies: int) -> GameAccuracy | None:
    """Publish whole-game averages only after every requested ply is present."""

    if total_plies == 0 or len(moves) != total_plies:
        return None
    return running_game_accuracy(moves).get(total_plies)


def running_game_accuracy(moves: Sequence[GameMoveAnalysis]) -> dict[int, GameAccuracy]:
    """Return per-side means through each ply of the contiguous analysed prefix."""

    totals: dict[ColorName, float] = {"white": 0.0, "black": 0.0}
    counts: dict[ColorName, int] = {"white": 0, "black": 0}
    missing: set[ColorName] = set()
    by_ply: dict[int, GameAccuracy] = {}
    for expected_ply, move in enumerate(sorted(moves, key=lambda item: item.ply), start=1):
        if move.ply != expected_ply:
            break
        color = move.player_color
        if not move.engine_top_lines or move.engine_played_line is None:
            missing.add(color)
        else:
            totals[color] += move_accuracy_percent(
                move.engine_top_lines[0].score, move.engine_played_line.score
            )
            counts[color] += 1
        by_ply[move.ply] = GameAccuracy(
            white=(
                round(totals["white"] / counts["white"], 1)
                if counts["white"] and "white" not in missing
                else None
            ),
            black=(
                round(totals["black"] / counts["black"], 1)
                if counts["black"] and "black" not in missing
                else None
            ),
        )
    return by_ply
