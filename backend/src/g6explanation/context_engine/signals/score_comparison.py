"""Shared score and WDL comparison helpers for move signals."""

from __future__ import annotations

from g6explanation.context_engine.contracts import EngineAnalysis, EngineLine, Score, Wdl


def score_as_cp(score: Score) -> int:
    if score.kind == "cp":
        if score.value is None:
            raise ValueError("Centipawn score is missing value.")
        return score.value
    if score.mate_for == "player":
        return 100_000
    return -100_000


def line_score_loss(best: Score, line: EngineLine) -> int | None:
    if best.kind == "mate" or line.score.kind == "mate":
        return None
    return max(0, score_as_cp(best) - score_as_cp(line.score))


def score_loss_cp(best: Score, played: Score) -> int | None:
    if best.kind == "mate" or played.kind == "mate":
        return None
    return max(0, score_as_cp(best) - score_as_cp(played))


def wdl_delta(best: Wdl | None, played: Wdl | None) -> Wdl | None:
    if best is None or played is None:
        return None
    return Wdl(
        win=played.win - best.win,
        draw=played.draw - best.draw,
        loss=played.loss - best.loss,
    )


def wdl_expected_score_loss(best: Wdl | None, played: Wdl | None) -> int | None:
    if best is None or played is None:
        return None
    return max(0, wdl_expected_score(best) - wdl_expected_score(played))


def wdl_expected_score(wdl: Wdl) -> int:
    return round(wdl.win + (wdl.draw * 0.5))


def is_player_mate(score: Score) -> bool:
    return score.kind == "mate" and score.mate_for == "player"


def has_mate_transition(analysis: EngineAnalysis) -> bool:
    best = analysis.top_lines[0].score
    played = analysis.played_line.score
    if best.kind == "mate" and best.mate_for == "player" and not is_player_mate(played):
        return True
    return played.kind == "mate" and played.mate_for == "opponent"


def absolute_cp_gap(left: Score, right: Score) -> int | None:
    if left.kind == "mate" or right.kind == "mate":
        return None
    return abs(score_as_cp(left) - score_as_cp(right))


def absolute_wdl_expected_gap(left: Wdl | None, right: Wdl | None) -> int | None:
    if left is None or right is None:
        return None
    return abs(wdl_expected_score(left) - wdl_expected_score(right))
