"""Move-quality and significance policy."""

from __future__ import annotations

from g6explanation.context_engine.contracts import (
    EngineAnalysis,
    EngineLine,
    MoveQuality,
    MoveQualityLabel,
    MoveSignificance,
    PlayedMoveFacts,
    Score,
    SignificanceLabel,
    Wdl,
)

BAD_QUALITY_LABELS: frozenset[MoveQualityLabel] = frozenset(
    {"inaccuracy", "mistake", "blunder", "missed_win"}
)
QUALITY_ORDER: dict[MoveQualityLabel, int] = {
    "best": 0,
    "excellent": 1,
    "good": 2,
    "neutral": 3,
    "inaccuracy": 4,
    "mistake": 5,
    "blunder": 6,
    "missed_win": 6,
}


def score_as_cp(score: Score) -> int:
    if score.kind == "cp":
        if score.value is None:
            raise ValueError("Centipawn score is missing value.")
        return score.value
    if score.mate_for == "player":
        return 100_000
    return -100_000


def classify_quality(analysis: EngineAnalysis, played: PlayedMoveFacts) -> MoveQuality:
    best = analysis.top_lines[0]
    played_line = analysis.played_line
    cp_loss = score_loss_cp(best.score, played_line.score)
    wdl_delta = _wdl_delta(best.wdl, played_line.wdl)
    wdl_loss = _wdl_expected_score_loss(best.wdl, played_line.wdl)

    if played_line.score.kind == "mate" and played_line.score.mate_for == "opponent":
        label: MoveQualityLabel = "blunder"
    elif (
        best.score.kind == "mate"
        and best.score.mate_for == "player"
        and not _is_player_mate(played_line.score)
    ):
        label = "missed_win"
    elif played.uci == best.move_uci:
        label = "best"
    else:
        cp_label = _label_from_cp_loss(cp_loss)
        wdl_label = _label_from_wdl_loss(wdl_loss)
        label = _worse_label(cp_label, wdl_label)

    return MoveQuality(
        label=label,
        score_delta_cp_player_pov=None if cp_loss is None else -cp_loss,
        score_loss_vs_best_cp=cp_loss,
        wdl_delta_player_pov=wdl_delta,
        wdl_expected_score_loss=wdl_loss,
        severity_text=_severity_text(best.score, played_line.score, cp_loss, wdl_loss),
    )


def calculate_significance(analysis: EngineAnalysis, played: PlayedMoveFacts) -> MoveSignificance:
    """Measure how much this move deserves emphasis relative to alternatives."""

    if _has_mate_transition(analysis):
        return MoveSignificance(label="critical", score=1.0)

    reference = _significance_reference_line(analysis, played)
    if reference is None:
        return MoveSignificance(label="low", score=0.0)

    played_line = analysis.played_line
    cp_gap = _absolute_cp_gap(played_line.score, reference.score)
    wdl_gap = _absolute_wdl_expected_gap(played_line.wdl, reference.wdl)

    cp_score = 0.0 if cp_gap is None else _clamp(cp_gap / 300)
    wdl_score = 0.0 if wdl_gap is None else _clamp(wdl_gap / 180)
    score = round(max(cp_score, wdl_score), 2)
    return MoveSignificance(label=_significance_label(score), score=score)


def line_score_loss(best_cp: int, line: EngineLine) -> int | None:
    if line.score.kind == "mate":
        return None
    return max(0, best_cp - score_as_cp(line.score))


def score_loss_cp(best: Score, played: Score) -> int | None:
    if best.kind == "mate" or played.kind == "mate":
        return None
    return max(0, score_as_cp(best) - score_as_cp(played))


def _wdl_delta(best: Wdl | None, played: Wdl | None) -> Wdl | None:
    if best is None or played is None:
        return None
    return Wdl(
        win=played.win - best.win,
        draw=played.draw - best.draw,
        loss=played.loss - best.loss,
    )


def _wdl_expected_score_loss(best: Wdl | None, played: Wdl | None) -> int | None:
    if best is None or played is None:
        return None
    return max(0, _wdl_expected_score(best) - _wdl_expected_score(played))


def _wdl_expected_score(wdl: Wdl) -> int:
    return round(wdl.win + (wdl.draw * 0.5))


def _label_from_cp_loss(loss: int | None) -> MoveQualityLabel:
    if loss is None:
        return "neutral"
    if loss <= 20:
        return "excellent"
    if loss <= 50:
        return "good"
    if loss <= 90:
        return "neutral"
    if loss <= 150:
        return "inaccuracy"
    if loss <= 300:
        return "mistake"
    return "blunder"


def _label_from_wdl_loss(loss: int | None) -> MoveQualityLabel:
    if loss is None:
        return "neutral"
    if loss <= 10:
        return "excellent"
    if loss <= 25:
        return "good"
    if loss <= 45:
        return "neutral"
    if loss <= 80:
        return "inaccuracy"
    if loss <= 150:
        return "mistake"
    return "blunder"


def _worse_label(left: MoveQualityLabel, right: MoveQualityLabel) -> MoveQualityLabel:
    return left if QUALITY_ORDER[left] >= QUALITY_ORDER[right] else right


def _is_player_mate(score: Score) -> bool:
    return score.kind == "mate" and score.mate_for == "player"


def _has_mate_transition(analysis: EngineAnalysis) -> bool:
    best = analysis.top_lines[0].score
    played = analysis.played_line.score
    if best.kind == "mate" and best.mate_for == "player" and not _is_player_mate(played):
        return True
    return played.kind == "mate" and played.mate_for == "opponent"


def _significance_reference_line(
    analysis: EngineAnalysis, played: PlayedMoveFacts
) -> EngineLine | None:
    if played.uci != analysis.top_lines[0].move_uci:
        return analysis.top_lines[0]
    return next(
        (line for line in analysis.top_lines[1:] if line.move_uci != played.uci),
        None,
    )


def _absolute_cp_gap(left: Score, right: Score) -> int | None:
    if left.kind == "mate" or right.kind == "mate":
        return None
    return abs(score_as_cp(left) - score_as_cp(right))


def _absolute_wdl_expected_gap(left: Wdl | None, right: Wdl | None) -> int | None:
    if left is None or right is None:
        return None
    return abs(_wdl_expected_score(left) - _wdl_expected_score(right))


def _significance_label(score: float) -> SignificanceLabel:
    if score >= 0.65:
        return "critical"
    if score >= 0.35:
        return "high"
    if score >= 0.15:
        return "moderate"
    return "low"


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _severity_text(
    best: Score,
    played: Score,
    cp_loss: int | None,
    wdl_loss: int | None,
) -> str:
    if best.kind == "mate" or played.kind == "mate":
        if played.kind == "mate" and played.mate_for == "opponent":
            return "the move allowed a forced mate against the player"
        if best.kind == "mate" and best.mate_for == "player":
            return "the best line had a forced mate for the player"
        return "the move changed a forced-mate evaluation"
    text = f"from {_score_band(score_as_cp(best))} to {_score_band(score_as_cp(played))}"
    if wdl_loss is not None and wdl_loss > 45:
        return f"{text}, with expected score dropping by {wdl_loss}/1000"
    if cp_loss is not None:
        return f"{text}, losing {cp_loss} centipawns versus the best move"
    return text


def _score_band(cp: int) -> str:
    if cp >= 300:
        return "winning"
    if cp >= 150:
        return "clearly better"
    if cp >= 50:
        return "slightly better"
    if cp > -50:
        return "roughly equal"
    if cp > -150:
        return "slightly worse"
    if cp > -300:
        return "clearly worse"
    return "losing"
