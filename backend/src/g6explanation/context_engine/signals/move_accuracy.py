"""Move accuracy from verified, player-perspective Stockfish scores."""

import math

from g6explanation.context_engine.contracts import Score


def move_accuracy_percent(best: Score, played: Score) -> float:
    """Apply Lichess's move-accuracy curve to winning-chance loss.

    Mate is an outcome endpoint, never a synthetic centipawn score.
    Independent searches can score the played move above the best line;
    that search noise incurs no accuracy penalty.
    """

    loss = _winning_chances_percent(best) - _winning_chances_percent(played)
    if loss <= 0:
        return 100.0
    return max(0.0, min(100.0, 103.1668 * math.exp(-0.04354 * loss) - 3.1669))


def _winning_chances_percent(score: Score) -> float:
    if score.kind == "mate":
        return 100.0 if score.mate_for == "player" else 0.0
    assert score.value is not None
    # Equivalent to the published logistic curve, without exponential overflow.
    return 50.0 + 50.0 * math.tanh(0.00368208 * score.value / 2.0)
