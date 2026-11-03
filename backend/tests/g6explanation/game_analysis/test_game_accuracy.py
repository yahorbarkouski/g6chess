import pytest
from pydantic import ValidationError

from g6explanation.context_engine.contracts import EngineLine, MoveBeauty, MoveSignificance, Score
from g6explanation.game_analysis.contracts import GameAccuracy, GameMoveAnalysis
from g6explanation.game_analysis.game_accuracy import game_accuracy, running_game_accuracy


def _move(ply: int, best: Score, played: Score) -> GameMoveAnalysis:
    return GameMoveAnalysis(
        ply=ply,
        san="e4" if ply % 2 else "e5",
        uci="e2e4" if ply % 2 else "e7e5",
        player_color="white" if ply % 2 else "black",
        state="context_ready",
        requires_explanation=False,
        quality="good",
        significance=MoveSignificance(label="low", score=0),
        beauty=MoveBeauty(label="low", score=0),
        context_latency_seconds=0,
        engine_top_lines=[EngineLine(move_uci="e2e4", move_san="e4", score=best)],
        engine_played_line=EngineLine(move_uci="e2e4", move_san="e4", score=played),
    )


def test_averages_all_moves_separately_in_each_players_perspective() -> None:
    moves = [
        _move(3, Score.mate(1, "player"), Score.mate(1, "opponent")),
        _move(2, Score.cp(0), Score.cp(-100)),
        _move(1, Score.cp(0), Score.cp(0)),
    ]

    accuracy = game_accuracy(moves, 3)

    assert accuracy == GameAccuracy(white=50.0, black=66.2)
    assert game_accuracy(list(reversed(moves)), 3) == accuracy


def test_incomplete_duplicate_and_empty_games_have_no_global_accuracy() -> None:
    move = _move(1, Score.cp(0), Score.cp(0))

    assert game_accuracy([move], 2) is None
    assert game_accuracy([move, move], 2) is None
    assert game_accuracy([], 0) is None


def test_running_accuracy_uses_only_moves_through_each_ply() -> None:
    moves = [
        _move(3, Score.mate(1, "player"), Score.mate(1, "opponent")),
        _move(1, Score.cp(0), Score.cp(0)),
        _move(2, Score.cp(0), Score.cp(-100)),
    ]

    assert running_game_accuracy(moves) == {
        1: GameAccuracy(white=100, black=None),
        2: GameAccuracy(white=100, black=66.2),
        3: GameAccuracy(white=50, black=66.2),
    }


def test_running_accuracy_waits_for_gaps_and_keeps_missing_evidence_unavailable() -> None:
    first = _move(1, Score.cp(0), Score.cp(0))
    third = _move(3, Score.cp(0), Score.cp(-100))

    assert running_game_accuracy([third]) == {}
    assert running_game_accuracy([first, third]) == {1: GameAccuracy(white=100, black=None)}
    second = _move(2, Score.cp(0), Score.cp(0))
    missing = first.model_copy(update={"engine_top_lines": []})
    assert running_game_accuracy([missing, second, third]) == {
        1: GameAccuracy(white=None, black=None),
        2: GameAccuracy(white=None, black=100),
        3: GameAccuracy(white=None, black=100),
    }


def test_side_without_moves_or_complete_engine_evidence_is_unavailable() -> None:
    move = _move(1, Score.cp(0), Score.cp(0))

    assert game_accuracy([move], 1) == GameAccuracy(white=100, black=None)
    missing = move.model_copy(update={"engine_played_line": None})
    assert game_accuracy([missing], 1) == GameAccuracy(white=None, black=None)
    missing = move.model_copy(update={"engine_top_lines": []})
    assert game_accuracy([missing], 1) == GameAccuracy(white=None, black=None)


@pytest.mark.parametrize("value", [-1, 101, float("nan"), float("inf")])
def test_accuracy_contract_rejects_invalid_percentages(value: float) -> None:
    with pytest.raises(ValidationError):
        GameAccuracy(white=value)
