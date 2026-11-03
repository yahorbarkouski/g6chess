import pytest

from g6explanation.context_engine.contracts import Score
from g6explanation.context_engine.signals.move_accuracy import move_accuracy_percent


@pytest.mark.parametrize(
    ("best", "played"),
    [
        (Score.cp(50), Score.cp(50)),
        (Score.cp(50), Score.cp(60)),
        (Score.mate(2, "player"), Score.mate(5, "player")),
        (Score.mate(5, "opponent"), Score.mate(2, "opponent")),
    ],
)
def test_preserving_winning_chances_has_full_accuracy(best: Score, played: Score) -> None:
    assert move_accuracy_percent(best, played) == 100.0


def test_accuracy_uses_winning_chance_loss_instead_of_raw_centipawn_loss() -> None:
    equal_position = move_accuracy_percent(Score.cp(0), Score.cp(-100))
    winning_position = move_accuracy_percent(Score.cp(1000), Score.cp(900))

    assert equal_position == pytest.approx(66.242, abs=0.001)
    assert winning_position > equal_position
    assert move_accuracy_percent(Score.cp(0), Score.cp(-300)) < equal_position


def test_mate_uses_outcome_endpoints_and_keeps_zero_accuracy() -> None:
    assert move_accuracy_percent(Score.mate(1, "player"), Score.mate(1, "opponent")) == 0
    assert move_accuracy_percent(Score.cp(0), Score.mate(1, "opponent")) < 10
    assert move_accuracy_percent(Score.cp(0), Score.cp(-100_000)) < 10
    assert move_accuracy_percent(Score.cp(100_000), Score.cp(100_000)) == 100
